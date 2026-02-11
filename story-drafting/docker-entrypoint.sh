#!/usr/bin/env bash
set -e

# Docker entrypoint script for LOCAL DEVELOPMENT
# Fetches secrets from AWS Secrets Manager to eliminate storing secrets in .env files
# NOTE: This is only used with Dockerfile.local, not in production ECS deployment

# Colors for output
RED='\e[31m'
GREEN='\e[32m'
BLUE='\e[34m'
YELLOW='\e[33m'
NC='\e[0m' # No Color

echo -e "${BLUE}=== Story Drafting MCP Server - Local Development ===${NC}"

# Configuration
export AWS_REGION="${AWS_REGION:-eu-west-1}"
export SECRET_NAME="${SECRET_NAME:-a207920-leon-skills}"
export AWS_PROFILE="${AWS_PROFILE:-tr-central-preprod}"

# Function to fetch secrets from AWS Secrets Manager
fetch_aws_secrets() {
    echo -e "${BLUE}Attempting to fetch secrets from AWS Secrets Manager...${NC}"
    echo -e "Secret: ${BLUE}$SECRET_NAME${NC}"
    echo -e "Region: ${BLUE}$AWS_REGION${NC}"
    echo -e "Profile: ${BLUE}$AWS_PROFILE${NC}"

    # Check if AWS CLI is available
    if ! command -v aws &> /dev/null; then
        echo -e "${YELLOW}⚠ AWS CLI not found. Falling back to .env file.${NC}"
        return 1
    fi

    # Try to fetch the secret
    if SECRET_JSON=$(aws secretsmanager get-secret-value \
        --secret-id "$SECRET_NAME" \
        --region "$AWS_REGION" \
        --query SecretString \
        --output text 2>/dev/null); then

        echo -e "${GREEN}✓ Successfully fetched secrets from AWS${NC}"

        # Parse JSON using jq if available, otherwise use grep
        if command -v jq &> /dev/null; then
            # Use jq for reliable JSON parsing
            export ORCHESTRATOR_ENDPOINT=$(echo "$SECRET_JSON" | jq -r '.ORCHESTRATOR_ENDPOINT // empty')
            export LEON_ORCHESTRATOR_API_KEY=$(echo "$SECRET_JSON" | jq -r '.LEON_ORCHESTRATOR_API_KEY // empty')
            export LEON_ORCHESTRATOR_TENANT_ID=$(echo "$SECRET_JSON" | jq -r '.LEON_ORCHESTRATOR_TENANT_ID // empty')
            export LEON_ORCHESTRATOR_CLIENT_ID=$(echo "$SECRET_JSON" | jq -r '.LEON_ORCHESTRATOR_CLIENT_ID // empty')
            export LEON_ORCHESTRATOR_CLIENT_SECRET=$(echo "$SECRET_JSON" | jq -r '.LEON_ORCHESTRATOR_CLIENT_SECRET // empty')
            export LEON_ORCHESTRATOR_RESOURCE=$(echo "$SECRET_JSON" | jq -r '.LEON_ORCHESTRATOR_RESOURCE // empty')
            export REUTERS_API_KEY=$(echo "$SECRET_JSON" | jq -r '.REUTERS_API_KEY // empty')
            export AZURE_OPENAI_ENDPOINT=$(echo "$SECRET_JSON" | jq -r '.AZURE_OPENAI_ENDPOINT // empty')
            export AZURE_OPENAI_API_KEY=$(echo "$SECRET_JSON" | jq -r '.AZURE_OPENAI_API_KEY // empty')
        else
            # Fallback to grep-based parsing
            SECRET_JSON_CLEAN=$(echo "$SECRET_JSON" | tr -d '\n' | tr -s ' ')

            ORCHESTRATOR_ENDPOINT=$(echo "$SECRET_JSON_CLEAN" | grep -o '"ORCHESTRATOR_ENDPOINT": *"[^"]*"' | sed 's/.*": *"//' | sed 's/"$//')
            LEON_ORCHESTRATOR_API_KEY=$(echo "$SECRET_JSON_CLEAN" | grep -o '"LEON_ORCHESTRATOR_API_KEY": *"[^"]*"' | sed 's/.*": *"//' | sed 's/"$//')
            LEON_ORCHESTRATOR_TENANT_ID=$(echo "$SECRET_JSON_CLEAN" | grep -o '"LEON_ORCHESTRATOR_TENANT_ID": *"[^"]*"' | sed 's/.*": *"//' | sed 's/"$//')
            LEON_ORCHESTRATOR_CLIENT_ID=$(echo "$SECRET_JSON_CLEAN" | grep -o '"LEON_ORCHESTRATOR_CLIENT_ID": *"[^"]*"' | sed 's/.*": *"//' | sed 's/"$//')
            LEON_ORCHESTRATOR_CLIENT_SECRET=$(echo "$SECRET_JSON_CLEAN" | grep -o '"LEON_ORCHESTRATOR_CLIENT_SECRET": *"[^"]*"' | sed 's/.*": *"//' | sed 's/"$//')
            LEON_ORCHESTRATOR_RESOURCE=$(echo "$SECRET_JSON_CLEAN" | grep -o '"LEON_ORCHESTRATOR_RESOURCE": *"[^"]*"' | sed 's/.*": *"//' | sed 's/"$//')
            REUTERS_API_KEY=$(echo "$SECRET_JSON_CLEAN" | grep -o '"REUTERS_API_KEY": *"[^"]*"' | sed 's/.*": *"//' | sed 's/"$//')
            AZURE_OPENAI_ENDPOINT=$(echo "$SECRET_JSON_CLEAN" | grep -o '"AZURE_OPENAI_ENDPOINT": *"[^"]*"' | sed 's/.*": *"//' | sed 's/"$//')
            AZURE_OPENAI_API_KEY=$(echo "$SECRET_JSON_CLEAN" | grep -o '"AZURE_OPENAI_API_KEY": *"[^"]*"' | sed 's/.*": *"//' | sed 's/"$//')

            export ORCHESTRATOR_ENDPOINT
            export LEON_ORCHESTRATOR_API_KEY
            export LEON_ORCHESTRATOR_TENANT_ID
            export LEON_ORCHESTRATOR_CLIENT_ID
            export LEON_ORCHESTRATOR_CLIENT_SECRET
            export LEON_ORCHESTRATOR_RESOURCE
            export REUTERS_API_KEY
            export AZURE_OPENAI_ENDPOINT
            export AZURE_OPENAI_API_KEY
        fi

        # Verify critical secrets were set
        if [ -z "$ORCHESTRATOR_ENDPOINT" ] || [ -z "$LEON_ORCHESTRATOR_API_KEY" ]; then
            echo -e "${YELLOW}⚠ Some secrets may not have been parsed correctly${NC}"
            echo -e "${YELLOW}  ORCHESTRATOR_ENDPOINT: ${ORCHESTRATOR_ENDPOINT:+set}${ORCHESTRATOR_ENDPOINT:-NOT SET}${NC}"
            echo -e "${YELLOW}  LEON_ORCHESTRATOR_API_KEY: ${LEON_ORCHESTRATOR_API_KEY:+set}${NC}"
        else
            echo -e "${GREEN}✓ Secrets exported as environment variables${NC}"
        fi

        return 0
    else
        echo -e "${YELLOW}⚠ Failed to fetch secrets from AWS. Falling back to .env file.${NC}"
        echo -e "${YELLOW}  Make sure you are logged in with cloud-tool:${NC}"
        echo -e "${YELLOW}  cloud-tool login -u 'mgmt\\mEmpId' -p 'vault_password' --account-id '060725138335' --role 'human-role/a207920-PowerUser2'${NC}"
        return 1
    fi
}

# Function to verify required environment variables
verify_env_vars() {
    local missing_vars=()

    required_vars=(
        "ORCHESTRATOR_ENDPOINT"
        "LEON_ORCHESTRATOR_API_KEY"
    )

    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo -e "${YELLOW}WARNING: Missing some environment variables:${NC}"
        for var in "${missing_vars[@]}"; do
            echo -e "  ${YELLOW}✗ $var${NC}"
        done
        echo -e "\n${YELLOW}The server will start but may not function correctly.${NC}"
        echo -e "${YELLOW}Please either:${NC}"
        echo -e "1. Login with cloud-tool: ${BLUE}cloud-tool login -u 'mgmt\\mEmpId' -p 'vault_password' --account-id '060725138335' --role 'human-role/a207920-PowerUser2'${NC}"
        echo -e "2. Or provide environment variables via docker run -e or .env file"
    else
        echo -e "${GREEN}✓ All required environment variables are set${NC}"
    fi
}

# Main startup logic
main() {
    # Try to fetch secrets from AWS Secrets Manager
    # Falls back to existing env vars if AWS is unavailable
    fetch_aws_secrets || true

    # Verify required variables are present
    verify_env_vars

    # Display startup info (without exposing secret values)
    echo -e "\n${GREEN}=== Configuration ===${NC}"
    echo -e "Service: ${BLUE}story-drafting-mcp${NC}"
    echo -e "Port: ${BLUE}${MCP_PORT:-8000}${NC}"
    echo -e "Orchestrator: ${BLUE}${ORCHESTRATOR_ENDPOINT:-NOT SET}${NC}"
    echo -e "API Key: ${BLUE}${LEON_ORCHESTRATOR_API_KEY:+***set***}${LEON_ORCHESTRATOR_API_KEY:-NOT SET}${NC}"

    echo -e "\n${GREEN}=== Starting Application ===${NC}\n"

    # Execute the main command (passed as arguments to this script)
    exec "$@"
}

# Run main function
main "$@"
