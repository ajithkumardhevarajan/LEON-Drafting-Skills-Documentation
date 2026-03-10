# LEON Skills Shared ALB — CloudFormation

Path-based routing for LEON AI assistant skill services in `tr-central-preprod`.  
A single internal ALB routes to three ECS Fargate skill services based on URL path prefix.

## Architecture

```
           8335.aws-int.thomsonreuters.com  (Route53 private zone)
                          |
   skills.leon-ci.*       |       skills.leon-test.*
                          ↓
         a207920-leo-{env}-main-euw1-skills-alb  (internal ALB, port 80)
          /                     |                        \
 /urgent-drafting        /story-drafting            /text-archive
        ↓                       ↓                         ↓
 CDK target group        CDK target group          CDK target group
 (CF export lookup)      (CF export lookup)        (CF export lookup)
        ↓                       ↓                         ↓
ECS: urgent-drafting    ECS: story-drafting        ECS: text-archive
```

**Key design decision:** The shared ALB does **not** create its own target groups. It imports the CDK-managed target group ARNs published as CloudFormation exports by each skill's CDK stack (`a207920-leon-skills-shared-alb-{env}-tg-{skill}`). This means ECS services do not need to be changed — they continue to receive traffic through their existing target groups.

A default listener rule returns a `{"error": "No skill route matched."}` JSON 404 for any path that doesn't match the three skill prefixes.

## Infrastructure

**Account:** `tr-central-preprod` (060725138335)  
**Region:** `eu-west-1`  
**VPC:** `vpc-51c3e835`  
**Private subnets:** `subnet-9dace9c5` (1a), `subnet-31447c55` (1b), `subnet-47714e31` (1c)  
**Route53 private zone:** `8335.aws-int.thomsonreuters.com` (Z1GFVCPGDV59FR)

## Files

| File | Purpose |
|------|---------|
| `templates/a207920_leon_skills_shared_alb.yaml` | Single CF template (both environments) |
| `parameters/ci/euw1/a207920_leon_skills_shared_alb_ci_euw1.json` | CI parameter values |
| `parameters/test/euw1/a207920_leon_skills_shared_alb_test_euw1.json` | Test parameter values |

## Deployed Stacks

| Environment | Stack name | Status |
|-------------|-----------|--------|
| CI   | `a207920-leon-skills-shared-alb-ci`   | ✅ UPDATE_COMPLETE |
| Test | `a207920-leon-skills-shared-alb-test` | ✅ CREATE_COMPLETE |

## Deployment

Run from the `cloudformation/` directory.

### CI

```bash
aws cloudformation deploy \
  --stack-name a207920-leon-skills-shared-alb-ci \
  --template-file templates/a207920_leon_skills_shared_alb.yaml \
  --parameter-overrides file://parameters/ci/euw1/a207920_leon_skills_shared_alb_ci_euw1.json \
  --profile tr-central-preprod \
  --region eu-west-1 \
  --capabilities CAPABILITY_NAMED_IAM
```

### Test

```bash
aws cloudformation deploy \
  --stack-name a207920-leon-skills-shared-alb-test \
  --template-file templates/a207920_leon_skills_shared_alb.yaml \
  --parameter-overrides file://parameters/test/euw1/a207920_leon_skills_shared_alb_test_euw1.json \
  --profile tr-central-preprod \
  --region eu-west-1 \
  --capabilities CAPABILITY_NAMED_IAM
```

## CDK Dependency: Target Group CF Exports

Before deploying this stack, each skill's CDK stack must be deployed so that it publishes its target group ARN as a CF export. The template imports these exports by name:

| CF Export name | Consumed by |
|----------------|-------------|
| `a207920-leon-skills-shared-alb-ci-tg-urgent` | CI ALB listener rule |
| `a207920-leon-skills-shared-alb-ci-tg-story` | CI ALB listener rule |
| `a207920-leon-skills-shared-alb-ci-tg-text-archive` | CI ALB listener rule |
| `a207920-leon-skills-shared-alb-test-tg-urgent` | Test ALB listener rule |
| `a207920-leon-skills-shared-alb-test-tg-story` | Test ALB listener rule |
| `a207920-leon-skills-shared-alb-test-tg-text-archive` | Test ALB listener rule |

These exports are created by the `shared_alb_tg_cf_export` value set in each skill's `infra/config.py` and wired up in `infra/mcp_stack.py` via `_attach_shared_alb_tg()`. The CDK environment names that map to these are:

| CDK env name | Maps to CF environment |
|---|---|
| `dev` | CI (targets `ci` exports) |
| `qa` | Test (targets `test` exports) |

## Post-Deployment: ECS Security Group Rules

**Required once per environment** — allows the shared ALB to reach port 8000 on each ECS task.

Get the shared ALB security group ID from the stack output:

```bash
aws cloudformation describe-stacks \
  --stack-name a207920-leon-skills-shared-alb-ci \
  --profile tr-central-preprod --region eu-west-1 \
  --query "Stacks[0].Outputs[?OutputKey=='SharedAlbSecurityGroupId'].OutputValue" \
  --output text
```

Then add an inbound rule for **port 8000** from the shared ALB SG to each of the three skill ECS task security groups:

```bash
# Repeat for each ECS task SG (urgent-drafting, story-drafting, text-archive)
aws ec2 authorize-security-group-ingress \
  --group-id <ECS_TASK_SG_ID> \
  --protocol tcp \
  --port 8000 \
  --source-group <SHARED_ALB_SG_ID> \
  --profile tr-central-preprod \
  --region eu-west-1
```

> ℹ️ The ECS task SG IDs can be found in the Outputs of each skill's CDK CloudFormation stack.

## DNS

Route53 ALIAS records (in `8335.aws-int.thomsonreuters.com`) are created by this CloudFormation template — no Banana ticket needed for the internal AWS DNS records.

However, **Banana/ServiceNow** tickets are needed for the corresponding `.int.thomsonreuters.com` CNAMEs (internal resolution from the wider TR network):

| CNAME | Target |
|-------|--------|
| `skills.leon-ci.int.thomsonreuters.com` | `skills.leon-ci.8335.aws-int.thomsonreuters.com` |
| `skills.leon-test.int.thomsonreuters.com` | `skills.leon-test.8335.aws-int.thomsonreuters.com` |

## Live Endpoints

| Environment | Skill | URL |
|-------------|-------|-----|
| CI   | urgent-drafting | `http://skills.leon-ci.8335.aws-int.thomsonreuters.com/urgent-drafting/health` |
| CI   | story-drafting  | `http://skills.leon-ci.8335.aws-int.thomsonreuters.com/story-drafting/health` |
| CI   | text-archive    | `http://skills.leon-ci.8335.aws-int.thomsonreuters.com/text-archive/health` |
| Test | urgent-drafting | `http://skills.leon-test.8335.aws-int.thomsonreuters.com/urgent-drafting/health` |
| Test | story-drafting  | `http://skills.leon-test.8335.aws-int.thomsonreuters.com/story-drafting/health` |
| Test | text-archive    | `http://skills.leon-test.8335.aws-int.thomsonreuters.com/text-archive/health` |

A `GET /` returns `404` with `{"error": "No skill route matched."}` — this confirms the ALB is alive.  
Skill paths return `503` until the CDK stacks are deployed (ECS tasks not yet registered to the target groups).

## Next Steps

1. **Deploy CDK for each skill** (`./deploy.sh cdk-deploy dev <tag>` / `cdk-deploy qa <tag>`) so ECS services register with the shared ALB target groups — this will turn the 503s into 200s
2. **Raise Banana tickets** for the `.int.thomsonreuters.com` CNAMEs (see DNS section above)
3. **Verify** health endpoints return 200 after CDK deploy
4. **Update LEON backend** to route skill requests via the shared ALB hostname instead of per-skill ALBs
5. **Decommission** per-skill ALBs (`a207920-spx-{env}-urg-draft-alb` etc.) once LEON backend is updated
