"""Workflow orchestration engine with Orchestrator-Worker pattern.

This package implements freely composable multi-step workflows using LangGraph's
Send API for parallel fan-out and dynamic worker assignment.

Key components:
- WorkflowPlanner: LLM-driven or YAML-template-based step planning
- WorkflowGraph: LangGraph StateGraph with Send-based parallel execution
- WorkflowTemplateRegistry: YAML workflow template management
"""

from app.core.langgraph.workflow.graph import WorkflowGraph
from app.core.langgraph.workflow.planner import WorkflowPlanner
from app.core.langgraph.workflow.schema import (
    WorkerResult,
    WorkerTaskState,
    WorkflowPlan,
    WorkflowState,
    WorkflowStep,
)
from app.core.langgraph.workflow.templates import WorkflowTemplateRegistry

__all__ = [
    "WorkflowGraph",
    "WorkflowPlanner",
    "WorkerResult",
    "WorkerTaskState",
    "WorkflowPlan",
    "WorkflowState",
    "WorkflowStep",
    "WorkflowTemplateRegistry",
]
