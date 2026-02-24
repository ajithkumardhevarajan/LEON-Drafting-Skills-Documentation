#!/usr/bin/env bash
set -e

# Convenience script to run the Text Archive MCP Server in Docker locally
# Automatically fetches all credentials from AWS and passes them to the container
#
# Prerequisites:
#   - AWS CLI configured
#   - cloud-tool login (for AWS access)
#
# Usage:
#   ./run-docker-local.sh           # Run on default port 8005
#   ./run-docker-local.sh 8006      # Run on custom port

# Colors for output
RED='\e[31m'
GREEN='\e[32m'
BLUE='\e[34m'
YELLOW='\e[33m'
NC='\e[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

IMAGE_NAME="text-archive-local"
CONTAINER_NAME="text-archive-dev"
PORT="${1:-8005}"
SECRET_NAME="a207920-leon-skills"
AWS_REGION="eu-west-1"

echo -e "${BLUE}=== Text Archive MCP Server - Docker Local Runner ===${NC}"
echo ""

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}ERROR: Docker is not running${NC}"
    echo -e "Please start Docker Desktop and try again"
    exit 1
fi
echo -e "${GREEN}✓ Docker is running${NC}"

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo -e "${RED}ERROR: AWS CLI not found${NC}"
    echo -e "Please install AWS CLI: https://aws.amazon.com/cli/"
    exit 1
fi
echo -e "${GREEN}✓ AWS CLI found${NC}"

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}ERROR: AWS credentials not configured or expired${NC}"
    echo -e "Please run:"
    echo -e "  ${BLUE}cloud-tool login -u 'mgmt\\mEmpId' -p 'vault_password' --account-id '060725138335' --role 'human-role/a207920-PowerUser2'${NC}"
    exit 1
fi
echo -e "${GREEN}✓ AWS credentials valid${NC}"

# Fetch JFrog credentials from AWS SSM Parameter Store
echo -e "\n${BLUE}Fetching JFrog credentials from AWS SSM...${NC}"

JFROG_USERNAME=$(aws ssm get-parameter \
    --name '/a207920/leon-skills/jfrog/username' \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text 2>/dev/null) || {
    echo -e "${RED}ERROR: Failed to fetch JFrog username from SSM${NC}"
    exit 1
}

JFROG_TOKEN=$(aws ssm get-parameter \
    --name '/a207920/leon-skills/jfrog/token' \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text 2>/dev/null) || {
    echo -e "${RED}ERROR: Failed to fetch JFrog token from SSM${NC}"
    exit 1
}

echo -e "${GREEN}✓ JFrog credentials fetched${NC}"

# Fetch application secrets from AWS Secrets Manager
echo -e "\n${BLUE}Fetching application secrets from AWS Secrets Manager...${NC}"
echo -e "Secret: ${BLUE}$SECRET_NAME${NC}"

SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_NAME" \
    --region "$AWS_REGION" \
    --query SecretString \
    --output text 2>/dev/null) || {
    echo -e "${RED}ERROR: Failed to fetch secrets from Secrets Manager${NC}"
    echo -e "Make sure you have access to: ${BLUE}$SECRET_NAME${NC}"
    exit 1
}

# Parse secrets using Python
echo -e "${BLUE}Parsing secrets...${NC}"

REUTERS_ARCHIVE_CLIENT_ID=$(echo "$SECRET_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('REUTERS_ARCHIVE_CLIENT_ID',''))" 2>/dev/null || echo "")
REUTERS_ARCHIVE_CLIENT_SECRET=$(echo "$SECRET_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('REUTERS_ARCHIVE_CLIENT_SECRET',''))" 2>/dev/null || echo "")

# Verify secrets
echo -e "${BLUE}Secret values status:${NC}"
echo -e "  REUTERS_ARCHIVE_CLIENT_ID: ${REUTERS_ARCHIVE_CLIENT_ID:+SET}${REUTERS_ARCHIVE_CLIENT_ID:-NOT SET}"
echo -e "  REUTERS_ARCHIVE_CLIENT_SECRET: ${REUTERS_ARCHIVE_CLIENT_SECRET:+SET (${#REUTERS_ARCHIVE_CLIENT_SECRET} chars)}${REUTERS_ARCHIVE_CLIENT_SECRET:-NOT SET}"

if [[ -z "$REUTERS_ARCHIVE_CLIENT_ID" ]] || [[ -z "$REUTERS_ARCHIVE_CLIENT_SECRET" ]]; then
    echo -e "${YELLOW}⚠ Warning: Archive API credentials are missing from Secrets Manager${NC}"
    echo -e "  The server will start but tool calls will return a configuration error."
    echo -e "  To fix: add REUTERS_ARCHIVE_CLIENT_ID and REUTERS_ARCHIVE_CLIENT_SECRET to the ${BLUE}$SECRET_NAME${NC} secret."
else
    echo -e "${GREEN}✓ Application secrets fetched${NC}"
fi

# Build the Docker image from the repo root (Dockerfile uses COPY text-archive/...)
echo -e "\n${BLUE}Building Docker image...${NC}"
echo -e "Build context: ${BLUE}$REPO_ROOT${NC}"

docker build --platform linux/arm64 \
    -f "$SCRIPT_DIR/Dockerfile" \
    --build-arg JFROG_USERNAME="$JFROG_USERNAME" \
    --build-arg JFROG_TOKEN="$JFROG_TOKEN" \
    -t "$IMAGE_NAME" \
    "$REPO_ROOT"

echo -e "${GREEN}✓ Image built successfully${NC}"

# Stop and remove existing container if it exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "\n${BLUE}Stopping existing container...${NC}"
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi

echo -e "\n${BLUE}Starting container...${NC}"
echo -e "Port: ${BLUE}localhost:$PORT -> container:8000${NC}"

docker run -d \
    --name "$CONTAINER_NAME" \
    -p "$PORT:8000" \
    -e MCP_PORT=8000 \
    -e REUTERS_ARCHIVE_CLIENT_ID="$REUTERS_ARCHIVE_CLIENT_ID" \
    -e REUTERS_ARCHIVE_CLIENT_SECRET="$REUTERS_ARCHIVE_CLIENT_SECRET" \
    "$IMAGE_NAME"

# Wait for container to start
sleep 2

# Check if container is running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${GREEN}✓ Container started successfully!${NC}"
    echo ""
    echo -e "${GREEN}=== Service Information ===${NC}"
    echo -e "Health:    ${BLUE}http://localhost:$PORT/health${NC}"
    echo -e "Ready:     ${BLUE}http://localhost:$PORT/ready${NC}"
    echo ""
    echo -e "${GREEN}=== Test Commands ===${NC}"
    echo -e "Health check:"
    echo -e "  ${BLUE}curl http://localhost:$PORT/health${NC}"
    echo ""
    echo -e "List tools:"
    echo -e "  ${BLUE}curl -s -X POST http://localhost:$PORT/ \\
    -H 'Content-Type: application/json' \\
    -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}' | python3 -m json.tool${NC}"
    echo ""
    echo -e "Call the archive search tool:"
    echo -e "  ${BLUE}curl -s -X POST http://localhost:$PORT/ \\
    -H 'Content-Type: application/json' \\
    -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"search_reuters_text_archive\",\"arguments\":{\"query\":\"What are the key points of Ford EV strategy?\"}}}' | python3 -m json.tool${NC}"
    echo ""
    echo -e "${GREEN}=== Useful Commands ===${NC}"
    echo -e "View logs:     ${BLUE}docker logs -f $CONTAINER_NAME${NC}"
    echo -e "Stop:          ${BLUE}docker stop $CONTAINER_NAME${NC}"
    echo -e "Restart:       ${BLUE}docker restart $CONTAINER_NAME${NC}"
    echo ""
    echo -e "${YELLOW}Showing container logs (Ctrl+C to exit, container keeps running):${NC}"
    echo ""
    docker logs -f "$CONTAINER_NAME"
else
    echo -e "${RED}ERROR: Container failed to start${NC}"
    echo -e "Logs:"
    docker logs "$CONTAINER_NAME"
    exit 1
fi
