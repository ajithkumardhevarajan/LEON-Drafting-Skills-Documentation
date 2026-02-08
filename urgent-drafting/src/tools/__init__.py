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
from .generate_urgent_draft import GenerateUrgentDraftTool

# Initialize the global tool registry
tool_registry = ToolRegistry()

# Register the urgent draft generation tool
tool_registry.register(GenerateUrgentDraftTool())

# Export for use by main.py
__all__ = [
    "BaseTool",
    "ToolRegistry",
    "tool_registry",
    "GenerateUrgentDraftTool"
]
