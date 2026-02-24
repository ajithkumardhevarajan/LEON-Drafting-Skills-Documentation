"""
Tool Registry

This module registers all available MCP tools for the text archive skill.
"""

from .base import ToolRegistry
from .archive_search import ArchiveSearchTool

# Create global registry instance
tool_registry = ToolRegistry()

# Register all tools
tool_registry.register(ArchiveSearchTool())

# Export registry
__all__ = ["tool_registry"]
