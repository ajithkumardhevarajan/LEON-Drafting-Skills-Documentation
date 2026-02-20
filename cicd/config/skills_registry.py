"""
Central registry for all skills and their CI/CD pipeline configurations.

To add a new skill:
1. Add an entry to SKILLS_REGISTRY with the skill name and path
2. Run: cd cicd && cdk deploy --all
3. Pipelines will be automatically created for all registered environments

Each skill gets one pipeline per environment (dev, qa, uat) with path-based triggers.
"""

from typing import Dict, Any, List

# Skills registry - Add new skills here to create their pipelines
SKILLS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "urgent-drafting": {
        "path": "urgent-drafting",  # Path in repository
        "environments": ["dev", "qa", "uat"],  # Environments to create pipelines for
        "description": "Urgent drafting skill for Leon assistant",
        "notifications": {
            "emails": ["simranjit.kamboj@thomsonreuters.com", "michal.zarow@thomsonreuters.com"],  # Email addresses for deployment notifications
            "enabled": True,  # Set to False to disable notifications for this skill
        },
    },
    "story-drafting": {
        "path": "story-drafting",  # Path in repository
        "environments": ["dev", "qa", "uat"],  # Environments to create pipelines for
        "description": "Story drafting skill for Leon assistant",
        "notifications": {
            "emails": ["simranjit.kamboj@thomsonreuters.com"],  # Email addresses for deployment notifications
            "enabled": True,  # Set to False to disable notifications for this skill
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

# Environment configuration - Defines branch triggers and approval requirements
ENVIRONMENTS: Dict[str, Dict[str, Any]] = {
    "dev": {
        "branch": "develop",  # Triggers on pushes to develop branch
        "require_approval": False,  # Auto-deploy without manual approval
        "description": "Development environment",
    },
    "qa": {
        "branch": "qa",  # Triggers on pushes to qa branch
        "require_approval": False,  # Auto-deploy without manual approval
        "description": "QA environment",
    },
    "uat": {
        "branch": "uat",  # Triggers on pushes to uat branch
        "require_approval": False,  # Auto-deploy without manual approval
        "description": "UAT environment (prod account)",
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
        "environments": ["dev", "qa"],  # Environments in this account
        "codestar_connection_arn": "arn:aws:codeconnections:eu-west-1:060725138335:connection/d39c32c7-a1b3-4033-a97c-be812c340906",
    },
    "prod": {
        "account": "304853478528",
        "region": "eu-west-1",
        "profile": "tr-central-prod",
        "asset_id": "207920",
        "resource_owner": "iridium@trten.onmicrosoft.com",
        "environments": ["uat", "prod"],  # Environments in this account
        "codestar_connection_arn": "arn:aws:codeconnections:eu-west-1:304853478528:connection/2d57c24a-267e-47de-9a03-8d1fb7f6a828",
    },
}

# Default AWS config for backward compatibility
# Uses preprod account (where dev/qa environments run)
AWS_CONFIG = AWS_CONFIGS["preprod"]

# CodeStar Connection for GitHub
# Created in AWS Console: Developer Tools -> Connections
# Format: arn:aws:codeconnections:region:account:connection/connection-id
CODESTAR_CONNECTION_ARN = "arn:aws:codeconnections:eu-west-1:060725138335:connection/d39c32c7-a1b3-4033-a97c-be812c340906"

# GitHub repository configuration
GITHUB_CONFIG = {
    "owner": "tr",  # GitHub organization/user
    "repo": "sphinx_leon-assistant-skills",  # Repository name
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
    # Trigger on any changes within the skill directory
    return [f"{skill_path}/**"]


def get_aws_config_for_environment(environment: str) -> Dict[str, Any]:
    """
    Get AWS configuration for a specific environment.

    Args:
        environment: Environment name (dev, qa, uat, prod, etc.)

    Returns:
        AWS configuration dict for the account that hosts this environment

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

    # Check each skill has required fields
    for skill_name, config in SKILLS_REGISTRY.items():
        if "path" not in config:
            errors.append(f"Skill '{skill_name}' missing 'path' field")
        if "environments" not in config:
            errors.append(f"Skill '{skill_name}' missing 'environments' field")

        # Check environments are valid
        for env in config.get("environments", []):
            if env not in ENVIRONMENTS:
                errors.append(
                    f"Skill '{skill_name}' references unknown environment '{env}'. "
                    f"Valid environments: {', '.join(ENVIRONMENTS.keys())}"
                )

    # Validate AWS account configurations
    all_configured_envs = [env for cfg in AWS_CONFIGS.values() for env in cfg.get("environments", [])]
    for env_name in ENVIRONMENTS.keys():
        if env_name not in all_configured_envs:
            errors.append(
                f"Environment '{env_name}' is defined in ENVIRONMENTS but not assigned to any AWS account in AWS_CONFIGS"
            )

    if errors:
        raise ValueError("Registry validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
