"""YAML workflow template loader and registry.

Similar to the Skills system, this module scans YAML files from the templates/
directory and makes them available for the WorkflowPlanner to match against
user requests.
"""

import os
from typing import (
    Dict,
    List,
    Optional,
)

import yaml

from app.core.langgraph.workflow.schema import (
    WorkflowPlan,
    WorkflowStep,
)
from app.core.logging import logger


class WorkflowTemplateRegistry:
    """Registry for YAML-defined workflow templates.

    Scans the templates/ directory at initialization and provides
    lookup by name and listing for the Planner's prompt.
    """

    def __init__(self):
        """Initialize and load all workflow templates from the templates/ directory."""
        self._templates: Dict[str, WorkflowPlan] = {}
        self._descriptions: Dict[str, str] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Scan the templates/ directory and parse all .yaml files."""
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        if not os.path.isdir(templates_dir):
            logger.warning("workflow_templates_dir_not_found", path=templates_dir)
            return

        for filename in sorted(os.listdir(templates_dir)):
            if not filename.endswith((".yaml", ".yml")):
                continue

            filepath = os.path.join(templates_dir, filename)
            try:
                plan = self._parse_template(filepath)
                if plan:
                    self._templates[plan.name] = plan
                    logger.info(
                        "workflow_template_loaded",
                        template_name=plan.name,
                        step_count=len(plan.steps),
                    )
            except Exception as e:
                logger.exception("workflow_template_parse_failed", file=filename, error=str(e))

    def _parse_template(self, filepath: str) -> Optional[WorkflowPlan]:
        """Parse a single YAML template file into a WorkflowPlan."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or "name" not in data or "steps" not in data:
            return None

        steps = []
        for step_data in data["steps"]:
            steps.append(
                WorkflowStep(
                    id=step_data["id"],
                    worker=step_data["worker"],
                    task=step_data["task"],
                    depends_on=step_data.get("depends_on", []),
                )
            )

        self._descriptions[data["name"]] = data.get("description", "")

        return WorkflowPlan(
            name=data["name"],
            steps=steps,
            reasoning=f"Loaded from template: {os.path.basename(filepath)}",
        )

    def get(self, name: str) -> Optional[WorkflowPlan]:
        """Get a workflow template by name."""
        return self._templates.get(name)

    def list_templates(self) -> List[Dict[str, str]]:
        """List all available templates with their descriptions."""
        return [
            {"name": name, "description": self._descriptions.get(name, "")}
            for name in self._templates
        ]

    def get_templates_prompt(self) -> str:
        """Generate a prompt section describing all available templates for the Planner."""
        if not self._templates:
            return "No predefined workflow templates available."

        lines = ["## Available Workflow Templates"]
        for name, plan in self._templates.items():
            desc = self._descriptions.get(name, "")
            worker_sequence = " → ".join(f"{s.worker}({s.id})" for s in plan.steps)
            lines.append(f"- **{name}**: {desc}")
            lines.append(f"  Flow: {worker_sequence}")
        return "\n".join(lines)


# Global singleton
workflow_template_registry = WorkflowTemplateRegistry()
