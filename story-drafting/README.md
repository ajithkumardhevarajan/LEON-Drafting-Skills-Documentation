# Story Drafting Skill

A Model Context Protocol (MCP) server providing story drafting generation capabilities for the LEON assistant.

## Overview

This skill provides a placeholder implementation for story drafting generation. The infrastructure is fully deployable to AWS ECS with proper authentication and secrets management, while the business logic will be implemented in future iterations.

## Features

- **MCP Protocol Compliant**: Implements the Model Context Protocol for seamless integration with LEON orchestrator
- **Placeholder Tool**: `generate_spot_story` - Accepts topic and context parameters and returns a placeholder response
- **AWS ECS Deployment**: Complete infrastructure for deploying to AWS with Application Load Balancer
- **Auto-scaling**: Configured for automatic scaling based on CPU and memory utilization
- **Secrets Management**: Integrated with AWS Secrets Manager for secure credential handling
- **Health Checks**: Built-in health and readiness endpoints for container orchestration

## Architecture

```
story-drafting/
├── src/
│   ├── main.py              # FastAPI MCP server
│   ├── models.py            # MCP protocol models
│   ├── tools/
│   │   ├── base.py          # BaseTool abstract class
│   │   └── generate_spot_story.py  # Placeholder tool
│   ├── services/
│   │   └── spot_story_service.py   # Placeholder service
│   └── config/              # Configuration management
├── infra/
│   ├── app.py               # CDK app entry point
│   ├── mcp_stack.py         # ECS/ALB stack definition
│   ├── config.py            # Deployment configuration
│   ├── deploy.sh            # Deployment script
│   └── VERSION              # Version tracking (0.1.x)
└── Dockerfile               # Multi-stage container build
```

## Prerequisites

- Python 3.11+
- Docker (for local testing and building)
- AWS CLI configured with appropriate credentials
- Access to JFrog Artifactory (for private packages)

## Local Development

### 1. Install Dependencies

```bash
# Create virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package in editable mode
uv pip install -e .
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
# Note: For local development, you may use placeholder values
# AWS Secrets Manager provides credentials in deployed environments
```

### 3. Run Locally

```bash
# Start the server (defaults to port 8004)
python run.py

# Or use the installed command
story-drafting-mcp
```

### 4. Test the Server

```bash
# Health check
curl http://localhost:8004/health

# Initialize MCP connection
curl -X POST http://localhost:8004/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'

# List available tools
curl -X POST http://localhost:8004/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# Call the placeholder tool
curl -X POST http://localhost:8004/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":3,
    "method":"tools/call",
    "params":{
      "name":"generate_spot_story",
      "arguments":{
        "topic":"Market Update",
        "context":"Financial markets trading activity"
      }
    }
  }'
```

## Deployment

See [infra/README.md](infra/README.md) for detailed deployment instructions.

### Quick Deploy

```bash
cd infra

# Deploy to dev environment
./deploy.sh deploy dev

# Deploy to qa environment
./deploy.sh deploy qa
```

## AWS Configuration

- **AWS Account**: 060725138335 (dev and qa)
- **Region**: eu-west-1
- **Asset ID**: 207920
- **Secrets**: arn:aws:secretsmanager:eu-west-1:060725138335:secret:a207920-leon-skills-vWvmX7
- **Port**: 8004 (different from urgent-drafting's 8003)

## Available Tools

### `generate_spot_story`

Placeholder tool for story drafting generation.

**Parameters:**
- `topic` (string, required): The topic or subject for the story drafting
- `context` (string, optional): Additional context or background information

**Response:**
Returns a placeholder message indicating the tool is functional but business logic is not yet implemented.

## Future Development

This skill is designed to be enhanced with actual story drafting generation logic:

1. **Business Logic**: Implement actual story generation in `spot_story_service.py`
2. **API Integration**: Add connections to Reuters APIs or other data sources
3. **LLM Integration**: Integrate with Azure OpenAI or other LLM services for content generation
4. **Additional Tools**: Add more tools for story refinement, validation, etc.

The infrastructure and MCP interface are production-ready and do not need changes when business logic is added.

## License

Thomson Reuters Internal Use Only
