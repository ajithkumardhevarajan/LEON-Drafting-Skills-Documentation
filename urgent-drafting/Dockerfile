# Urgent Drafting MCP Server Dockerfile
#
# Build: docker build --platform linux/arm64 -t urgent-drafting-mcp .
# Run:   docker run -p 8000:8000 urgent-drafting-mcp

# Builder stage - use uv for dependency management
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim as builder

# Accept JFrog credentials as build arguments (for private packages)
ARG JFROG_USERNAME
ARG JFROG_TOKEN

# Set working directory
WORKDIR /app

# Copy dependency files and source code (needed for pip install -e .)
COPY pyproject.toml ./
COPY uv.toml ./
COPY src/ ./src/
COPY run.py ./
RUN touch README.md

# Install dependencies with JFrog authentication (required for private packages)
# Use PyPI for public packages (fastapi, etc.) and JFrog for private packages
# --index-url: Primary index (PyPI)
# --extra-index-url: Additional index for private packages (JFrog)
# Use python3 -m venv instead of uv venv to get pip included
RUN python3 -m venv .venv && \
    /app/.venv/bin/pip install --no-cache-dir . \
    --index-url https://pypi.org/simple \
    --extra-index-url "https://${JFROG_USERNAME}:${JFROG_TOKEN}@tr1.jfrog.io/artifactory/api/pypi/pypi/simple" && \
    echo "=== Installed packages ===" && \
    /app/.venv/bin/pip list

# Runtime stage - minimal image
# Use AWS ECR Public Gallery to avoid Docker Hub rate limits
FROM public.ecr.aws/docker/library/python:3.11-slim-bookworm

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
