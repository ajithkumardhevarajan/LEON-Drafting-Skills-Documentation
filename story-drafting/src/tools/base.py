"""
Base Tool Classes

This module provides the abstract base class and registry for MCP tools.
All tools must inherit from BaseTool and implement the required methods.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ..models import Tool, ToolParameter, ToolResult


class BaseTool(ABC):
    """
    Abstract base class for all MCP tools.

    To create a new tool:
    1. Inherit from BaseTool
    2. Implement all @property methods (name, description, parameters)
    3. Implement the execute() method with your business logic
    4. Register the tool in tools/__init__.py
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique identifier for this tool.
        Use lowercase with underscores (e.g., 'get_example_data')
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Human-readable description of what this tool does.
        The LLM uses this to decide when to invoke the tool.
        """
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """
        Parameter definitions for this tool.

        Return a dictionary where keys are parameter names and values
        contain the parameter schema.

        Example:
        {
            "category": {
                "type": "string",
                "description": "Category of data to retrieve",
                "enum": ["news", "sports", "tech"],
                "required": True
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results",
                "default": 10,
                "required": False
            }
        }
        """
        pass

    @property
    def response_mode(self) -> str:
        """
        How the backend should handle the tool's response.

        Options:
        - None (default): Backend decides how to handle the response
        - "direct": Return the tool's result directly to the user
        - "enhanced": Send the tool's output back to LLM for processing

        Override this method if you need specific response handling.
        """
        return None

    @property
    def preferred_model(self) -> str:
        """
        Preferred LLM model for this tool (optional).

        Examples: "gpt-4o", "claude-3-5-sonnet", "gemini-2-5-flash"

        Override this if your tool requires a specific model.
        """
        return None

    @property
    def orchestration_hints(self) -> Dict[str, Any]:
        """
        Hints for fast-path orchestration (optional).

        Allows pattern-based routing to bypass LLM orchestration for
        performance. Useful for high-frequency, predictable queries.

        Example:
        {
            "enabled": True,
            "priority": 10,
            "query_patterns": [r"get\s+data", r"retrieve\s+info"],
            "parameter_extractions": [
                {
                    "parameter_name": "query",
                    "fallback": "user_query",
                    "required": True
                }
            ]
        }
        """
        return None

    @abstractmethod
    async def execute(
        self, arguments: Dict[str, Any], jwt_token: str
    ) -> ToolResult:
        """
        Execute the tool's logic.

        Args:
            arguments: Dictionary of parameter values passed by the backend
            jwt_token: JWT token for authentication (if needed for API calls)

        Returns:
            ToolResult with content array and error flag

        Example:
        return ToolResult(
            content=[{"type": "text", "text": "Result data here"}],
            isError=False
        )

        For errors:
        return ToolResult(
            content=[{"type": "text", "text": "Error message"}],
            isError=True
        )
        """
        pass

    def to_tool_definition(self) -> Tool:
        """
        Convert this tool instance to a Tool model.
        Called by the registry when listing tools to the backend.
        """
        # Convert parameters dict to ToolParameter models
        tool_parameters = {}
        for param_name, param_def in self.parameters.items():
            tool_parameters[param_name] = ToolParameter(**param_def)

        return Tool(
            name=self.name,
            description=self.description,
            parameters=tool_parameters,
            response_mode=self.response_mode,
            preferred_model=self.preferred_model,
            orchestration_hints=self.orchestration_hints,
        )


class ToolRegistry:
    """
    Registry for managing MCP tools.

    The registry:
    - Stores all available tools
    - Provides tool lookup by name
    - Lists tools for MCP protocol
    - Executes tools with proper error handling
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """
        Register a tool instance.

        Args:
            tool: BaseTool instance to register

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool:
        """
        Get a tool by name.

        Args:
            name: Tool identifier

        Returns:
            BaseTool instance

        Raises:
            ValueError: If tool is not found
        """
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found in registry")
        return self._tools[name]

    def list_tools(self) -> List[Tool]:
        """
        Get all registered tools as Tool models.

        Returns:
            List of Tool definitions for MCP protocol
        """
        return [tool.to_tool_definition() for tool in self._tools.values()]

    async def execute_tool(
        self, name: str, arguments: Dict[str, Any], jwt_token: str
    ) -> ToolResult:
        """
        Execute a tool by name.

        Args:
            name: Tool identifier
            arguments: Parameter values
            jwt_token: JWT token for authentication

        Returns:
            ToolResult from the tool execution

        Raises:
            ValueError: If tool is not found
        """
        tool = self.get_tool(name)
        return await tool.execute(arguments, jwt_token)
