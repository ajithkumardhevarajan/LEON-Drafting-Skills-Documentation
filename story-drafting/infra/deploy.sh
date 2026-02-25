#!/usr/bin/env bash

# Comprehensive deployment script for MCP servers to AWS ECS
# Handles ECR repository creation, image building, pushing, and CDK deployment

set -e

# Colors for output
RED='\e[31m'
GREEN='\e[32m'
BLUE='\e[34m'
YELLOW='\e[33m'
NC='\e[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse command line arguments FIRST (before ANY output or config loading)
# Usage: ./deploy.sh [COMMAND] [ENVIRONMENT] [IMAGE_TAG]
COMMAND=${1:-"deploy"}
ENVIRONMENT=${2:-"dev"}
IMAGE_TAG=${3:-""}

# Handle version command immediately (no output, just version number)
if [[ "$COMMAND" == "version" ]]; then
    cd "$SCRIPT_DIR"
    VERSION_FILE="$SCRIPT_DIR/VERSION"
    if [[ ! -f "$VERSION_FILE" ]]; then
        echo "latest"
        exit 0
    fi

    MAJOR_MINOR=$(cat "$VERSION_FILE" | tr -d '[:space:]' | sed 's/\.x$//')
    if [[ ! "$MAJOR_MINOR" =~ ^[0-9]+\.[0-9]+$ ]]; then
        echo "latest"
        exit 0
    fi

    MAJOR=$(echo "$MAJOR_MINOR" | cut -d. -f1)
    MINOR=$(echo "$MAJOR_MINOR" | cut -d. -f2)

    # Get git commit SHA (short form)
    # In CodeBuild, use environment variable; otherwise use git command
    if [[ -n "$CODEBUILD_RESOLVED_SOURCE_VERSION" ]]; then
        # CodeBuild provides the full commit SHA
        GIT_SHA=$(echo "$CODEBUILD_RESOLVED_SOURCE_VERSION" | cut -c1-7)
        DIRTY_SUFFIX=""  # CodeBuild always builds from clean commits
    else
        cd "$MCP_ROOT"
        GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
        DIRTY_SUFFIX=""
        if ! git diff-index --quiet HEAD -- 2>/dev/null; then
            DIRTY_SUFFIX="-dirty"
        fi
        cd "$SCRIPT_DIR"
    fi

    # Note: Can't query ECR without loading config, so just use git-based version
    echo "v${MAJOR}.${MINOR}.0-${GIT_SHA}${DIRTY_SUFFIX}"
    exit 0
fi

# Export environment for Python config and CDK
export DEPLOYMENT_ENV="$ENVIRONMENT"

echo -e "${BLUE}=== MCP Server Deployment Script ===${NC}"
echo -e "Script directory: ${BLUE}$SCRIPT_DIR${NC}"
echo -e "MCP root directory: ${BLUE}$MCP_ROOT${NC}"

# Load configuration from Python config
echo -e "\n${BLUE}Loading configuration...${NC}"
cd "$SCRIPT_DIR"

CONFIG_VALUES=$(python3 -c "
from config import CONFIG
print(f'AWS_ACCOUNT={CONFIG.aws_account}')
print(f'AWS_REGION={CONFIG.aws_region}')
print(f'AWS_PROFILE={CONFIG.aws_profile}')
print(f'ECR_REPO={CONFIG.ecr_repository_name}')
print(f'MCP_NAME={CONFIG.mcp_name}')
print(f'SERVICE_NAME={CONFIG.service_name}')
print(f'STACK_NAME={CONFIG.get_stack_name()}')
print(f'DEFAULT_TAG={CONFIG.default_image_tag}')
print(f'CPU={CONFIG.cpu}')
print(f'MEMORY={CONFIG.memory_mib}')
print(f'DESIRED_COUNT={CONFIG.desired_count}')
print(f'MIN_CAPACITY={CONFIG.min_capacity}')
print(f'MAX_CAPACITY={CONFIG.max_capacity}')
")

if [[ $? -ne 0 ]]; then
    echo -e "${RED}ERROR:${NC} Failed to load configuration from config.py"
    exit 1
fi

# Parse configuration
eval "$CONFIG_VALUES"

echo -e "Configuration:"
echo -e "  MCP Name: ${BLUE}$MCP_NAME${NC}"
echo -e "  Service: ${BLUE}$SERVICE_NAME${NC}"
echo -e "  Stack: ${BLUE}$STACK_NAME${NC}"
echo -e "  ECR Repository: ${BLUE}$ECR_REPO${NC}"
echo -e "  AWS Account: ${BLUE}$AWS_ACCOUNT${NC}"
echo -e "  AWS Region: ${BLUE}$AWS_REGION${NC}"
echo -e "  AWS Profile: ${BLUE}$AWS_PROFILE${NC}"
echo -e "\n${BLUE}Environment-specific settings:${NC}"
echo -e "  CPU: ${BLUE}${CPU}${NC}"
echo -e "  Memory: ${BLUE}${MEMORY} MiB${NC}"
echo -e "  Desired Count: ${BLUE}${DESIRED_COUNT}${NC}"
echo -e "  Auto Scaling: ${BLUE}${MIN_CAPACITY}-${MAX_CAPACITY} tasks${NC}"

# Set AWS profile for all AWS CLI commands (only if not in CodeBuild)
# CodeBuild uses IAM role credentials automatically
if [[ -z "$CODEBUILD_BUILD_ID" ]]; then
    export AWS_PROFILE="$AWS_PROFILE"
    echo -e "\n${BLUE}Using AWS Profile: $AWS_PROFILE${NC}"
else
    echo -e "\n${BLUE}Running in CodeBuild - using IAM role credentials${NC}"
fi

# Function to get next version from VERSION file, ECR, and git
get_next_version() {
    VERSION_FILE="$SCRIPT_DIR/VERSION"
    MAJOR_MINOR=$(cat "$VERSION_FILE" | tr -d '[:space:]' | sed 's/\.x$//')

    # Validate format
    if [[ ! "$MAJOR_MINOR" =~ ^[0-9]+\.[0-9]+$ ]]; then
        echo "Error: VERSION file must contain MAJOR.MINOR or MAJOR.MINOR.x" >&2
        exit 1
    fi

    MAJOR=$(echo "$MAJOR_MINOR" | cut -d. -f1)
    MINOR=$(echo "$MAJOR_MINOR" | cut -d. -f2)

    # Get git commit SHA (short form)
    # In CodeBuild, use environment variable; otherwise use git command
    if [[ -n "$CODEBUILD_RESOLVED_SOURCE_VERSION" ]]; then
        # CodeBuild provides the full commit SHA
        GIT_SHA=$(echo "$CODEBUILD_RESOLVED_SOURCE_VERSION" | cut -c1-7)
        DIRTY_SUFFIX=""  # CodeBuild always builds from clean commits
    else
        cd "$MCP_ROOT"
        GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

        # Check if working tree is dirty (has uncommitted changes)
        DIRTY_SUFFIX=""
        if ! git diff-index --quiet HEAD -- 2>/dev/null; then
            DIRTY_SUFFIX="-dirty"
        fi

        cd "$SCRIPT_DIR"
    fi

    # Query ECR for existing tags
    TAGS=$(aws ecr list-images --repository-name "$ECR_REPO" \
        --query 'imageIds[*].imageTag' --output text 2>/dev/null || echo "")

    # Find latest in current series (matches v0.1.X-sha or v0.1.X-sha-dirty format)
    SERIES_PATTERN="^v${MAJOR}\.${MINOR}\.[0-9]+(-[a-f0-9]+)?(-dirty)?$"
    LATEST=$(echo "$TAGS" | tr '\t' '\n' | grep -E "$SERIES_PATTERN" | sort -V | tail -n 1)

    if [ -z "$LATEST" ]; then
        echo "v${MAJOR}.${MINOR}.0-${GIT_SHA}${DIRTY_SUFFIX}"
    else
        # Extract just the semantic version part (before any dash)
        PATCH=$(echo "$LATEST" | sed 's/^v//' | sed 's/-.*//' | cut -d. -f3)
        echo "v${MAJOR}.${MINOR}.$((PATCH + 1))-${GIT_SHA}${DIRTY_SUFFIX}"
    fi
}

# Command and environment already parsed at the beginning of the script

case "$COMMAND" in
    "help"|"-h"|"--help")
        echo -e "\n${BLUE}Usage:${NC}"
        echo -e "  $0 [COMMAND] [ENVIRONMENT] [IMAGE_TAG]"
        echo -e "\n${BLUE}Commands:${NC}"
        echo -e "  ${GREEN}deploy${NC}     - Full deployment (build, push, deploy) [default]"
        echo -e "  ${GREEN}build${NC}      - Build Docker image only"
        echo -e "  ${GREEN}push${NC}       - Push existing image to ECR"
        echo -e "  ${GREEN}cdk-deploy${NC} - Deploy using CDK only (assumes image exists)"
        echo -e "  ${GREEN}cdk-diff${NC}   - Show CDK diff without deploying"
        echo -e "  ${GREEN}cdk-bootstrap${NC} - Bootstrap CDK environment"
        echo -e "  ${GREEN}cdk-destroy${NC} - Destroy the CDK stack"
        echo -e "  ${GREEN}create-ecr${NC} - Create ECR repository"
        echo -e "  ${GREEN}status${NC}     - Show deployment status"
        echo -e "  ${GREEN}version${NC}    - Output next version number only"
        echo -e "  ${GREEN}help${NC}       - Show this help"
        echo -e "\n${BLUE}Environments:${NC}"
        echo -e "  dev (default), qa, staging, prod"
        echo -e "\n${BLUE}Examples:${NC}"
        echo -e "  $0 deploy              # Deploy to dev with auto-versioned tag (e.g., v0.1.0-a7f3b2c)"
        echo -e "  $0 deploy dev          # Deploy to dev with auto-versioned tag"
        echo -e "  $0 deploy qa           # Deploy to qa with auto-versioned tag"
        echo -e "  $0 deploy prod v0.1.5-a7f3b2c  # Deploy to prod with specific tag (rollback)"
        echo -e "  $0 status              # Show VERSION file and available tags"
        echo -e "  $0 cdk-diff dev        # Show diff for dev environment"
        echo -e "\n${BLUE}Versioning:${NC}"
        echo -e "  Version format: vMAJOR.MINOR.PATCH-GITSHA (e.g., v0.1.5-a7f3b2c)"
        echo -e "  Uncommitted changes add '-dirty' suffix (e.g., v0.1.5-a7f3b2c-dirty)"
        echo -e "  Auto-computed from VERSION file (0.1.x), ECR tags, and git status"
        echo -e "  Each deployment creates an immutable tag with code traceability"
        echo -e "  Override by providing explicit tag: $0 deploy dev v0.1.5-a7f3b2c"
        exit 0
        ;;
esac

# Auto-compute version for build/push/deploy if not provided
# For cdk-deploy, IMAGE_TAG should come from environment variable (set by buildspec) or command line arg
if [[ -z "$IMAGE_TAG" && ("$COMMAND" == "deploy" || "$COMMAND" == "build" || "$COMMAND" == "push") ]]; then
    echo -e "\n${BLUE}Auto-computing next version...${NC}"
    IMAGE_TAG=$(get_next_version)
    echo -e "Computed version: ${GREEN}$IMAGE_TAG${NC}"
elif [[ -z "$IMAGE_TAG" && "$COMMAND" == "cdk-deploy" ]]; then
    # For cdk-deploy, try to get from DEFAULT_TAG, but warn if empty
    IMAGE_TAG="$DEFAULT_TAG"
    if [[ -z "$IMAGE_TAG" ]]; then
        echo -e "${YELLOW}WARNING:${NC} IMAGE_TAG not provided and DEFAULT_TAG is empty"
        echo -e "  For pipeline: ensure IMAGE_TAG environment variable is set in buildspec"
        echo -e "  For local: provide image tag as third argument: ./deploy.sh cdk-deploy <env> <tag>"
        echo -e "${RED}ERROR:${NC} Cannot proceed without IMAGE_TAG"
        exit 1
    fi
elif [[ -z "$IMAGE_TAG" ]]; then
    IMAGE_TAG="$DEFAULT_TAG"
fi

echo -e "\nCommand: ${GREEN}$COMMAND${NC}"
echo -e "Environment: ${GREEN}$ENVIRONMENT${NC}"
echo -e "Image Tag: ${GREEN}$IMAGE_TAG${NC}"

# Function to check if ECR repository exists
check_ecr_repo() {
    echo -e "\n${BLUE}Checking ECR repository...${NC}"
    if aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$AWS_REGION" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ ECR repository exists: $ECR_REPO${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ ECR repository does not exist: $ECR_REPO${NC}"
        return 1
    fi
}

# Function to create ECR repository
create_ecr_repo() {
    echo -e "\n${BLUE}Creating ECR repository...${NC}"
    aws ecr create-repository \
        --repository-name "$ECR_REPO" \
        --region "$AWS_REGION" \
        --image-tag-mutability MUTABLE \
        --image-scanning-configuration scanOnPush=true \
        --tags "Key=Skill-Name,Value=$MCP_NAME" "Key=Service-Type,Value=Leon-Skill" >/dev/null

    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✓ ECR repository created: $ECR_REPO${NC}"
    else
        echo -e "${RED}ERROR:${NC} Failed to create ECR repository"
        exit 1
    fi
}

# Function to build Docker image
build_image() {
    echo -e "\n${BLUE}Building Docker image...${NC}"

    # Build from repository root (parent of MCP_ROOT) so Dockerfile can access both shared/ and story-drafting/
    REPO_ROOT="$(dirname "$MCP_ROOT")"
    cd "$REPO_ROOT"

    # Pass JFrog credentials as build args (required for private packages)
    if [[ -z "${JFROG_USERNAME:-}" || -z "${JFROG_TOKEN:-}" ]]; then
        echo -e "${RED}ERROR:${NC} JFROG_USERNAME and JFROG_TOKEN must be set for private package access"
        echo -e "  This build requires private package: reuters-ai-assistant-mcp-hitl"
        echo -e "\n  Current credential status:"
        echo -e "    JFROG_USERNAME: $([ -n "${JFROG_USERNAME:-}" ] && echo "SET (length: ${#JFROG_USERNAME})" || echo "NOT SET")"
        echo -e "    JFROG_TOKEN: $([ -n "${JFROG_TOKEN:-}" ] && echo "SET (length: ${#JFROG_TOKEN})" || echo "NOT SET")"
        echo -e "\n  For pipeline builds:"
        echo -e "    Ensure parameter-store is configured in buildspec.yml"
        echo -e "    Check SSM parameters: /a207920/leon-skills/jfrog/username and /a207920/leon-skills/jfrog/token"
        echo -e "\n  For local builds:"
        echo -e "    export JFROG_USERNAME=\$(aws ssm get-parameter --name '/a207920/leon-skills/jfrog/username' --with-decryption --query 'Parameter.Value' --output text)"
        echo -e "    export JFROG_TOKEN=\$(aws ssm get-parameter --name '/a207920/leon-skills/jfrog/token' --with-decryption --query 'Parameter.Value' --output text)"
        exit 1
    fi

    echo -e "${BLUE}Using JFrog credentials for private package access${NC}"
    echo -e "  Username: ${JFROG_USERNAME:0:3}*** (${#JFROG_USERNAME} chars)"
    echo -e "  Token: *** (${#JFROG_TOKEN} chars)"
    docker build --platform linux/arm64 \
        --build-arg JFROG_USERNAME="$JFROG_USERNAME" \
        --build-arg JFROG_TOKEN="$JFROG_TOKEN" \
        -f story-drafting/Dockerfile \
        -t "$ECR_REPO:$IMAGE_TAG" .
    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✓ Image built successfully${NC}"
    else
        echo -e "${RED}ERROR:${NC} Failed to build Docker image"
        exit 1
    fi
}

# Function to push image to ECR
push_image() {
    echo -e "\n${BLUE}Pushing image to ECR...${NC}"

    # ECR login
    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com"
    if [[ $? -ne 0 ]]; then
        echo -e "${RED}ERROR:${NC} Failed to login to ECR"
        exit 1
    fi

    # Tag and push
    ECR_URI="$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"
    docker tag "$ECR_REPO:$IMAGE_TAG" "$ECR_URI"
    docker push "$ECR_URI"

    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✓ Image pushed successfully: $ECR_URI${NC}"
    else
        echo -e "${RED}ERROR:${NC} Failed to push image"
        exit 1
    fi
}

# Function to deploy with CDK
cdk_deploy() {
    echo -e "\n${BLUE}Deploying with CDK...${NC}"
    cd "$SCRIPT_DIR"

    # Install dependencies if needed
    if [[ ! -d ".venv" ]]; then
        echo -e "${BLUE}Creating Python virtual environment...${NC}"
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -r requirements.txt
    else
        source .venv/bin/activate
    fi

    # Deploy with CDK
    export IMAGE_TAG="$IMAGE_TAG"
    cdk deploy --require-approval never

    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✓ CDK deployment successful${NC}"
    else
        echo -e "${RED}ERROR:${NC} CDK deployment failed"
        exit 1
    fi
}

# Function to show CDK diff
cdk_diff() {
    echo -e "\n${BLUE}Showing CDK diff...${NC}"
    cd "$SCRIPT_DIR"

    if [[ ! -d ".venv" ]]; then
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -r requirements.txt
    else
        source .venv/bin/activate
    fi

    export IMAGE_TAG="$IMAGE_TAG"
    cdk diff
}

# Function to bootstrap CDK
cdk_bootstrap() {
    echo -e "\n${BLUE}Bootstrapping CDK environment...${NC}"
    cd "$SCRIPT_DIR"

    if [[ ! -d ".venv" ]]; then
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -r requirements.txt
    else
        source .venv/bin/activate
    fi

    # Get asset_id from config
    ASSET_ID=$(python3 -c "from config import CONFIG; print(CONFIG.asset_id)")

    # Bootstrap once for all leon-skills (shared by all skills)
    # No environment suffix - creates default bootstrap for account/region
    # All skills use deployment_env=None and share this bootstrap
    echo -e "${YELLOW}This will create a shared bootstrap for all leon-skills${NC}"
    echo -e "${YELLOW}Account: $AWS_ACCOUNT, Region: $AWS_REGION${NC}"
    read -p "Continue? (y/n): " -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Bootstrap cancelled${NC}"
        exit 0
    fi

    # Use PRODUCTION environment type for prod environments, DEVELOPMENT for all others
    if [[ "$ENVIRONMENT" == prod* ]]; then
        ENV_TYPE="PRODUCTION"
    else
        ENV_TYPE="DEVELOPMENT"
    fi

    trcdk bootstrap aws://$AWS_ACCOUNT/$AWS_REGION \
        --asset-id "$ASSET_ID" \
        --resource-owner "iridium@trten.onmicrosoft.com" \
        --environment-type "$ENV_TYPE"

    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✓ CDK environment bootstrapped successfully${NC}"
    else
        echo -e "${RED}ERROR:${NC} CDK bootstrap failed"
        exit 1
    fi
}

# Function to destroy CDK stack
cdk_destroy() {
    echo -e "\n${YELLOW}⚠ This will destroy the entire stack!${NC}"
    echo -e "Stack name: ${RED}$STACK_NAME${NC}"
    echo -e "\nAre you sure? Type 'yes' to confirm:"
    read -r confirmation

    if [[ "$confirmation" != "yes" ]]; then
        echo -e "${BLUE}Deployment destruction cancelled.${NC}"
        exit 0
    fi

    cd "$SCRIPT_DIR"
    if [[ ! -d ".venv" ]]; then
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -r requirements.txt
    else
        source .venv/bin/activate
    fi

    cdk destroy --force
}

# Function to show deployment status
show_status() {
    echo -e "\n${BLUE}Deployment Status${NC}"
    echo -e "=================="

    # Show VERSION file content
    VERSION_FILE="$SCRIPT_DIR/VERSION"
    if [[ -f "$VERSION_FILE" ]]; then
        VERSION_CONTENT=$(cat "$VERSION_FILE" | tr -d '[:space:]')
        echo -e "VERSION file: ${GREEN}$VERSION_CONTENT${NC}"

        # Show what the next version would be
        NEXT_VERSION=$(get_next_version 2>/dev/null || echo "N/A")
        echo -e "Next version: ${GREEN}$NEXT_VERSION${NC}"
    else
        echo -e "VERSION file: ${YELLOW}NOT FOUND${NC}"
    fi

    echo ""

    # Check ECR repository
    if check_ecr_repo >/dev/null 2>&1; then
        echo -e "ECR Repository: ${GREEN}✓ EXISTS${NC}"

        # Check for images
        IMAGES=$(aws ecr list-images --repository-name "$ECR_REPO" --region "$AWS_REGION" --query 'imageIds[*].imageTag' --output text 2>/dev/null)
        if [[ -n "$IMAGES" ]]; then
            # Parse VERSION file to get current series
            VERSION_FILE="$SCRIPT_DIR/VERSION"
            if [[ -f "$VERSION_FILE" ]]; then
                MAJOR_MINOR=$(cat "$VERSION_FILE" | tr -d '[:space:]' | sed 's/\.x$//')
                MAJOR=$(echo "$MAJOR_MINOR" | cut -d. -f1)
                MINOR=$(echo "$MAJOR_MINOR" | cut -d. -f2)

                # Filter and sort tags for current series (matches v0.1.X-sha or v0.1.X-sha-dirty)
                SERIES_PATTERN="^v${MAJOR}\.${MINOR}\.[0-9]+(-[a-f0-9]+)?(-dirty)?$"
                SERIES_TAGS=$(echo "$IMAGES" | tr '\t' '\n' | grep -E "$SERIES_PATTERN" | sort -V)

                if [[ -n "$SERIES_TAGS" ]]; then
                    echo -e "Tags in current series (${MAJOR}.${MINOR}.x):"
                    echo "$SERIES_TAGS" | sed 's/^/  /'

                    LATEST_SERIES=$(echo "$SERIES_TAGS" | tail -n 1)
                    echo -e "Latest: ${GREEN}$LATEST_SERIES${NC}"
                else
                    echo -e "Tags in current series: ${YELLOW}None yet${NC}"
                fi

                # Show all tags for reference
                echo -e "\nAll available tags:"
                echo "$IMAGES" | tr '\t' '\n' | sort -V | sed 's/^/  /'
            else
                echo -e "Available Tags: ${GREEN}$IMAGES${NC}"
            fi
        else
            echo -e "Available Tags: ${YELLOW}None${NC}"
        fi
    else
        echo -e "ECR Repository: ${RED}✗ NOT FOUND${NC}"
    fi

    echo ""

    # Check CDK stack
    cd "$SCRIPT_DIR"
    if [[ -d ".venv" ]]; then
        source .venv/bin/activate
        STACK_STATUS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")
        echo -e "CDK Stack: ${GREEN}$STACK_STATUS${NC}"
    else
        echo -e "CDK Stack: ${YELLOW}UNKNOWN (no .venv)${NC}"
    fi
}

# Main execution logic
case "$COMMAND" in
    "create-ecr")
        create_ecr_repo
        ;;
    "build")
        build_image
        ;;
    "push")
        check_ecr_repo || create_ecr_repo
        push_image
        ;;
    "cdk-deploy")
        cdk_deploy
        ;;
    "cdk-diff")
        cdk_diff
        ;;
    "cdk-bootstrap")
        cdk_bootstrap
        ;;
    "cdk-destroy")
        cdk_destroy
        ;;
    "status")
        show_status
        ;;
    "deploy")
        echo -e "\n${BLUE}Starting full deployment...${NC}"
        check_ecr_repo || create_ecr_repo
        build_image
        push_image
        cdk_deploy
        echo -e "\n${GREEN}🎉 Deployment completed successfully!${NC}"
        echo -e "\nTo check status: ${YELLOW}$0 status${NC}"
        ;;
    *)
        echo -e "${RED}ERROR:${NC} Unknown command: $COMMAND"
        echo -e "Use ${YELLOW}$0 help${NC} to see available commands"
        exit 1
        ;;
esac
