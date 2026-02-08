"""
MCP Protocol Models

This module defines all Pydantic models required for the Model Context Protocol (MCP).
These models handle JSON-RPC 2.0 communication between the backend and this MCP server.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# ============================================================================
# JSON-RPC 2.0 Base Models
# ============================================================================

class MCPRequest(BaseModel):
    """Base JSON-RPC 2.0 request"""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPError(BaseModel):
    """JSON-RPC 2.0 error structure"""
    code: int
    message: str
    data: Optional[Any] = None


class MCPResponse(BaseModel):
    """Base JSON-RPC 2.0 response"""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    result: Optional[Any] = None
    error: Optional[MCPError] = None


# ============================================================================
# MCP Initialize Protocol
# ============================================================================

class ServerInfo(BaseModel):
    """Information about this MCP server"""
    name: str
    version: str


class ServerCapabilities(BaseModel):
    """Capabilities advertised by this server"""
    tools: Optional[Dict[str, Any]] = Field(default_factory=dict)
    resources: Optional[Dict[str, Any]] = Field(default_factory=dict)
    prompts: Optional[Dict[str, Any]] = Field(default_factory=dict)


class InitializeRequest(BaseModel):
    """Initialize handshake request"""
    protocolVersion: str
    capabilities: Dict[str, Any]
    clientInfo: Dict[str, str]


class InitializeResponse(BaseModel):
    """Initialize handshake response"""
    protocolVersion: str
    capabilities: ServerCapabilities
    serverInfo: ServerInfo


# ============================================================================
# Tool Models
# ============================================================================

class ToolParameter(BaseModel):
    """Schema for a tool parameter"""
    type: str  # "string", "number", "integer", "boolean", "array", "object"
    description: str
    enum: Optional[List[Any]] = None
    default: Optional[Any] = None
    required: Optional[bool] = None
    items: Optional[Dict[str, Any]] = None  # For array types
    properties: Optional[Dict[str, Any]] = None  # For object types
    ui_metadata: Optional[Dict[str, Any]] = None  # UI hints for parameter prompting


class Tool(BaseModel):
    """Tool definition in MCP format"""
    name: str
    description: str
    parameters: Dict[str, ToolParameter]
    response_mode: Optional[str] = None  # "direct", "enhanced", or None
    preferred_model: Optional[str] = None  # e.g., "gpt-4o", "claude-3-5-sonnet"
    orchestration_hints: Optional[Dict[str, Any]] = None  # Fast-path routing hints

    def to_mcp_schema(self) -> Dict[str, Any]:
        """
        Convert tool definition to MCP JSON Schema format.

        Returns a dictionary with the tool schema in the format expected by MCP:
        - name: Tool identifier
        - description: What the tool does
        - inputSchema: JSON Schema for parameters
        - Meta fields: response_mode, preferred_model, orchestration_hints
        """
        # Extract required parameters
        required_params = [
            param_name
            for param_name, param_def in self.parameters.items()
            if param_def.required
        ]

        # Build JSON Schema properties
        properties = {}
        for param_name, param_def in self.parameters.items():
            prop = {
                "type": param_def.type,
                "description": param_def.description,
            }
            if param_def.enum:
                prop["enum"] = param_def.enum
            if param_def.default is not None:
                prop["default"] = param_def.default
            if param_def.items:
                prop["items"] = param_def.items
            if param_def.properties:
                prop["properties"] = param_def.properties
            if param_def.ui_metadata:
                prop["ui_metadata"] = param_def.ui_metadata

            properties[param_name] = prop

        # Build MCP schema
        schema = {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
            },
        }

        # Add required parameters if any
        if required_params:
            schema["inputSchema"]["required"] = required_params

        # Add meta fields for backend orchestration
        if self.response_mode:
            schema["response_mode"] = self.response_mode
        if self.preferred_model:
            schema["preferred_model"] = self.preferred_model
        if self.orchestration_hints:
            schema["orchestration_hints"] = self.orchestration_hints

        return schema


class ToolCall(BaseModel):
    """Request to invoke a tool"""
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Result from tool execution"""
    content: List[Dict[str, Any]]  # Array of {type: "text", text: "..."} or {type: "image", data: "..."}
    isError: bool = False


# ============================================================================
# Health Check Models
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    uptime_seconds: float
    server_name: str
    version: str


# ============================================================================
# Asset Models for Urgent Drafting
# ============================================================================

class Asset(BaseModel):
    """News asset from Reuters API"""
    id: str
    headline: str
    body: Optional[str] = None
    modified_at: Optional[str] = None
    usn: Optional[str] = None


class SelectableAsset(Asset):
    """Asset with selection state for urgent builder"""
    included: bool = True  # CRITICAL: Default is True - all assets start included
