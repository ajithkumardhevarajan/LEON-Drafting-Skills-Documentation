"""
Story Drafting MCP Server

This is the main FastAPI server implementing the Model Context Protocol (MCP)
for story drafting capabilities. It handles JSON-RPC 2.0 requests from the
backend and routes them to appropriate handlers.

Key endpoints:
- POST /       - MCP JSON-RPC endpoint (initialize, tools/list, tools/call, etc.)
- GET /health  - Health check endpoint
- GET /ready   - Readiness check endpoint
"""

import logging
import os
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import uvicorn
from pathlib import Path

from .models import (
    HealthResponse,
    InitializeResponse,
    MCPError,
    ServerCapabilities,
    ServerInfo,
)
from .tools import tool_registry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class StoryDraftingMCPServer:
    """
    MCP Server implementing the Model Context Protocol over HTTP.

    This server:
    - Handles MCP JSON-RPC 2.0 protocol
    - Provides story drafting tools
    - Includes health check endpoints
    - Supports CORS for cross-origin requests
    """

    def __init__(self):
        self.app = FastAPI(
            title="Story Drafting MCP Server",
            description="Model Context Protocol server for story drafting capabilities",
            version="0.1.0",
        )
        self.start_time = time.time()
        self.initialized = False

        self._setup_middleware()
        self._setup_routes()

        logger.info("Story Drafting MCP Server initialized")

    def _setup_middleware(self):
        """Configure CORS middleware for cross-origin requests."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self):
        """Set up all HTTP routes."""

        @self.app.post("/")
        async def mcp_handler(request: Request) -> JSONResponse:
            """
            Main MCP JSON-RPC 2.0 endpoint.

            Handles all MCP protocol methods:
            - initialize: Handshake and capability exchange
            - tools/list: List available tools
            - tools/call: Execute a tool
            - resources/list: List available resources (not implemented)
            - prompts/list: List available prompts (not implemented)
            """
            try:
                body = await request.json()
                logger.info(f"Received MCP request: {body.get('method')}")

                # Extract JSON-RPC fields
                request_id = body.get("id")
                method = body.get("method")
                params = body.get("params", {})

                # Extract headers for JWT token
                headers = dict(request.headers)

                # Route to appropriate handler
                if method == "initialize":
                    return await self._handle_initialize(request_id, params)
                elif method == "tools/list":
                    return await self._handle_list_tools(request_id, params)
                elif method == "tools/call":
                    return await self._handle_call_tool(
                        request_id, params, headers
                    )
                elif method == "resources/list":
                    return await self._handle_list_resources(request_id, params)
                elif method == "prompts/list":
                    return await self._handle_list_prompts(request_id, params)
                else:
                    logger.warning(f"Unknown method: {method}")
                    return self._error_response(
                        request_id, -32601, f"Method not found: {method}"
                    )

            except Exception as e:
                logger.error(f"Error handling MCP request: {str(e)}", exc_info=True)
                return self._error_response(
                    None, -32603, f"Internal error: {str(e)}"
                )

        @self.app.get("/health")
        async def health_check() -> JSONResponse:
            """
            Health check endpoint.

            Returns server status and uptime.
            """
            uptime = time.time() - self.start_time
            health = HealthResponse(
                status="healthy",
                uptime_seconds=uptime,
                server_name="Story Drafting MCP",
                version="0.1.0",
            )
            return JSONResponse(content=health.model_dump())

        @self.app.get("/ready")
        async def readiness_check() -> JSONResponse:
            """
            Readiness check endpoint.

            Returns whether the server is ready to accept requests.
            """
            return JSONResponse(
                content={"status": "ready", "initialized": self.initialized}
            )

        @self.app.get("/skills")
        async def skills_documentation() -> FileResponse:
            """
            Skills documentation endpoint.

            Returns the interactive skills and capabilities reference guide.
            """
            static_path = Path(__file__).parent.parent / "static" / "skills.html"
            return FileResponse(static_path, media_type="text/html")

    async def _handle_initialize(
        self, request_id: Optional[str], params: Dict[str, Any]
    ) -> JSONResponse:
        """
        Handle the MCP initialize handshake.

        This is the first request from the backend to establish the connection
        and exchange capabilities.
        """
        logger.info("Handling initialize request")

        # Mark as initialized
        self.initialized = True

        # Build response
        response = InitializeResponse(
            protocolVersion="2024-11-05",
            capabilities=ServerCapabilities(
                tools={},  # We support story drafting tools
                resources={},  # No resources in this server
                prompts={},  # No prompts in this server
            ),
            serverInfo=ServerInfo(name="Spot Story MCP", version="0.1.0"),
        )

        logger.info("Initialize successful")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "result": response.model_dump(),
            }
        )

    async def _handle_list_tools(
        self, request_id: Optional[str], params: Dict[str, Any]
    ) -> JSONResponse:
        """
        Handle tools/list request.

        Returns all registered tools with their schemas.
        """
        logger.info("Listing tools")

        # Get all tools from registry
        tools = tool_registry.list_tools()

        # Convert to MCP schema format
        tool_schemas = [tool.to_mcp_schema() for tool in tools]

        # Debug: Log orchestration hints for each tool
        for tool in tools:
            hints = tool.orchestration_hints
            logger.info(f"Tool '{tool.name}' orchestration_hints: {hints is not None}, enabled: {hints.get('enabled') if hints else 'N/A'}")

        logger.info(f"Returning {len(tool_schemas)} tools")
        return JSONResponse(
            content={"jsonrpc": "2.0", "id": request_id, "result": {"tools": tool_schemas}}
        )

    async def _handle_call_tool(
        self, request_id: Optional[str], params: Dict[str, Any], headers: Dict[str, str]
    ) -> JSONResponse:
        """
        Handle tools/call request with mcp-hitl support.

        Executes a tool and returns the result, with automatic interrupt handling.
        """
        # Import mcp_hitl handler
        from mcp_hitl import handle_tool_call

        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        logger.info(f"Calling tool: {tool_name} with args: {arguments}")

        # Extract JWT token from Authorization header
        jwt_token = headers.get("authorization", "").removeprefix("Bearer ")

        # Use mcp_hitl helper for automatic interrupt handling
        # This handles:
        # - Normal tool execution
        # - Interrupt responses with continuation tokens
        # - Resume with user responses
        # - Proper JSON-RPC formatting
        return await handle_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            jwt_token=jwt_token,
            request_id=request_id,
            tool_registry=tool_registry
        )

    async def _handle_list_resources(
        self, request_id: Optional[str], params: Dict[str, Any]
    ) -> JSONResponse:
        """
        Handle resources/list request.

        Resources are not implemented in this server.
        Returns empty list.
        """
        logger.info("Listing resources (not implemented)")
        return JSONResponse(
            content={"jsonrpc": "2.0", "id": request_id, "result": {"resources": []}}
        )

    async def _handle_list_prompts(
        self, request_id: Optional[str], params: Dict[str, Any]
    ) -> JSONResponse:
        """
        Handle prompts/list request.

        Prompts are not implemented in this server.
        Returns empty list.
        """
        logger.info("Listing prompts (not implemented)")
        return JSONResponse(
            content={"jsonrpc": "2.0", "id": request_id, "result": {"prompts": []}}
        )

    def _error_response(
        self, request_id: Optional[str], code: int, message: str
    ) -> JSONResponse:
        """
        Build a JSON-RPC 2.0 error response.

        Error codes:
        -32700: Parse error
        -32600: Invalid request
        -32601: Method not found
        -32602: Invalid params
        -32603: Internal error
        """
        error = MCPError(code=code, message=message)
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": error.model_dump(),
            },
            status_code=200,  # JSON-RPC errors use 200 status
        )


def main():
    """
    Entry point for running the server.
    """
    # Get configuration from environment
    host = os.getenv("MCP_HOST", "0.0.0.0")
    # Default to 8000 for Docker/production, override with MCP_PORT env var (e.g., 8004 for local dev)
    port = int(os.getenv("MCP_PORT", "8000"))

    # Create server instance
    server = StoryDraftingMCPServer()

    # Log startup
    logger.info(f"Starting Story Drafting MCP Server on {host}:{port}")

    # Run server
    uvicorn.run(server.app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
