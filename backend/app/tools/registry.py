from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

from app.core.logging import get_logger
from app.tools.base import BaseTool

logger = get_logger("tools.registry")


class ToolRegistry:
    """
    Domain-aware tool registry.

    Discovers and registers all tool implementations at startup by scanning
    the tools/core/ and tools/<domain>/ directories. Tools self-declare which
    domains they support via the `domains` class attribute.

    Usage:
        registry = ToolRegistry()
        registry.discover_and_register()
        tool = registry.get_tool("file_claim", domain="insurance")
        result = await tool.execute(input_data)
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}  # name -> tool instance

    @property
    def count(self) -> int:
        return len(self._tools)

    def discover_and_register(self) -> None:
        """
        Auto-discover all BaseTool subclasses in tools/core/ and tools/<domain>/ packages.

        Walks the tools package tree, imports each module, and registers any
        BaseTool subclass found (that has a concrete name attribute).
        """
        import app.tools.core as core_pkg
        self._scan_package(core_pkg)

        # Scan domain-specific tool packages
        import app.tools as tools_root_pkg

        tools_path = tools_root_pkg.__path__
        tools_prefix = tools_root_pkg.__name__ + "."

        for importer, modname, ispkg in pkgutil.walk_packages(
            path=tools_path, prefix=tools_prefix, onerror=lambda e: None
        ):
            if ispkg and modname not in (
                "app.tools.core",
                "app.tools",
            ):
                # Domain tool sub-package
                try:
                    pkg = importlib.import_module(modname)
                    self._scan_package(pkg)
                except Exception as e:
                    logger.warning(
                        "Failed to import tool package",
                        node="tools.registry",
                        package=modname,
                        error=str(e),
                    )

        logger.info(
            "Tool registry populated",
            node="tools.registry",
            tools=list(self._tools.keys()),
        )

    def _scan_package(self, pkg) -> None:
        """Scan a package for BaseTool subclasses and register them."""
        if not hasattr(pkg, "__path__"):
            return

        for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
            full_modname = f"{pkg.__name__}.{modname}"
            try:
                module = importlib.import_module(full_modname)
                self._register_from_module(module)
            except Exception as e:
                logger.warning(
                    "Failed to import tool module",
                    node="tools.registry",
                    module=full_modname,
                    error=str(e),
                )

    def _register_from_module(self, module) -> None:
        """Find and register all BaseTool subclasses in a module."""
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseTool)
                and obj is not BaseTool
                and hasattr(obj, "name")
                and obj.name
            ):
                instance = obj()
                self._tools[instance.name] = instance
                logger.debug(
                    "Tool registered",
                    node="tools.registry",
                    tool_name=instance.name,
                    domains=getattr(instance, "domains", []),
                )

    def register(self, tool: BaseTool) -> None:
        """Manually register a tool instance."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str, domain: str | None = None) -> BaseTool | None:
        """
        Get a tool by name, optionally validating domain access.

        Args:
            name: Tool registry key.
            domain: If provided, checks that the tool supports this domain.

        Returns:
            Tool instance, or None if not found or domain not allowed.
        """
        tool = self._tools.get(name)
        if tool is None:
            return None

        if domain is not None:
            tool_domains = getattr(tool, "domains", ["*"])
            if "*" not in tool_domains and domain not in tool_domains:
                logger.warning(
                    "Tool not available for domain",
                    node="tools.registry",
                    tool_name=name,
                    domain=domain,
                    tool_domains=tool_domains,
                )
                return None

        return tool

    def get_tools_for_domain(self, domain: str) -> list[BaseTool]:
        """Get all tools available for a given domain."""
        result = []
        for tool in self._tools.values():
            tool_domains = getattr(tool, "domains", ["*"])
            if "*" in tool_domains or domain in tool_domains:
                result.append(tool)
        return result

    def get_manifest(self, domain: str, enabled_tools: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Get the LLM tool manifest for a domain.

        Args:
            domain: Domain to scope the manifest to.
            enabled_tools: Optional allowlist of tool names from domain.yaml.

        Returns:
            List of tool manifest dicts for inclusion in LLM system prompt.
        """
        tools = self.get_tools_for_domain(domain)
        if enabled_tools:
            tools = [t for t in tools if t.name in enabled_tools]
        return [t.to_manifest_entry() for t in tools]

    def all_names(self) -> list[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())
