"""
Tool Registry

This module registers all available MCP tools for the spot story skill.
"""

from .base import ToolRegistry
from .generate_spot_story import GenerateSpotStoryTool
from .update_spot_story import UpdateSpotStoryTool

# Create global registry instance
tool_registry = ToolRegistry()

# Register all tools
tool_registry.register(GenerateSpotStoryTool())
tool_registry.register(UpdateSpotStoryTool())

# Export registry
__all__ = ["tool_registry"]
