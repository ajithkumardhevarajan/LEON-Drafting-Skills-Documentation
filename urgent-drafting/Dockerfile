# Urgent Drafting MCP Server Dockerfile
#
# Build: docker build -t urgent-drafting-mcp .
# Run:   docker run -p 8000:8000 urgent-drafting-mcp

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:0.9.1 /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./
RUN touch README.md

# Install dependencies
RUN uv venv && \
    uv pip install -e .

# Copy source code
COPY src/ ./src/
COPY run.py ./

# Expose port (default 8000, override with MCP_PORT env var)
EXPOSE 8000

# Run the server
CMD ["python", "run.py"]
