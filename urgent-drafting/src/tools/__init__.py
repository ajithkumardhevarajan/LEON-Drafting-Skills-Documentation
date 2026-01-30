"""
Tool Registry Initialization

This module initializes the tool registry and registers all available tools.

To add a new tool:
1. Create a new file in this directory (e.g., my_tool.py)
2. Implement a class that inherits from BaseTool
3. Import it here
4. Register it with tool_registry.register()
"""

from .base import BaseTool, ToolRegistry
from .urgent_draft_tool import UrgentDraftTool

# Initialize the global tool registry
tool_registry = ToolRegistry()

# Register all available tools
tool_registry.register(UrgentDraftTool())

# Export for use by main.py
__all__ = ["BaseTool", "ToolRegistry", "tool_registry", "UrgentDraftTool"]
