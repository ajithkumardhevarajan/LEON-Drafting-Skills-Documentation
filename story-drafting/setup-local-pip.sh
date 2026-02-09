#!/usr/bin/env bash
#
# Alternative Setup Script using pip instead of uv
# Uses pip with extra-index-url for JFrog (same as Dockerfile)
#
# Usage:
#   source ./setup-local-pip.sh

# Check if script is being sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "ERROR: This script must be sourced, not executed"
    echo "Usage: source ./setup-local-pip.sh"
    exit 1
fi

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Spot Story Local Development Setup (pip) ===${NC}"

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

# Export credentials
export JFROG_USERNAME
export JFROG_TOKEN

echo -e "${GREEN}✓ JFrog credentials configured${NC}"
echo -e "  Username: ${JFROG_USERNAME:0:3}*** (${#JFROG_USERNAME} chars)"
echo -e "  Token: *** (${#JFROG_TOKEN} chars)"

# Check if virtual environment exists
if [[ ! -d ".venv" ]]; then
    echo -e "\n${BLUE}Creating virtual environment...${NC}"
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "\n${BLUE}Activating virtual environment...${NC}"
source .venv/bin/activate

echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Install dependencies using pip with JFrog authentication
echo -e "\n${BLUE}Installing dependencies with pip...${NC}"
JFROG_INDEX="https://${JFROG_USERNAME}:${JFROG_TOKEN}@tr1.jfrog.io/artifactory/api/pypi/pypi/simple"

if ! pip install -e . \
    --index-url https://pypi.org/simple \
    --extra-index-url "$JFROG_INDEX"; then
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
echo -e "${YELLOW}Re-run 'source ./setup-local-pip.sh' in new terminal sessions${NC}"
