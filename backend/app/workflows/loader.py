"""
loader.py — Workflow YAML parser.
Loads a workflow definition from YAML and returns a typed WorkflowDefinition.
New business process = new YAML file. No code change required.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import yaml

WORKFLOWS_DIR = os.path.join(os.path.dirname(__file__))


@dataclass
class StepDefinition:
    """A single step in a workflow graph."""
    goal: str
    tool: Optional[str] = None
    action: Optional[str] = None
    on_success: Optional[str] = None
    on_fail: Optional[str] = None
    on_exhausted: Optional[str] = None
    max_attempts: int = 1
    branch: dict[str, str] = field(default_factory=dict)
    terminal: bool = False
    generate_summary: bool = False
    policy_gated: bool = False
    rag_query_template: Optional[str] = None
    rag_top_k: int = 3
    tool_args_override: dict = field(default_factory=dict)


@dataclass
class WorkflowDefinition:
    """A complete workflow with all its steps."""
    name: str
    description: str
    entry_step: str
    steps: dict[str, StepDefinition]

    def get_step(self, step_id: str) -> Optional[StepDefinition]:
        return self.steps.get(step_id)


@lru_cache(maxsize=10)
def load_workflow(name: str) -> WorkflowDefinition:
    """
    Load a workflow definition from YAML by name.
    Results are cached after first load.

    Args:
        name: Workflow name (e.g. "technical_support")

    Returns:
        WorkflowDefinition instance

    Raises:
        FileNotFoundError: If the workflow YAML does not exist.
    """
    yaml_path = os.path.join(WORKFLOWS_DIR, f"{name}.yaml")
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"Workflow '{name}' not found at {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    steps: dict[str, StepDefinition] = {}
    for step_id, step_data in raw.get("steps", {}).items():
        steps[step_id] = StepDefinition(
            goal=step_data.get("goal", ""),
            tool=step_data.get("tool"),
            action=step_data.get("action"),
            on_success=step_data.get("on_success"),
            on_fail=step_data.get("on_fail"),
            on_exhausted=step_data.get("on_exhausted"),
            max_attempts=step_data.get("max_attempts", 1),
            branch=step_data.get("branch", {}),
            terminal=step_data.get("terminal", False),
            generate_summary=step_data.get("generate_summary", False),
            policy_gated=step_data.get("policy_gated", False),
            rag_query_template=step_data.get("rag_query_template"),
            rag_top_k=step_data.get("rag_top_k", 3),
            tool_args_override=step_data.get("tool_args_override", {}),
        )

    return WorkflowDefinition(
        name=raw["name"],
        description=raw.get("description", ""),
        entry_step=raw["entry_step"],
        steps=steps,
    )


def list_workflows() -> list[str]:
    """Return names of all available workflow YAML files."""
    return [
        f.replace(".yaml", "")
        for f in os.listdir(WORKFLOWS_DIR)
        if f.endswith(".yaml")
    ]
