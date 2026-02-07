"""Workflow Graph using LangGraph's Orchestrator-Worker + Send pattern.

This module implements a freely composable multi-step workflow engine:
1. Planner node: generates a multi-step plan (YAML template or LLM dynamic)
2. assign_workers: uses Send API to fan-out parallel workers
3. worker_task node: individual worker execution with isolated WorkerTaskState
4. synthesizer node: aggregates all worker results into final output

Supports:
- Parallel execution of independent steps via Send
- Sequential dependency chains via multi-round scheduling
- HITL approval integration for sensitive tool calls
"""

from typing import (
    AsyncGenerator,
    Optional,
)

from langchain_core.messages import AIMessage
from langfuse.langchain import CallbackHandler
from langgraph.graph import (
    END,
    START,
    StateGraph,
)
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import (
    RunnableConfig,
    Send,
)

from app.core.config import (
    Environment,
    settings,
)
from app.core.langgraph.agents.workers import WORKER_REGISTRY
from app.core.langgraph.base import BaseAgentMixin
from app.core.langgraph.workflow.planner import WorkflowPlanner
from app.core.langgraph.workflow.schema import (
    WorkerResult,
    WorkerTaskState,
    WorkflowPlan,
    WorkflowState,
    WorkflowStep,
)
from app.core.logging import logger
from app.schemas import Message
from app.utils import dump_messages


class WorkflowGraph(BaseAgentMixin):
    """Orchestrator-Worker workflow graph with Send-based parallel execution.

    Graph structure:
        START → planner → assign_workers(Send) → worker_task → check_completion
              → (more rounds or) → synthesizer → END
    """

    def __init__(self):
        """Initialize the WorkflowGraph."""
        self.planner = WorkflowPlanner()
        self._connection_pool = None
        self._graph: Optional[CompiledStateGraph] = None
        logger.info(
            "workflow_graph_initialized",
            available_workers=list(WORKER_REGISTRY.keys()),
        )

    # ─── Graph Nodes ───────────────────────────────────────────────

    async def _planner_node(self, state: WorkflowState, config: RunnableConfig) -> dict:
        """Planner node: generate a multi-step workflow plan."""
        session_id = config["configurable"]["thread_id"]
        user_message = ""
        for msg in reversed(state.messages):
            if hasattr(msg, "type") and msg.type == "human":
                user_message = msg.content
                break
            elif isinstance(msg, dict) and msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        # Check if a template name was passed via config metadata
        template_name = config.get("metadata", {}).get("workflow_template")

        logger.info(
            "workflow_planner_entered",
            session_id=session_id,
            user_input=user_message[:200],
            template_name=template_name,
        )

        plan = await self.planner.plan(user_message, template_name=template_name)

        logger.info(
            "workflow_plan_created",
            session_id=session_id,
            plan_name=plan.name,
            step_count=len(plan.steps),
            steps=[{"id": s.id, "worker": s.worker, "depends_on": s.depends_on} for s in plan.steps],
        )

        return {"plan": plan, "current_round": 0}

    def _get_steps_for_round(self, plan: WorkflowPlan, round_num: int, completed_ids: set) -> list[WorkflowStep]:
        """Get steps eligible to run in the current round (dependencies satisfied)."""
        eligible = []
        for step in plan.steps:
            if step.id in completed_ids:
                continue
            if all(dep in completed_ids for dep in step.depends_on):
                eligible.append(step)
        return eligible

    def _assign_workers(self, state: WorkflowState) -> list[Send]:
        """Conditional edge: fan-out eligible steps to parallel workers via Send."""
        if not state.plan or not state.plan.steps:
            return [Send("synthesizer", state)]

        completed_ids = {r["step_id"] for r in state.completed_results} if state.completed_results else set()
        eligible_steps = self._get_steps_for_round(state.plan, state.current_round, completed_ids)

        if not eligible_steps:
            # No more steps to run, go to synthesizer
            return [Send("synthesizer", state)]

        # Build context from completed dependency results
        results_by_id = {r["step_id"]: r["output"] for r in state.completed_results} if state.completed_results else {}

        sends = []
        for step in eligible_steps:
            dep_context = ""
            if step.depends_on:
                dep_parts = []
                for dep_id in step.depends_on:
                    if dep_id in results_by_id:
                        dep_parts.append(f"[Result from {dep_id}]:\n{results_by_id[dep_id]}")
                dep_context = "\n\n".join(dep_parts)

            sends.append(
                Send(
                    "worker_task",
                    {
                        "step": step.model_dump(),
                        "messages": state.messages,
                        "completed_results": [],
                        "context_from_deps": dep_context,
                    },
                )
            )

        logger.info(
            "workflow_workers_assigned",
            round=state.current_round,
            worker_count=len(sends),
            workers=[s.worker for s in eligible_steps],
        )

        return sends

    async def _worker_task_node(self, state: WorkerTaskState) -> dict:
        """Worker task node: execute a single step using the assigned worker."""
        step = state.step if isinstance(state.step, WorkflowStep) else WorkflowStep(**state.step)
        worker = WORKER_REGISTRY.get(step.worker)

        if not worker:
            logger.warning("workflow_worker_not_found", worker=step.worker, step_id=step.id)
            return {
                "completed_results": [
                    {
                        "step_id": step.id,
                        "worker": step.worker,
                        "task": step.task,
                        "output": f"Worker '{step.worker}' not found.",
                    }
                ]
            }

        # Build messages for the worker
        task_prompt = step.task
        if state.context_from_deps:
            task_prompt = f"{step.task}\n\n## Context from previous steps\n{state.context_from_deps}"

        # Convert original messages to provide conversation context
        worker_messages = []
        for msg in state.messages:
            if hasattr(msg, "content"):
                role = getattr(msg, "type", "user")
                if role == "human":
                    role = "user"
                elif role == "ai":
                    role = "assistant"
                worker_messages.append(type(msg)(content=msg.content))
            elif isinstance(msg, dict):
                from langchain_core.messages import HumanMessage

                worker_messages.append(HumanMessage(content=msg.get("content", "")))

        # Override last message with the enriched task prompt
        from langchain_core.messages import HumanMessage

        worker_messages = [HumanMessage(content=task_prompt)]

        logger.info(
            "workflow_worker_task_started",
            step_id=step.id,
            worker=step.worker,
            task=step.task[:200],
        )

        try:
            response = await worker.invoke(worker_messages)
            output = response.content if hasattr(response, "content") else str(response)

            logger.info(
                "workflow_worker_task_completed",
                step_id=step.id,
                worker=step.worker,
                output_length=len(output),
            )

            return {
                "completed_results": [
                    {
                        "step_id": step.id,
                        "worker": step.worker,
                        "task": step.task,
                        "output": output,
                    }
                ]
            }
        except Exception as e:
            logger.exception(
                "workflow_worker_task_failed",
                step_id=step.id,
                worker=step.worker,
                error=str(e),
            )
            return {
                "completed_results": [
                    {
                        "step_id": step.id,
                        "worker": step.worker,
                        "task": step.task,
                        "output": f"Worker '{step.worker}' failed: {str(e)}",
                    }
                ]
            }

    async def _check_completion_node(self, state: WorkflowState) -> dict:
        """Check if all plan steps are completed; if not, increment round for next batch."""
        if not state.plan:
            return {}

        completed_ids = {r["step_id"] for r in state.completed_results} if state.completed_results else set()
        all_step_ids = {s.id for s in state.plan.steps}
        remaining = all_step_ids - completed_ids

        if remaining:
            logger.info(
                "workflow_round_completed",
                round=state.current_round,
                completed=list(completed_ids),
                remaining=list(remaining),
            )
            return {"current_round": state.current_round + 1}

        logger.info(
            "workflow_all_steps_completed",
            total_steps=len(all_step_ids),
        )
        return {}

    async def _synthesizer_node(self, state: WorkflowState) -> dict:
        """Synthesizer node: combine all worker results into final output."""
        if not state.completed_results:
            return {
                "final_output": "No results to synthesize.",
                "messages": [AIMessage(content="No results to synthesize.")],
            }

        # Build structured summary
        sections = []
        for result in state.completed_results:
            sections.append(
                f"### Step: {result['step_id']} (Worker: {result['worker']})\n"
                f"**Task**: {result['task'][:200]}\n\n"
                f"{result['output']}"
            )

        combined = "\n\n---\n\n".join(sections)

        plan_name = state.plan.name if state.plan else "unknown"
        step_count = len(state.completed_results)

        final_output = f"# Workflow Results: {plan_name}\n*Completed {step_count} steps*\n\n{combined}"

        logger.info(
            "workflow_synthesis_completed",
            plan_name=plan_name,
            step_count=step_count,
            output_length=len(final_output),
        )

        return {
            "final_output": final_output,
            "messages": [AIMessage(content=final_output)],
        }

    # ─── Graph Builder ─────────────────────────────────────────────

    async def create_graph(self) -> Optional[CompiledStateGraph]:
        """Create and compile the Workflow LangGraph."""
        if self._graph is not None:
            return self._graph

        try:
            builder = StateGraph(WorkflowState)

            # Add nodes
            builder.add_node("planner", self._planner_node)
            builder.add_node("worker_task", self._worker_task_node)
            builder.add_node("check_completion", self._check_completion_node)
            builder.add_node("synthesizer", self._synthesizer_node)

            # Edges
            builder.add_edge(START, "planner")
            builder.add_conditional_edges("planner", self._assign_workers, ["worker_task", "synthesizer"])
            builder.add_edge("worker_task", "check_completion")
            builder.add_conditional_edges(
                "check_completion",
                self._route_after_check,
                ["worker_task", "synthesizer"],
            )
            builder.add_edge("synthesizer", END)

            # Checkpointer
            checkpointer = await self._setup_checkpointer()

            self._graph = builder.compile(
                checkpointer=checkpointer,
                name=f"{settings.PROJECT_NAME} Workflow ({settings.ENVIRONMENT.value})",
            )

            logger.info(
                "workflow_graph_created",
                has_checkpointer=checkpointer is not None,
            )

        except Exception as e:
            logger.exception("workflow_graph_creation_failed", error=str(e))
            if settings.ENVIRONMENT == Environment.PRODUCTION:
                return None
            raise e

        return self._graph

    def _route_after_check(self, state: WorkflowState) -> list[Send] | str:
        """Route after check_completion: fan-out to workers or go to synthesizer."""
        if not state.plan:
            return "synthesizer"

        completed_ids = {r["step_id"] for r in state.completed_results} if state.completed_results else set()
        all_step_ids = {s.id for s in state.plan.steps}

        if completed_ids >= all_step_ids:
            return "synthesizer"

        # Fan-out eligible steps
        return self._assign_workers(state)

    # ─── Public API ────────────────────────────────────────────────

    async def get_response(
        self,
        messages: list[Message],
        session_id: str,
        user_id: Optional[str] = None,
        template_name: Optional[str] = None,
    ) -> list[dict]:
        """Execute a workflow and return the final response.

        Args:
            messages: User messages.
            session_id: Session ID for checkpointing.
            user_id: User ID for tracing.
            template_name: Optional workflow template to use.

        Returns:
            list[dict]: Processed messages with workflow results.
        """
        if self._graph is None:
            self._graph = await self.create_graph()

        config = {
            "configurable": {"thread_id": session_id},
            "callbacks": [CallbackHandler()],
            "metadata": {
                "langfuse_user_id": user_id,
                "langfuse_session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
                "workflow_template": template_name,
            },
        }

        try:
            response = await self._graph.ainvoke(
                input={"messages": dump_messages(messages)},
                config=config,
            )
            return self._process_messages(response["messages"])
        except Exception as e:
            logger.exception("workflow_execution_failed", error=str(e))
            return []

    async def get_stream_response(
        self,
        messages: list[Message],
        session_id: str,
        user_id: Optional[str] = None,
        template_name: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Execute a workflow with streaming response.

        Args:
            messages: User messages.
            session_id: Session ID for checkpointing.
            user_id: User ID for tracing.
            template_name: Optional workflow template to use.

        Yields:
            str: Tokens from the workflow execution.
        """
        if self._graph is None:
            self._graph = await self.create_graph()

        config = {
            "configurable": {"thread_id": session_id},
            "callbacks": [CallbackHandler()],
            "metadata": {
                "langfuse_user_id": user_id,
                "langfuse_session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
                "workflow_template": template_name,
            },
        }

        try:
            async for token, _ in self._graph.astream(
                {"messages": dump_messages(messages)},
                config,
                stream_mode="messages",
            ):
                try:
                    if hasattr(token, "content") and token.content:
                        yield token.content
                except Exception as token_error:
                    logger.error(
                        "workflow_stream_token_error",
                        error=str(token_error),
                        session_id=session_id,
                    )
                    continue
        except Exception as e:
            logger.exception("workflow_stream_failed", error=str(e))
            raise
