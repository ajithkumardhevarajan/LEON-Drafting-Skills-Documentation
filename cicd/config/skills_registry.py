"""
Central registry for all skills and their CI/CD pipeline configurations.

To add a new skill:
1. Add an entry to SKILLS_REGISTRY with the skill name and path
2. Run: cd cicd && cdk deploy --all
3. Pipelines will be automatically created for all registered environments

Each skill gets one pipeline per environment.
For prod, one pipeline deploys sequentially to euw1 then use1.
"""

from typing import Dict, Any, List, Optional

# Skills registry - Add new skills here to create their pipelines
SKILLS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "urgent-drafting": {
        "path": "urgent-drafting",
        "environments": ["dev", "qa", "uat", "prod"],
        "description": "Urgent drafting skill for Leon assistant",
        "notifications": {
            "emails": ["simranjit.kamboj@thomsonreuters.com", "michal.zarow@thomsonreuters.com"],
            "enabled": True,
        },
    },
    "story-drafting": {
        "path": "story-drafting",
        "environments": ["dev", "qa", "uat"],
        "description": "Story drafting skill for Leon assistant",
        "notifications": {
            "emails": ["simranjit.kamboj@thomsonreuters.com"],
            "enabled": True,
        },
    },
    "text-archive": {
        "path": "text-archive",
        "environments": ["dev", "qa", "uat"],
        "description": "Reuters Text Archive search skill for Leon assistant",
        "notifications": {
            "emails": ["simranjit.kamboj@thomsonreuters.com"],
            "enabled": True,
        },
    },
    # Add future skills here:
    # "future-skill": {
    #     "path": "future-skill",
    #     "environments": ["dev", "qa"],
    #     "description": "Description of future skill",
    #     "notifications": {
    #         "emails": ["team@example.com"],
    #         "enabled": True,
    #     },
    # },
}

# Environment configuration - Defines branch triggers, approval requirements, and deploy targets
#
# deploy_stages (optional): ordered list of regions to deploy to within one pipeline.
#   - Not set (single-region): pipeline deploys to its own region in one "Deploy" stage.
#   - Set (multi-region, e.g. prod): pipeline deploys sequentially — euw1 first, then use1.
#     Each entry maps to a DEPLOYMENT_ENV value that config.py inside the skill uses to
#     resolve the target AWS account/region/secrets.
ENVIRONMENTS: Dict[str, Dict[str, Any]] = {
    "dev": {
        "branch": "develop",
        "require_approval": False,
        "description": "Development environment",
    },
    "qa": {
        "branch": "qa",
        "require_approval": False,
        "description": "QA environment",
    },
    "uat": {
        "branch": "uat",
        "require_approval": False,
        "description": "UAT environment (prod account, euw1)",
    },
    "prod": {
        "branch": "prod",
        "require_approval": True,  # Manual approval gate before any deployment
        "description": "Production environment — one pipeline, euw1 then use1 sequential",
        # Ordered deploy stages: euw1 deploys and stabilises before use1 starts.
        # 'environment' is the DEPLOYMENT_ENV value passed into the skill's CDK app
        # (maps to ENVIRONMENT_CONFIGS in each skill's config.py).
        # 'region' is the AWS region for that deploy stage's CDK stack and IAM policies.
        "deploy_stages": [
            {"environment": "prod-euw1", "region": "eu-west-1"},
            {"environment": "prod-use1", "region": "us-east-1"},
        ],
    },
}

# AWS Configuration - Per-account configuration for multi-account deployment
AWS_CONFIGS = {
    "preprod": {
        "account": "060725138335",
        "region": "eu-west-1",
        "profile": "tr-central-preprod",
        "asset_id": "207920",
        "resource_owner": "iridium@trten.onmicrosoft.com",
        "environments": ["dev", "qa"],
        "codestar_connection_arn": "arn:aws:codeconnections:eu-west-1:060725138335:connection/d39c32c7-a1b3-4033-a97c-be812c340906",
    },
    "prod": {
        "account": "304853478528",
        "region": "eu-west-1",  # Pipeline infrastructure lives in euw1
        "profile": "tr-central-prod",
        "asset_id": "207920",
        "resource_owner": "iridium@trten.onmicrosoft.com",
        "environments": ["uat", "prod"],
        "codestar_connection_arn": "arn:aws:codeconnections:eu-west-1:304853478528:connection/2d57c24a-267e-47de-9a03-8d1fb7f6a828",
    },
}

# Default AWS config for backward compatibility
AWS_CONFIG = AWS_CONFIGS["preprod"]

# CodeStar Connection for GitHub
CODESTAR_CONNECTION_ARN = "arn:aws:codeconnections:eu-west-1:060725138335:connection/d39c32c7-a1b3-4033-a97c-be812c340906"

# GitHub repository configuration
GITHUB_CONFIG = {
    "owner": "tr",
    "repo": "sphinx_leon-assistant-skills",
}


def get_skill_pipeline_name(skill_name: str, environment: str) -> str:
    """Generate pipeline name for a skill in a specific environment."""
    return f"{skill_name}-{environment}"


def get_skill_path_filter(skill_name: str) -> List[str]:
    """Generate path filter patterns for a skill's pipeline."""
    skill_config = SKILLS_REGISTRY.get(skill_name)
    if not skill_config:
        raise ValueError(f"Skill {skill_name} not found in registry")
    skill_path = skill_config["path"]
    return [f"{skill_path}/**"]


def get_aws_config_for_environment(environment: str) -> Dict[str, Any]:
    """
    Get AWS configuration for a specific environment.

    Returns the account/region/profile/etc. for the pipeline infrastructure.
    For prod, the pipeline itself lives in eu-west-1 even though it deploys to both
    eu-west-1 and us-east-1 — the deploy_stages in ENVIRONMENTS handle that.

    Raises:
        ValueError: If environment is not configured in any AWS account
    """
    for aws_config in AWS_CONFIGS.values():
        if environment in aws_config.get("environments", []):
            return {
                "account": aws_config["account"],
                "region": aws_config["region"],
                "profile": aws_config["profile"],
                "asset_id": aws_config["asset_id"],
                "resource_owner": aws_config["resource_owner"],
                "codestar_connection_arn": aws_config["codestar_connection_arn"],
            }

    raise ValueError(
        f"Environment '{environment}' not found in any AWS account configuration. "
        f"Available environments: {[env for cfg in AWS_CONFIGS.values() for env in cfg.get('environments', [])]}"
    )


def validate_registry() -> None:
    """Validate the skills registry configuration."""
    errors = []

    for skill_name, config in SKILLS_REGISTRY.items():
        if "path" not in config:
            errors.append(f"Skill '{skill_name}' missing 'path' field")
        if "environments" not in config:
            errors.append(f"Skill '{skill_name}' missing 'environments' field")

        for env in config.get("environments", []):
            if env not in ENVIRONMENTS:
                errors.append(
                    f"Skill '{skill_name}' references unknown environment '{env}'. "
                    f"Valid environments: {', '.join(ENVIRONMENTS.keys())}"
                )

    # Every ENVIRONMENTS entry must be assigned to an AWS account
    all_configured_envs = [
        env for cfg in AWS_CONFIGS.values() for env in cfg.get("environments", [])
    ]
    for env_name in ENVIRONMENTS.keys():
        if env_name not in all_configured_envs:
            errors.append(
                f"Environment '{env_name}' is defined in ENVIRONMENTS but not assigned "
                f"to any AWS account in AWS_CONFIGS"
            )

    if errors:
        raise ValueError("Registry validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
