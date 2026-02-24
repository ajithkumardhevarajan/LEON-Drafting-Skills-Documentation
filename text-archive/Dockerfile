# Text Archive MCP Server Dockerfile
#
# Build: docker build --platform linux/arm64 -t text-archive-mcp .
# Run:   docker run -p 8000:8000 text-archive-mcp

# ===== Builder stage: Build wheels for all dependencies =====
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim as builder

# Accept JFrog credentials as build arguments (for private packages)
ARG JFROG_USERNAME
ARG JFROG_TOKEN

WORKDIR /build

# Install build dependencies
RUN python3 -m venv /build/venv && \
    /build/venv/bin/pip install --no-cache-dir --upgrade pip wheel setuptools build

# Copy skill files
COPY text-archive/ /build/skill/
WORKDIR /build/skill

# Build wheels for all skill dependencies (including JFrog private packages)
RUN /build/venv/bin/pip wheel --wheel-dir /build/wheels --no-cache-dir \
    --index-url https://pypi.org/simple \
    --extra-index-url "https://${JFROG_USERNAME}:${JFROG_TOKEN}@tr1.jfrog.io/artifactory/api/pypi/pypi/simple" \
    . && \
    echo "=== Built all wheels ===" && \
    ls -lh /build/wheels/

# ===== Runtime stage: Minimal image with only runtime dependencies =====
FROM public.ecr.aws/docker/library/python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/venv/bin:$PATH"

WORKDIR /app

# Create virtual environment and install from pre-built wheels
RUN python3 -m venv /app/venv

# Copy wheels from builder and install (fast, no build deps needed)
COPY --from=builder /build/wheels /tmp/wheels
RUN /app/venv/bin/pip install --no-cache-dir /tmp/wheels/*.whl && \
    rm -rf /tmp/wheels && \
    echo "=== Installed packages ===" && \
    /app/venv/bin/pip list

# Copy application code (done last for better layer caching)
COPY text-archive/src/ ./src/
COPY text-archive/run.py ./

# Expose port (default 8000, override with MCP_PORT env var)
EXPOSE 8000

# Run the server
CMD ["python", "run.py"]
