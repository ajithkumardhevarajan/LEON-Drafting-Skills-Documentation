# Static Files

This directory contains static files served by the Story Drafting MCP Server.

## Files

- `skills.html` - Interactive skills and capabilities reference guide
  - Accessible at `/skills` endpoint
  - Comprehensive documentation for all Reuters AI Assistant skills
  - Includes workflows, capabilities matrix, and model information

## Usage

The static files are served via FastAPI's FileResponse at dedicated routes.

### Accessing the Skills Documentation

When the service is deployed:
- **Local:** http://localhost:8004/skills
- **Dev:** https://reuters-drafting.8663.aws-int.thomsonreuters.com/skills (or appropriate ALB URL)
