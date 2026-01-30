# Urgent Drafting MCP - Deployment Infrastructure

Per-skill AWS ECS deployment infrastructure for urgent-drafting MCP server.

## Architecture

- **Pattern**: Per-skill infrastructure (self-contained)
- **Platform**: AWS ECS Fargate behind Application Load Balancer (ALB)
- **Framework**: AWS CDK with TR CDK Library (tr-cdk-lib)
- **Region**: eu-west-1 (Ireland)
- **Account**: 060725138335 (tr-central-preprod)
- **Asset ID**: 207920

## Infrastructure Files

```
infra/
├── app.py              # CDK app entry point
├── config.py           # Skill configuration
├── mcp_stack.py        # ECS stack definition
├── deploy.sh           # Deployment script
├── cdk.json            # CDK configuration
└── requirements.txt    # Python dependencies
```

## Configuration

Edit `config.py` to customize the deployment:

- **Service naming**: `urg-draft` (short name to avoid ALB 32-char limit)
- **Service full name**: `urgent-drafting` (for display/logs)
- **ECR repository**: Separate per environment
  - Dev: `a207920/urgent-drafting-skill/dev`
  - QA: `a207920/urgent-drafting-skill/qa`
  - Staging: `a207920/urgent-drafting-skill/staging`
  - Prod: `a207920/urgent-drafting-skill/prod`
- **Resource prefix**: `a207920` (includes asset ID)
- **Container port**: 8000
- **CPU**: 512 units
- **Memory**: 1024 MiB
- **Auto-scaling**: 1-5 tasks (70% CPU/memory target)
- **ALB**: Internal (not public)

## Versioning Strategy

This deployment uses **hybrid semantic versioning with git traceability**:

### Version Format
```
vMAJOR.MINOR.PATCH-GITSHA[-dirty]
```

**Examples:**
- `v0.1.0-a7f3b2c` - Clean build from git commit a7f3b2c
- `v0.1.1-b4e2f91` - Clean build from git commit b4e2f91
- `v0.1.2-b4e2f91-dirty` - Build from b4e2f91 with uncommitted changes

### How It Works

1. **VERSION File** (`infra/VERSION`): Contains `MAJOR.MINOR.x` (e.g., `0.1.x`)
2. **Auto-increment**: Patch version auto-increments by querying ECR for existing tags
3. **Git SHA**: Appends short commit hash for code traceability
4. **Dirty Flag**: Adds `-dirty` suffix when deploying with uncommitted changes

### Benefits

- ✅ **Human-readable**: Semantic versioning shows deployment progression
- ✅ **Traceable**: Git SHA pinpoints exact code deployed
- ✅ **Immutable**: Each deployment gets a unique tag
- ✅ **Rollback-friendly**: Deploy any previous version by tag
- ✅ **Environment-independent**: Separate ECR repos per environment prevent version conflicts

### Version Control

```bash
# Check current version and next version
./deploy.sh status

# Output shows:
# VERSION file: 0.1.x
# Next version: v0.1.5-a7f3b2c
# Latest: v0.1.4-xyz1234
```

To bump major or minor version:
```bash
# Edit infra/VERSION file
echo "0.2.x" > infra/VERSION

# Next deployment will be v0.2.0-<sha>
./deploy.sh deploy dev
```

## Deployment Commands

### First-Time Setup

```bash
cd infra

# Bootstrap CDK environment (ONCE for all leon-skills)
# This creates dedicated bootstrap resources with "leon" environment suffix
# All leon MCP skills share these bootstrap resources
# Only run this ONCE, not per skill
./deploy.sh cdk-bootstrap

# Create ECR repository (one-time per environment)
./deploy.sh create-ecr
```

**About Bootstrap:**
- Uses environment suffix "leon-skills" to isolate from other leon resources
- Creates: `a207920-cdk-toolkit-leon-skills-euw1-*` resources
- Shared by ALL MCP skills in this project
- Only run once, regardless of how many skills you deploy

### Full Deployment

```bash
# Deploy to dev with auto-versioned tag (e.g., v0.1.0-a7f3b2c)
./deploy.sh deploy dev

# Deploy to qa with auto-versioned tag
./deploy.sh deploy qa

# Deploy to staging with auto-versioned tag
./deploy.sh deploy staging

# Deploy specific version (rollback)
./deploy.sh deploy dev v0.1.5-a7f3b2c
```

**Note**: Each environment has its own ECR repository, so version numbers are independent per environment.

The `deploy` command performs:
1. Auto-compute version from VERSION file, ECR tags, and git status
2. Build Docker image for linux/arm64
3. Push image to ECR with computed version tag
4. Deploy infrastructure with CDK

### Individual Operations

```bash
# Build Docker image only (auto-versions)
./deploy.sh build

# Build with specific tag
./deploy.sh build v0.1.5-a7f3b2c

# Push existing image to ECR (auto-versions)
./deploy.sh push

# Push with specific tag
./deploy.sh push v0.1.5-a7f3b2c

# Deploy CDK stack only (assumes image exists)
./deploy.sh cdk-deploy dev v0.1.5-a7f3b2c

# Preview infrastructure changes
./deploy.sh cdk-diff dev

# Check deployment status and version info
./deploy.sh status

# Destroy stack (prompts for confirmation)
./deploy.sh cdk-destroy
```

## Resources Created

The stack creates the following AWS resources:

### Compute
- **ECS Cluster**: `a207920-urgent-drafting-cluster`
- **ECS Service**: `a207920-urgent-drafting-service`
- **Fargate Task**: `a207920-urgent-drafting-task`
- **Container Insights**: Enabled

### Networking
- **ALB**: `a207920-urgent-drafting-alb` (internal)
- **Target Group**: With `/health` health checks
- **VPC**: From TR context (shared)

### IAM
- **Task Role**: `a207920-urgent-drafting-task-role`
  - SSM parameter access for configuration
- **Execution Role**: `a207920-urgent-drafting-exec-role`
  - ECR image pull permissions
  - CloudWatch Logs write permissions

### Observability
- **CloudWatch Logs**: `/aws/ecs/a207920-urgent-drafting-service`
- **Retention**: 30 days
- **Container Insights**: Enabled

### Configuration
- **SSM Parameters**:
  - `/a207920/urg-draft/alb-dns` - ALB DNS name
  - `/a207920/urg-draft/service-url` - Service HTTP URL
  - `/a207920/urg-draft/service-arn` - ECS Service ARN

### Auto-Scaling
- **CPU-based**: Target 70% utilization
- **Memory-based**: Target 70% utilization
- **Scale range**: 1-5 tasks
- **Cooldown**: 60 seconds

## Environment Variables

Container environment variables are loaded from:
1. Hardcoded in `config.py`: `MCP_SERVICE_NAME`, `AWS_DEFAULT_REGION`, `MCP_PORT`
2. Optional `.env` file in parent directory (all variables loaded automatically)

Example `.env`:
```bash
ANTHROPIC_API_KEY=sk-...
LOG_LEVEL=info
```

## Naming Convention

All resources include the `a207920` asset ID prefix. Note the use of short name (`urg-draft`) for ALB due to 32-character limit, and full name (`urgent-drafting`) for other resources.

| Resource Type | Pattern | Example |
|--------------|---------|---------|
| ECR | `a207920/{skill}/{env}` | `a207920/urgent-drafting-skill/dev` |
| Image Tag | `vMAJOR.MINOR.PATCH-GITSHA[-dirty]` | `v0.1.5-a7f3b2c` |
| Stack | `a207920-{short-name}-skill-stack` | `a207920-urg-draft-skill-stack` |
| ECS Cluster | `a207920-spx-{env}-{full-name}-cluster` | `a207920-spx-dev-urgent-drafting-cluster` |
| ECS Service | `a207920-spx-{env}-{full-name}-service` | `a207920-spx-dev-urgent-drafting-service` |
| ALB | `a207920-spx-{env}-{short-name}-alb` | `a207920-spx-dev-urg-draft-alb` |
| IAM Roles | `a207920-spx-{env}-{full-name}-{type}-role` | `a207920-spx-dev-urgent-drafting-task-role` |
| SSM Params | `/a207920/{short-name}/{param}` | `/a207920/urg-draft/service-url` |
| CloudWatch | `/aws/ecs/a207920-spx-{env}-{full-name}-service` | `/aws/ecs/a207920-spx-dev-urgent-drafting-service` |

**Note on ECR Repositories:**
- Each environment (dev, qa, staging, prod) has its own ECR repository
- This allows independent versioning per environment
- Dev/QA share preprod AWS account, staging/prod share prod AWS account

## Health Checks

### Container Health Check
- **Command**: `curl -f http://localhost:8000/health || exit 1`
- **Interval**: 30 seconds
- **Timeout**: 5 seconds
- **Retries**: 3
- **Start Period**: 60 seconds

### ALB Target Group Health Check
- **Path**: `/health`
- **Interval**: 30 seconds
- **Timeout**: 5 seconds
- **Healthy Threshold**: 2
- **Unhealthy Threshold**: 3

## Deployment Status

Check deployment status and service information:

```bash
./deploy.sh status
```

This shows:
- **VERSION file**: Current version series (e.g., `0.1.x`)
- **Next version**: What the next deployment will be tagged as (e.g., `v0.1.5-a7f3b2c`)
- **ECR repository**: Existence and status
- **Available tags**:
  - Tags in current version series
  - Latest deployed version
  - All available tags (for rollback reference)
- **CDK stack status**: Current CloudFormation stack state
- **Git status**: Whether working tree is clean or dirty

## Accessing the Service

After deployment, retrieve the service URL:

```bash
# From SSM Parameter
aws ssm get-parameter \
  --name /a207920/urg-draft/service-url \
  --region eu-west-1 \
  --profile tr-central-preprod \
  --query 'Parameter.Value' \
  --output text

# Or from deploy script
./deploy.sh status
```

Test the health endpoint:
```bash
SERVICE_URL=$(aws ssm get-parameter --name /a207920/urg-draft/service-url --region eu-west-1 --profile tr-central-preprod --query 'Parameter.Value' --output text)
curl $SERVICE_URL/health
```

## Rollback and Version Management

### Rolling Back to Previous Version

```bash
# Check available versions
./deploy.sh status

# Deploy specific previous version
./deploy.sh deploy dev v0.1.3-abc1234
```

### Checking What's Deployed

```bash
# Get current deployment version from ECS
aws ecs describe-services \
  --cluster a207920-spx-dev-urgent-drafting-cluster \
  --services a207920-spx-dev-urgent-drafting-service \
  --region eu-west-1 \
  --profile tr-central-preprod \
  --query 'services[0].taskDefinition'

# Extract image tag from task definition
aws ecs describe-task-definition \
  --task-definition <TASK_DEF_ARN> \
  --region eu-west-1 \
  --profile tr-central-preprod \
  --query 'taskDefinition.containerDefinitions[0].image'
```

### Inspecting Code from Version

```bash
# Given version v0.1.5-a7f3b2c, inspect the code
git show a7f3b2c

# See what changed in that commit
git show a7f3b2c --stat

# Compare two deployed versions
git diff abc1234..def5678
```

### Bumping Major/Minor Version

When you want to start a new version series:

```bash
# Edit VERSION file
cd infra
echo "0.2.x" > VERSION

# Next deployment starts new series
./deploy.sh deploy dev  # Creates v0.2.0-<sha>
```

Use cases for version bumps:
- **Patch (auto)**: Bug fixes, small changes, normal deployments
- **Minor (manual)**: New features, API additions, backward-compatible changes
- **Major (manual)**: Breaking changes, major refactors, API redesigns

## Adding a New Skill

To deploy a different skill using this pattern:

1. Create skill folder: `mkdir my-new-skill`
2. Add application code: `Dockerfile`, `src/`, `run.py`, `pyproject.toml`
3. Copy infrastructure: `cp -r urgent-drafting/infra my-new-skill/`
4. Update `my-new-skill/infra/config.py`:
   - Change `mcp_name` and `service_name`
   - Update `ecr_repository_name`
   - Update `ssm_parameter_prefix`
   - Adjust resource sizing if needed
5. Deploy: `cd my-new-skill/infra && ./deploy.sh deploy`

## Troubleshooting

### CDK Synthesis Issues
```bash
cd infra
source .venv/bin/activate
cdk synth
```

### View CloudWatch Logs
```bash
aws logs tail /aws/ecs/a207920-urgent-drafting-service \
  --follow \
  --region eu-west-1 \
  --profile tr-central-preprod
```

### Check ECS Service Events
```bash
aws ecs describe-services \
  --cluster a207920-urgent-drafting-cluster \
  --services a207920-urgent-drafting-service \
  --region eu-west-1 \
  --profile tr-central-preprod \
  --query 'services[0].events[:5]'
```

### Force New Deployment
```bash
aws ecs update-service \
  --cluster a207920-urgent-drafting-cluster \
  --service a207920-urgent-drafting-service \
  --force-new-deployment \
  --region eu-west-1 \
  --profile tr-central-preprod
```

## Tags

All resources are tagged with:
- `tr:application-asset-insight-id`: 207920
- `tr:environment-type`: DEVELOPMENT
- `tr:project-name`: sphinx
- `tr:resource-owner`: iridium@trten.onmicrosoft.com
- `tr:service-name`: sphinx-urgent-drafting-mcp
- `MCP-Name`: urgent-drafting-mcp
- `Service-Type`: MCP-Server
- `Deployment-Method`: CDK

## References

- Based on [story-search-mcp](../../reuters-ai_assistant/sample-mcps/story-search-mcp/infra) pattern
- Uses [TR CDK Library](https://github.com/thomsonreuters/tr-cdk-lib) (v2.11.2)
- AWS CDK v2.161.0
