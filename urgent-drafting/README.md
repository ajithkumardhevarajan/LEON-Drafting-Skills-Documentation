# Urgent Drafting MCP Server

A **Model Context Protocol (MCP)** server for urgent news drafting capabilities in the Reuters AI Assistant project. This server provides tools for creating breaking news, urgent alerts, and flash updates with different priority levels.

## What is This?

This MCP server provides urgent news drafting functionality with:
- ✅ Full MCP protocol implementation (JSON-RPC 2.0 over HTTP)
- ✅ Urgent draft tool with priority levels (breaking, urgent, flash)
- ✅ Configurable word count and structured draft generation
- ✅ Health check endpoints
- ✅ Docker support
- ✅ Clean, documented code ready to extend

## Quick Start

### 1. Install Dependencies

Using `uv` (recommended):
```bash
cd sample-mcps/urgent-drafting-mcp
uv sync
```

Or using `pip`:
```bash
pip install -e .
```

### 2. Run the Server

```bash
python run.py
```

The server will start on `http://localhost:8000` by default.

### 3. Test the Server

Check health:
```bash
curl http://localhost:8000/health
```

List tools:
```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

Create an urgent draft:
```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "create_urgent_draft",
      "arguments": {
        "topic": "Major earthquake hits coastal region",
        "priority": "breaking",
        "word_count": 200
      }
    }
  }'
```

## Project Structure

```
urgent-drafting-mcp/
├── src/
│   ├── __init__.py              # Package initialization
│   ├── main.py                  # FastAPI server with MCP protocol
│   ├── models.py                # Pydantic models (MCP protocol)
│   └── tools/
│       ├── __init__.py          # Tool registry initialization
│       ├── base.py              # BaseTool abstract class
│       └── urgent_draft_tool.py # Urgent drafting tool
├── pyproject.toml               # Dependencies and project metadata
├── run.py                       # Entry point
├── Dockerfile                   # Container configuration
├── .env.example                # Environment variables template
└── README.md                   # This file
```

## The Urgent Draft Tool

### Tool: `create_urgent_draft`

Creates urgent news drafts with specified priority levels.

**Parameters:**
- **`topic`** (string, required) - The topic or subject for the urgent news draft
- **`priority`** (string, optional) - Priority level: `"breaking"`, `"urgent"`, or `"flash"` (default: `"urgent"`)
- **`word_count`** (integer, optional) - Target word count for the draft body, 50-500 words (default: 150)

**Example Output:**
```
======================================================================
🔴 BREAKING NEWS: BREAKING: Major earthquake hits coastal region
======================================================================

Priority: BREAKING (High Priority)
Generated: 2026-01-30 12:34:56 UTC
Topic: Major earthquake hits coastal region
Target Length: 200 words

──────────────────────────────────────────────────────────────────────
DRAFT BODY
──────────────────────────────────────────────────────────────────────

[LEDE] A significant development regarding Major earthquake hits
coastal region has emerged, according to initial reports...

[CONTEXT] The situation concerning Major earthquake hits coastal
region is currently developing. Reuters is gathering additional
information...

[DETAILS] Further details about Major earthquake hits coastal region
are expected as the story develops...

──────────────────────────────────────────────────────────────────────

[END OF DRAFT]
```

### Priority Levels

- **`flash`** ⚡ - Highest priority, immediate breaking news
- **`breaking`** 🔴 - High priority, important breaking news
- **`urgent`** 🔵 - Standard urgent news updates

## Using as a Template

This server serves as a template for building more sophisticated urgent drafting tools. To extend it:

### 1. Add New Tools

Create `src/tools/my_new_tool.py`:

```python
from typing import Any, Dict
from .base import BaseTool
from ..models import ToolResult

class MyNewTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_new_tool"

    @property
    def description(self) -> str:
        return "Description of what my tool does"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "param1": {
                "type": "string",
                "description": "First parameter",
                "required": True
            }
        }

    async def execute(self, arguments: Dict[str, Any], jwt_token: str) -> ToolResult:
        # Your logic here
        result = f"Processed: {arguments.get('param1')}"
        return ToolResult(
            content=[{"type": "text", "text": result}],
            isError=False
        )
```

### 2. Register Your Tool

Edit `src/tools/__init__.py`:

```python
from .base import BaseTool, ToolRegistry
from .urgent_draft_tool import UrgentDraftTool
from .my_new_tool import MyNewTool  # Add import

tool_registry = ToolRegistry()
tool_registry.register(UrgentDraftTool())
tool_registry.register(MyNewTool())  # Register new tool

__all__ = ["BaseTool", "ToolRegistry", "tool_registry", "UrgentDraftTool", "MyNewTool"]
```

### 3. Enhance the Urgent Draft Tool

The current implementation is a simplified example. To make it production-ready:

1. **Connect to Real Data Sources**
   - Integrate with news APIs (Reuters Wire, etc.)
   - Query story databases for context
   - Access historical articles for reference

2. **Add AI/LLM Integration**
   - Use OpenAI, Claude, or other LLMs for content generation
   - Apply Reuters editorial guidelines
   - Generate contextually appropriate headlines and bodies

3. **Implement Fact-Checking**
   - Verify information from multiple sources
   - Add source attribution
   - Include confidence scores

## Configuration

Copy `.env.example` to `.env` and adjust:

```bash
cp .env.example .env
```

Available environment variables:
- `MCP_HOST` - Server host (default: `0.0.0.0`)
- `MCP_PORT` - Server port (default: `8000`)

Add any tool-specific configuration variables as needed (API keys, database URLs, etc.).

## Docker Support

Build the image:
```bash
docker build -t urgent-drafting-mcp .
```

Run the container:
```bash
docker run -p 8000:8000 urgent-drafting-mcp
```

With custom port:
```bash
docker run -p 8001:8001 -e MCP_PORT=8001 urgent-drafting-mcp
```

## Registering with the Backend

Once your MCP is running, register it with the Reuters AI Assistant backend:

```bash
# 1. Register the skill globally
curl -X POST http://localhost:8080/api/v1/admin/skills \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{
    "name": "Urgent Drafting MCP",
    "endpoint_url": "http://localhost:8000",
    "description": "Creates urgent news drafts with priority levels (breaking, urgent, flash)"
  }'

# 2. Associate with your tenant
curl -X POST http://localhost:8080/api/v1/admin/tenants/YOUR_TENANT_ID/skills \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{
    "skill_id": "SKILL_ID_FROM_PREVIOUS_RESPONSE"
  }'
```

## Advanced Features

### Response Modes

Control how the backend processes your tool's output:

```python
@property
def response_mode(self) -> str:
    return "direct"  # "direct" | "enhanced" | None
```

- `None` (default): Backend decides
- `"direct"`: Return tool result directly to user
- `"enhanced"`: Send result to LLM for additional processing

### Preferred Model

Request a specific LLM for your tool:

```python
@property
def preferred_model(self) -> str:
    return "gpt-4o"  # or "claude-3-5-sonnet", etc.
```

### Fast-Path Orchestration

Enable pattern-based routing to bypass LLM orchestration:

```python
@property
def orchestration_hints(self) -> Dict[str, Any]:
    return {
        "enabled": True,
        "priority": 10,
        "query_patterns": [
            r"create\s+urgent\s+draft",
            r"breaking\s+news\s+about"
        ],
        "parameter_extractions": [
            {
                "parameter_name": "topic",
                "fallback": "user_query",
                "required": True
            }
        ]
    }
```

### Parameter UI Metadata

Provide hints for the UI when prompting for parameters:

```python
"parameters": {
    "priority": {
        "type": "string",
        "description": "Priority level",
        "enum": ["breaking", "urgent", "flash"],
        "ui_metadata": {
            "widget": "select",
            "labels": {
                "breaking": "🔴 Breaking News",
                "urgent": "🔵 Urgent",
                "flash": "⚡ Flash"
            }
        }
    }
}
```

## Development Tips

1. **Start Simple**: The current implementation is intentionally basic - extend it incrementally
2. **Test Locally**: Use curl or Postman to test tools before backend integration
3. **Log Everything**: Use Python logging for debugging (logs appear in console/Docker logs)
4. **Error Handling**: Always return `ToolResult` with `isError=True` for errors
5. **Validate Inputs**: Check all required parameters and validate ranges/enums
6. **Document Well**: Clear docstrings help other developers understand your tools

## Example Use Cases

This MCP can be extended for:

- **Breaking News Alerts** - Rapid-fire short alerts for developing stories
- **Live Event Coverage** - Real-time updates during major events
- **Crisis Reporting** - Emergency updates with fact-checking requirements
- **Market Flash Reports** - Financial news requiring immediate publication
- **Sports Updates** - Live game scores and breaking sports news

## Related MCPs

Check out other sample MCPs for inspiration:
- `story-search-mcp` - Search and retrieve stories from databases
- `story-draft-mcp` - Full-featured story drafting with approval workflows
- `generate-headline-mcp` - AI-powered headline generation

## Need Help?

- **Documentation**: See `reuters-assistant_backend/docs/` for backend architecture
- **MCP Protocol**: Review `src/models.py` for protocol details
- **Ask the Team**: Reach out if you get stuck!

## License

Internal Reuters project - see main repository for license information.
