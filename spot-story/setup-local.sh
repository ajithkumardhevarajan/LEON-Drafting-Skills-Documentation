#!/usr/bin/env bash
#
# Local Development Setup Script
# Fetches JFrog credentials from AWS SSM Parameter Store and configures environment
#
# Usage:
#   source ./setup-local.sh
#   OR
#   . ./setup-local.sh
#
# Note: Must be sourced (not executed) to export environment variables to current shell

# Check if script is being sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "ERROR: This script must be sourced, not executed"
    echo "Usage: source ./setup-local.sh"
    exit 1
fi

# Function to handle errors without exiting the terminal
handle_error() {
    echo -e "${RED}ERROR: $1${NC}"
    return 1
}

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Spot Story Local Development Setup ===${NC}"

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo -e "${RED}ERROR: AWS CLI not found${NC}"
    echo -e "Please install AWS CLI: https://aws.amazon.com/cli/"
    return 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}ERROR: AWS credentials not configured${NC}"
    echo -e "Please configure AWS CLI with: aws configure --profile tr-central-preprod"
    return 1
fi

echo -e "${BLUE}Fetching JFrog credentials from AWS SSM Parameter Store...${NC}"

# Fetch JFrog credentials from SSM Parameter Store
JFROG_USERNAME=$(aws ssm get-parameter \
    --name '/a207920/leon-skills/jfrog/username' \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text 2>/dev/null)

JFROG_TOKEN=$(aws ssm get-parameter \
    --name '/a207920/leon-skills/jfrog/token' \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text 2>/dev/null)

if [[ -z "$JFROG_USERNAME" || -z "$JFROG_TOKEN" ]]; then
    echo -e "${RED}ERROR: Failed to fetch JFrog credentials from SSM${NC}"
    echo -e "Please ensure you have access to:"
    echo -e "  - /a207920/leon-skills/jfrog/username"
    echo -e "  - /a207920/leon-skills/jfrog/token"
    return 1
fi

# Export credentials for uv to use
export JFROG_USERNAME
export JFROG_TOKEN

# Configure uv to use JFrog credentials
# uv uses UV_INDEX_<NAME>_USERNAME and UV_INDEX_<NAME>_PASSWORD
# where <NAME> is the uppercase name of the index (JFROG in our case)
export UV_INDEX_JFROG_USERNAME="$JFROG_USERNAME"
export UV_INDEX_JFROG_PASSWORD="$JFROG_TOKEN"

echo -e "${GREEN}✓ JFrog credentials configured${NC}"
echo -e "  Username: ${JFROG_USERNAME:0:3}*** (${#JFROG_USERNAME} chars)"
echo -e "  Token: *** (${#JFROG_TOKEN} chars)"
echo -e "  UV_INDEX_JFROG_USERNAME: ${UV_INDEX_JFROG_USERNAME:0:3}*** (${#UV_INDEX_JFROG_USERNAME} chars)"
echo -e "  UV_INDEX_JFROG_PASSWORD: *** (${#UV_INDEX_JFROG_PASSWORD} chars)"

# Check if virtual environment exists
if [[ ! -d ".venv" ]]; then
    echo -e "\n${BLUE}Creating virtual environment...${NC}"
    uv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "\n${BLUE}Activating virtual environment...${NC}"
source .venv/bin/activate

echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Install dependencies
echo -e "\n${BLUE}Installing dependencies...${NC}"
if ! uv pip install -e .; then
    echo -e "${RED}ERROR: Failed to install dependencies${NC}"
    echo -e "Check the error messages above for details"
    return 1
fi

echo -e "${GREEN}✓ Dependencies installed successfully${NC}"

echo -e "\n${GREEN}=== Setup Complete! ===${NC}"
echo -e "\nYou can now:"
echo -e "  ${BLUE}1.${NC} Run the server: ${YELLOW}python run.py${NC}"
echo -e "  ${BLUE}2.${NC} Test health: ${YELLOW}curl http://localhost:8004/health${NC}"
echo -e "  ${BLUE}3.${NC} Run tests: ${YELLOW}pytest${NC} (if tests exist)"
echo -e "\n${YELLOW}Note: JFrog credentials are set for this shell session only${NC}"
echo -e "${YELLOW}Re-run 'source ./setup-local.sh' in new terminal sessions${NC}"
