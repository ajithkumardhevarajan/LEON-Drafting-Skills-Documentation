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

- **Service naming**: `urgent-drafting-mcp`
- **ECR repository**: `a207920/urgent-drafting-mcp/dev`
- **Resource prefix**: `a207920` (includes asset ID)
- **Container port**: 8000
- **CPU**: 512 units
- **Memory**: 1024 MiB
- **Auto-scaling**: 1-5 tasks (70% CPU/memory target)
- **ALB**: Internal (not public)

## Deployment Commands

### First-Time Setup

```bash
cd infra

# Bootstrap CDK environment (ONCE for all leon-skills)
# This creates dedicated bootstrap resources with "leon" environment suffix
# All leon MCP skills share these bootstrap resources
# Only run this ONCE, not per skill
./deploy.sh cdk-bootstrap

# Create ECR repository (one-time per skill)
./deploy.sh create-ecr
```

**About Bootstrap:**
- Uses environment suffix "leon-skills" to isolate from other leon resources
- Creates: `a207920-cdk-toolkit-leon-skills-euw1-*` resources
- Shared by ALL MCP skills in this project
- Only run once, regardless of how many skills you deploy

### Full Deployment

```bash
# Deploy with 'latest' tag (default)
./deploy.sh deploy

# Deploy with specific version tag
./deploy.sh deploy v1.0.0
```

The `deploy` command performs:
1. Build Docker image for linux/amd64
2. Push image to ECR
3. Deploy infrastructure with CDK

### Individual Operations

```bash
# Build Docker image only
./deploy.sh build [tag]

# Push existing image to ECR
./deploy.sh push [tag]

# Deploy CDK stack only (assumes image exists)
./deploy.sh cdk-deploy [tag]

# Preview infrastructure changes
./deploy.sh cdk-diff [tag]

# Check deployment status
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
  - `/a207920/urgent-drafting-mcp/alb-dns` - ALB DNS name
  - `/a207920/urgent-drafting-mcp/service-url` - Service HTTP URL
  - `/a207920/urgent-drafting-mcp/service-arn` - ECS Service ARN

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

All resources include the `a207920` asset ID prefix:

| Resource Type | Pattern | Example |
|--------------|---------|---------|
| ECR | `a207920/{service}/dev` | `a207920/urgent-drafting-mcp/dev` |
| ECS Cluster | `a207920-{service}-cluster` | `a207920-urgent-drafting-cluster` |
| ECS Service | `a207920-{service}-service` | `a207920-urgent-drafting-service` |
| ALB | `a207920-{service}-alb` | `a207920-urgent-drafting-alb` |
| IAM Roles | `a207920-{service}-{type}-role` | `a207920-urgent-drafting-task-role` |
| SSM Params | `/a207920/{service}/{param}` | `/a207920/urgent-drafting-mcp/service-url` |
| CloudWatch | `/aws/ecs/a207920-{service}-service` | `/aws/ecs/a207920-urgent-drafting-service` |

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
- ECR repository existence
- Available image tags
- CDK stack status

## Accessing the Service

After deployment, retrieve the service URL:

```bash
# From SSM Parameter
aws ssm get-parameter \
  --name /a207920/urgent-drafting-mcp/service-url \
  --region eu-west-1 \
  --profile tr-central-preprod \
  --query 'Parameter.Value' \
  --output text

# Or from deploy script
./deploy.sh status
```

Test the health endpoint:
```bash
SERVICE_URL=$(aws ssm get-parameter --name /a207920/urgent-drafting-mcp/service-url --region eu-west-1 --profile tr-central-preprod --query 'Parameter.Value' --output text)
curl $SERVICE_URL/health
```

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
