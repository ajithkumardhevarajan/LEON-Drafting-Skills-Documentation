"""
Urgent Drafting MCP Server

This is the main FastAPI server implementing the Model Context Protocol (MCP)
for urgent news drafting capabilities. It handles JSON-RPC 2.0 requests from the
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
from fastapi.responses import JSONResponse
import uvicorn

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


class UrgentDraftingMCPServer:
    """
    MCP Server implementing the Model Context Protocol over HTTP.

    This server:
    - Handles MCP JSON-RPC 2.0 protocol
    - Provides urgent news drafting tools
    - Includes health check endpoints
    - Supports CORS for cross-origin requests
    """

    def __init__(self):
        self.app = FastAPI(
            title="Urgent Drafting MCP Server",
            description="Model Context Protocol server for urgent news drafting capabilities",
            version="0.1.0",
        )
        self.start_time = time.time()
        self.initialized = False

        self._setup_middleware()
        self._setup_routes()

        logger.info("Urgent Drafting MCP Server initialized")

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
                server_name="Urgent Drafting MCP",
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
                tools={},  # We support urgent drafting tools
                resources={},  # No resources in this server
                prompts={},  # No prompts in this server
            ),
            serverInfo=ServerInfo(name="Urgent Drafting MCP", version="0.1.0"),
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

        logger.info(f"Returning {len(tool_schemas)} tools")
        return JSONResponse(
            content={"jsonrpc": "2.0", "id": request_id, "result": {"tools": tool_schemas}}
        )

    async def _handle_call_tool(
        self, request_id: Optional[str], params: Dict[str, Any], headers: Dict[str, str]
    ) -> JSONResponse:
        """
        Handle tools/call request.

        Executes a tool and returns the result.
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        logger.info(f"Calling tool: {tool_name} with args: {arguments}")

        try:
            # Extract JWT token from Authorization header
            jwt_token = headers.get("authorization", "").removeprefix("Bearer ")

            # Execute tool
            result = await tool_registry.execute_tool(
                tool_name, arguments, jwt_token
            )

            logger.info(f"Tool {tool_name} executed successfully")
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": result.content,
                        "isError": result.isError,
                    },
                }
            )

        except ValueError as e:
            # Tool not found
            logger.error(f"Tool not found: {tool_name}")
            return self._error_response(request_id, -32602, str(e))

        except Exception as e:
            # Execution error
            logger.error(
                f"Error executing tool {tool_name}: {str(e)}", exc_info=True
            )
            return self._error_response(
                request_id, -32603, f"Tool execution failed: {str(e)}"
            )

    async def _handle_list_resources(
        self, request_id: Optional[str], params: Dict[str, Any]
    ) -> JSONResponse:
        """
        Handle resources/list request.

        Resources are not implemented in this boilerplate.
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

        Prompts are not implemented in this boilerplate.
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
    port = int(os.getenv("MCP_PORT", "8003"))

    # Create server instance
    server = UrgentDraftingMCPServer()

    # Log startup
    logger.info(f"Starting Urgent Drafting MCP Server on {host}:{port}")

    # Run server
    uvicorn.run(server.app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
