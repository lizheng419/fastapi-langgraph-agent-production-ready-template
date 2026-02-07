"""Unit tests for the Workflow template registry and schema."""

import os
import tempfile

import pytest
import yaml

from app.core.langgraph.workflow.schema import (
    WorkflowPlan,
    WorkflowStep,
)


class TestWorkflowStep:
    """Tests for WorkflowStep Pydantic model."""

    def test_create_step(self):
        """Test creating a basic workflow step."""
        step = WorkflowStep(
            id="step_1",
            worker="researcher",
            task="Research the topic",
            depends_on=[],
        )
        assert step.id == "step_1"
        assert step.worker == "researcher"
        assert step.task == "Research the topic"
        assert step.depends_on == []

    def test_step_with_dependencies(self):
        """Test creating a step with dependencies."""
        step = WorkflowStep(
            id="step_2",
            worker="coder",
            task="Implement solution",
            depends_on=["step_1"],
        )
        assert step.depends_on == ["step_1"]

    def test_step_default_depends_on(self):
        """Test that depends_on defaults to empty list."""
        step = WorkflowStep(id="s1", worker="coder", task="Code")
        assert step.depends_on == []


class TestWorkflowPlan:
    """Tests for WorkflowPlan Pydantic model."""

    def test_create_plan(self):
        """Test creating a workflow plan with multiple steps."""
        steps = [
            WorkflowStep(id="step_1", worker="researcher", task="Research"),
            WorkflowStep(id="step_2", worker="coder", task="Code", depends_on=["step_1"]),
        ]
        plan = WorkflowPlan(name="test_plan", steps=steps, reasoning="Test")
        assert plan.name == "test_plan"
        assert len(plan.steps) == 2
        assert plan.reasoning == "Test"

    def test_plan_defaults(self):
        """Test that plan has sensible defaults."""
        plan = WorkflowPlan()
        assert plan.name == "dynamic"
        assert plan.steps == []
        assert plan.reasoning == ""


class TestWorkflowTemplateRegistry:
    """Tests for YAML template loading and registry lookup."""

    def _create_temp_template(self, tmp_path, filename, content):
        """Helper to create a temporary YAML template file."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(exist_ok=True)
        filepath = templates_dir / filename
        filepath.write_text(yaml.dump(content), encoding="utf-8")
        return str(templates_dir)

    def test_parse_valid_yaml_template(self, tmp_path):
        """Test parsing a valid YAML workflow template."""
        from app.core.langgraph.workflow.templates import WorkflowTemplateRegistry

        template_data = {
            "name": "test_workflow",
            "description": "A test workflow",
            "steps": [
                {"id": "step_1", "worker": "researcher", "task": "Research", "depends_on": []},
                {"id": "step_2", "worker": "coder", "task": "Code", "depends_on": ["step_1"]},
            ],
        }
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        filepath = templates_dir / "test.yaml"
        filepath.write_text(yaml.dump(template_data), encoding="utf-8")

        registry = WorkflowTemplateRegistry.__new__(WorkflowTemplateRegistry)
        registry._templates = {}
        registry._descriptions = {}

        plan = registry._parse_template(str(filepath))
        assert plan is not None
        assert plan.name == "test_workflow"
        assert len(plan.steps) == 2
        assert plan.steps[0].worker == "researcher"
        assert plan.steps[1].depends_on == ["step_1"]

    def test_parse_invalid_yaml_returns_none(self, tmp_path):
        """Test that YAML without required fields returns None."""
        from app.core.langgraph.workflow.templates import WorkflowTemplateRegistry

        template_data = {"description": "Missing name and steps"}
        filepath = tmp_path / "invalid.yaml"
        filepath.write_text(yaml.dump(template_data), encoding="utf-8")

        registry = WorkflowTemplateRegistry.__new__(WorkflowTemplateRegistry)
        registry._templates = {}
        registry._descriptions = {}

        plan = registry._parse_template(str(filepath))
        assert plan is None

    def test_list_templates(self):
        """Test listing templates from the global registry."""
        from app.core.langgraph.workflow.templates import workflow_template_registry

        templates = workflow_template_registry.list_templates()
        assert isinstance(templates, list)
        for t in templates:
            assert "name" in t
            assert "description" in t

    def test_get_templates_prompt(self):
        """Test generating prompt text from templates."""
        from app.core.langgraph.workflow.templates import workflow_template_registry

        prompt = workflow_template_registry.get_templates_prompt()
        assert isinstance(prompt, str)
        # Should either list templates or say none available
        assert "template" in prompt.lower() or "Template" in prompt
