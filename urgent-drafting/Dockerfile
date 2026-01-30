# Urgent Drafting MCP Server Dockerfile
#
# Build: docker build --platform linux/arm64 -t urgent-drafting-mcp .
# Run:   docker run -p 8000:8000 urgent-drafting-mcp

# Builder stage - use uv for dependency management
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim as builder

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

# Runtime stage - minimal image
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy virtual environment and application from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/run.py /app/run.py

# Expose port (default 8000, override with MCP_PORT env var)
EXPOSE 8000

# Run the server
CMD ["python", "run.py"]
