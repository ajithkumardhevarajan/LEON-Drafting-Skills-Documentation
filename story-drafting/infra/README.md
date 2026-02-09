# Story Drafting Infrastructure

AWS CDK infrastructure for deploying the story-drafting MCP skill to ECS with Application Load Balancer.

## Overview

This infrastructure deploys the story-drafting skill as a containerized service on AWS ECS Fargate, fronted by an Application Load Balancer. It includes:

- **ECS Cluster & Service**: Runs the MCP server containers
- **Application Load Balancer**: Distributes traffic to ECS tasks
- **Auto-scaling**: CPU and memory-based scaling
- **Secrets Management**: Integration with AWS Secrets Manager
- **CloudWatch Logs**: Centralized logging
- **SSM Parameters**: Service discovery and configuration

## Prerequisites

1. **AWS Account Access**: Access to account 060725138335 with profile `tr-central-preprod`
2. **JFrog Credentials**: Set as environment variables or SSM parameters
3. **CDK Bootstrap**: One-time bootstrap for the account/region (shared by all skills)
4. **Docker**: For building container images locally
5. **Python 3.11+**: For running CDK

## Configuration

All configuration is managed in `config.py`:

```python
ENVIRONMENT_CONFIGS = {
    "dev": {
        "aws_account": "060725138335",
        "cpu": 512,
        "memory_mib": 1024,
        "desired_count": 1,
        "min_capacity": 1,
        "max_capacity": 3,
    },
    "qa": {
        "aws_account": "060725138335",
        "cpu": 1024,
        "memory_mib": 2048,
        "desired_count": 2,
        "min_capacity": 2,
        "max_capacity": 5,
    }
}
```

## Deployment Script

The `deploy.sh` script handles the complete deployment workflow:

```bash
./deploy.sh [COMMAND] [ENVIRONMENT] [IMAGE_TAG]
```

### Commands

- `deploy` - Full deployment (build, push, deploy) [default]
- `build` - Build Docker image only
- `push` - Push existing image to ECR
- `cdk-deploy` - Deploy using CDK only (assumes image exists)
- `cdk-diff` - Show CDK diff without deploying
- `cdk-bootstrap` - Bootstrap CDK environment (one-time)
- `cdk-destroy` - Destroy the CDK stack
- `create-ecr` - Create ECR repository
- `status` - Show deployment status
- `version` - Output next version number only

### Environments

- `dev` - Development environment (default)
- `qa` - QA environment
- `staging` - Staging environment (planned)
- `prod` - Production environment (planned)

## Deployment Workflow

### First-Time Setup

```bash
# 1. Bootstrap CDK (one-time, shared by all skills)
./deploy.sh cdk-bootstrap dev

# 2. Set JFrog credentials (for building images)
export JFROG_USERNAME=$(aws ssm get-parameter --name '/a207920/leon-skills/jfrog/username' --with-decryption --query 'Parameter.Value' --output text)
export JFROG_TOKEN=$(aws ssm get-parameter --name '/a207920/leon-skills/jfrog/token' --with-decryption --query 'Parameter.Value' --output text)
```

### Regular Deployment

```bash
# Deploy to dev (auto-versioned)
./deploy.sh deploy dev

# Deploy to qa (auto-versioned)
./deploy.sh deploy qa

# Deploy specific version to prod
./deploy.sh deploy prod v0.1.5-a7f3b2c
```

### Development Workflow

```bash
# Build image locally
./deploy.sh build dev

# Show CDK diff before deploying
./deploy.sh cdk-diff dev

# Deploy only CDK changes (reuse existing image)
./deploy.sh cdk-deploy dev

# Check deployment status
./deploy.sh status dev
```

## Versioning

The deployment uses semantic versioning with git SHA tracking:

- **Format**: `vMAJOR.MINOR.PATCH-GITSHA` (e.g., `v0.1.5-a7f3b2c`)
- **VERSION file**: Contains `0.1.x` indicating the current major.minor series
- **Auto-increment**: Patch version auto-increments from ECR tags
- **Git tracking**: Includes short git SHA for traceability
- **Dirty builds**: Adds `-dirty` suffix for uncommitted changes

Example:
```bash
# VERSION file contains: 0.1.x
# Latest ECR tag: v0.1.4-abc1234
# Current git SHA: a7f3b2c
# Working tree clean
# Next version: v0.1.5-a7f3b2c
```

## Infrastructure Resources

### Naming Convention

Resources use the TR CDK naming pattern:
- **Prefix**: `a207920-spx-` (asset ID + sphinx project)
- **Pattern**: `{prefix}{environment}-{service}-{resource-type}`

Examples:
- Cluster: `a207920-spx-dev-story-drafting-cluster`
- Service: `a207920-spx-dev-story-drafting-service`
- ALB: `a207920-spx-dev-story-drafting-alb`
- Task: `a207920-spx-dev-story-drafting-task`

### Created Resources

1. **ECS Cluster**: Container orchestration
2. **ECS Service**: Manages task lifecycle
3. **Fargate Task Definition**: Container specification
4. **Application Load Balancer**: Traffic distribution
5. **Target Group**: Health-checked ECS tasks
6. **CloudWatch Log Group**: `/aws/ecs/a207920-spx-{env}-story-drafting-service`
7. **IAM Roles**: Task execution and task roles
8. **SSM Parameters**:
   - `/a207920/story-drafting/{env}/alb-dns`
   - `/a207920/story-drafting/{env}/service-url`
   - `/a207920/story-drafting/{env}/service-arn`

## Secrets Management

The skill uses AWS Secrets Manager for sensitive credentials:

**Secret ARN**: `arn:aws:secretsmanager:eu-west-1:060725138335:secret:a207920-leon-skills-vWvmX7`

**Secret Keys**:
- `ORCHESTRATOR_ENDPOINT`
- `ORCHESTRATOR_API_VERSION`
- `LEON_ORCHESTRATOR_TENANT_ID`
- `LEON_ORCHESTRATOR_CLIENT_ID`
- `LEON_ORCHESTRATOR_CLIENT_SECRET`
- `LEON_ORCHESTRATOR_RESOURCE`
- `LEON_ORCHESTRATOR_API_KEY`
- `ORCHESTRATOR_DEPLOYMENT_GPT4_1`

These secrets are injected into ECS containers at runtime.

## Monitoring

### CloudWatch Logs

```bash
# View logs via AWS CLI
aws logs tail /aws/ecs/a207920-spx-dev-story-drafting-service --follow

# Or use AWS Console
# CloudWatch > Log groups > /aws/ecs/a207920-spx-dev-story-drafting-service
```

### Health Checks

```bash
# Get ALB DNS name
ALB_DNS=$(aws ssm get-parameter --name '/a207920/story-drafting/dev/alb-dns' --query 'Parameter.Value' --output text)

# Check health endpoint
curl http://$ALB_DNS/health

# Check readiness
curl http://$ALB_DNS/ready
```

### ECS Service Status

```bash
# View service in AWS Console
# ECS > Clusters > a207920-spx-dev-story-drafting-cluster > Services

# Or via AWS CLI
aws ecs describe-services \
  --cluster a207920-spx-dev-story-drafting-cluster \
  --services a207920-spx-dev-story-drafting-service
```

## Troubleshooting

### Image Build Fails

```bash
# Ensure JFrog credentials are set
echo $JFROG_USERNAME
echo $JFROG_TOKEN

# Build with verbose output
docker build --platform linux/arm64 \
  --build-arg JFROG_USERNAME="$JFROG_USERNAME" \
  --build-arg JFROG_TOKEN="$JFROG_TOKEN" \
  --progress=plain -t story-drafting-test .
```

### CDK Deployment Fails

```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify bootstrap exists
aws cloudformation describe-stacks --stack-name CDKToolkit

# View CDK diff to see what changed
./deploy.sh cdk-diff dev
```

### ECS Tasks Not Starting

1. Check CloudWatch Logs for startup errors
2. Verify secrets exist in Secrets Manager
3. Check IAM role permissions
4. Ensure ECR image exists with correct tag

### Health Check Failures

1. Verify container port (8004) matches config
2. Check if application started correctly in logs
3. Ensure security groups allow ALB -> ECS traffic
4. Verify health endpoint returns 200 status

## Cleanup

```bash
# Destroy the stack (interactive confirmation)
./deploy.sh cdk-destroy dev

# Manually delete ECR images if needed
aws ecr batch-delete-image \
  --repository-name a207920/story-drafting-skill/dev \
  --image-ids imageTag=v0.1.5-a7f3b2c
```

## CI/CD Integration

The infrastructure is designed for AWS CodeBuild/CodePipeline integration:

1. **Build Phase**: Runs `deploy.sh build` with JFrog credentials from SSM
2. **Push Phase**: Runs `deploy.sh push` to ECR
3. **Deploy Phase**: Runs `deploy.sh cdk-deploy` with `IMAGE_TAG` environment variable

See `buildspec.yml` (if present) for CI/CD configuration.

## Support

For questions or issues:
- Check CloudWatch Logs for application errors
- Review ECS service events in AWS Console
- Verify configuration in `config.py`
- Contact the Iridium team for infrastructure support
