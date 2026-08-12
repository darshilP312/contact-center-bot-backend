from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Type

from pydantic import BaseModel


class BaseTool(ABC):
    """
    Abstract base class for all enterprise tools.

    Every tool must:
    1. Declare its name (registry key), description (for LLM manifest),
       and domains (which domain plugins can use it).
    2. Implement async execute() with typed Pydantic input/output.
    3. Be deterministic: same input → same output (for mock implementations).
    4. Include a # TODO: Replace with {SystemName} API call comment.

    Tools are discovered and registered automatically by ToolRegistry at startup.
    """

    name: str                           # snake_case registry key
    description: str                    # Used in LLM tool manifest
    domains: list[str]                  # ["insurance"] or ["*"] for all domains
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]

    @abstractmethod
    async def execute(self, input_data: BaseModel) -> BaseModel:
        """
        Execute the tool with the given input.

        All implementations must be deterministic (mock) or real API calls.
        Mock implementations must use hashlib.md5 seeding for determinism.
        """
        ...

    def to_manifest_entry(self) -> dict[str, Any]:
        """
        Return LLM-facing tool manifest entry.

        Used by the planner node to build the tool list in the system prompt.
        """
        schema = self.input_schema.model_json_schema()
        return {
            "name": self.name,
            "description": self.description,
            "parameters": schema,
        }
