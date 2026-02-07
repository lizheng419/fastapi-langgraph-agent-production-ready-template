"""Workflow Planner that generates multi-step execution plans.

The Planner first tries to match user requests against predefined YAML templates.
If no template matches, it uses the LLM to dynamically generate a multi-step plan
with worker assignments and dependency ordering.
"""

import json
from typing import Optional

from app.core.langgraph.agents.workers import WORKER_REGISTRY
from app.core.langgraph.workflow.schema import (
    WorkflowPlan,
    WorkflowStep,
)
from app.core.langgraph.workflow.templates import workflow_template_registry
from app.core.logging import logger
from app.services.llm import llm_service


class WorkflowPlanner:
    """Plans multi-step workflows by matching templates or LLM dynamic generation.

    Priority order:
    1. Match a predefined YAML template by name (if user specifies)
    2. LLM analyzes user request and generates a dynamic multi-step plan
    """

    def __init__(self):
        """Initialize the WorkflowPlanner."""
        self.llm_service = llm_service
        self._build_planning_prompt()

    def _build_planning_prompt(self) -> None:
        """Build the system prompt for LLM-based dynamic planning."""
        worker_descriptions = "\n".join(
            f"- **{w.name}**: {w.description}" for w in WORKER_REGISTRY.values()
        )
        templates_prompt = workflow_template_registry.get_templates_prompt()

        self._planning_prompt = (
            "You are a Workflow Planner. Your job is to break down a user's complex request "
            "into a multi-step execution plan, assigning each step to the most appropriate worker.\n\n"
            "## Available Workers\n"
            f"{worker_descriptions}\n\n"
            f"{templates_prompt}\n\n"
            "## Instructions\n"
            "1. Analyze the user's request carefully.\n"
            "2. If the request matches one of the available templates, use that template name.\n"
            "3. Otherwise, create a dynamic multi-step plan.\n"
            "4. Each step must specify: id, worker, task description, and dependencies.\n"
            "5. Steps without dependencies can run in parallel.\n"
            "6. Steps with depends_on will run after those dependencies complete.\n"
            "7. Use 2-5 steps. Keep each step focused on one clear task.\n\n"
            "## Output Format\n"
            "Respond with ONLY a JSON object:\n"
            "```json\n"
            "{\n"
            '  "name": "workflow_name",\n'
            '  "reasoning": "brief explanation",\n'
            '  "steps": [\n'
            '    {"id": "step_1", "worker": "researcher", "task": "...", "depends_on": []},\n'
            '    {"id": "step_2", "worker": "coder", "task": "...", "depends_on": ["step_1"]}\n'
            "  ]\n"
            "}\n"
            "```\n\n"
            "Valid worker names: " + ", ".join(list(WORKER_REGISTRY.keys()))
        )

    async def plan(self, user_message: str, template_name: Optional[str] = None) -> WorkflowPlan:
        """Generate a workflow plan for the user's request.

        Args:
            user_message: The user's request text.
            template_name: Optional template name to use directly.

        Returns:
            WorkflowPlan: The generated or template-matched plan.
        """
        # Priority 1: Explicit template match
        if template_name:
            template = workflow_template_registry.get(template_name)
            if template:
                logger.info(
                    "workflow_template_matched",
                    template_name=template_name,
                    step_count=len(template.steps),
                )
                return self._inject_user_context(template, user_message)

        # Priority 2: LLM dynamic planning
        return await self._llm_plan(user_message)

    def _inject_user_context(self, plan: WorkflowPlan, user_message: str) -> WorkflowPlan:
        """Inject user's specific request context into template step tasks."""
        enriched_steps = []
        for step in plan.steps:
            enriched_steps.append(
                WorkflowStep(
                    id=step.id,
                    worker=step.worker,
                    task=f"{step.task}\n\nUser's original request: {user_message}",
                    depends_on=step.depends_on,
                )
            )
        return WorkflowPlan(
            name=plan.name,
            steps=enriched_steps,
            reasoning=plan.reasoning,
        )

    async def _llm_plan(self, user_message: str) -> WorkflowPlan:
        """Use LLM to dynamically generate a multi-step workflow plan."""
        planning_messages = [
            {"role": "system", "content": self._planning_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await self.llm_service.call(planning_messages)
            content = response.content if hasattr(response, "content") else str(response)

            plan_data = self._parse_plan_json(content)

            steps = []
            for step_data in plan_data.get("steps", []):
                worker = step_data.get("worker", "")
                if worker not in WORKER_REGISTRY:
                    logger.warning(
                        "workflow_planner_invalid_worker",
                        worker=worker,
                        available=list(WORKER_REGISTRY.keys()),
                    )
                    continue
                steps.append(
                    WorkflowStep(
                        id=step_data.get("id", f"step_{len(steps) + 1}"),
                        worker=worker,
                        task=step_data.get("task", ""),
                        depends_on=step_data.get("depends_on", []),
                    )
                )

            plan = WorkflowPlan(
                name=plan_data.get("name", "dynamic"),
                steps=steps,
                reasoning=plan_data.get("reasoning", "LLM-generated plan"),
            )

            logger.info(
                "workflow_plan_generated",
                plan_name=plan.name,
                step_count=len(plan.steps),
                workers=[s.worker for s in plan.steps],
                reasoning=plan.reasoning,
            )
            return plan

        except Exception as e:
            logger.exception("workflow_planning_failed", error=str(e))
            # Fallback: single-step plan using coder
            return WorkflowPlan(
                name="fallback",
                steps=[
                    WorkflowStep(
                        id="step_1",
                        worker="coder",
                        task=user_message,
                        depends_on=[],
                    )
                ],
                reasoning=f"Planning failed ({str(e)}), falling back to single coder worker.",
            )

    def _parse_plan_json(self, content: str) -> dict:
        """Extract and parse JSON from LLM response, handling markdown code blocks."""
        try:
            if "```" in content:
                json_str = content.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                json_str = json_str.strip()
            else:
                json_str = content.strip()

            return json.loads(json_str)
        except (json.JSONDecodeError, IndexError) as e:
            logger.warning("workflow_plan_json_parse_failed", error=str(e), content=content[:300])
            raise ValueError(f"Failed to parse plan JSON: {e}") from e
