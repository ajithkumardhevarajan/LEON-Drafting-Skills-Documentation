"""
Central registry for all skills and their CI/CD pipeline configurations.

To add a new skill:
1. Add an entry to SKILLS_REGISTRY with the skill name and path
2. Run: cd cicd && cdk deploy --all
3. Pipelines will be automatically created for all registered environments

Each skill gets one pipeline per environment (dev, qa) with path-based triggers.
"""

from typing import Dict, Any, List

# Skills registry - Add new skills here to create their pipelines
SKILLS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "urgent-drafting": {
        "path": "urgent-drafting",  # Path in repository
        "environments": ["dev", "qa"],  # Environments to create pipelines for
        "description": "Urgent drafting skill for Leon assistant",
    },
    # Add future skills here:
    # "future-skill": {
    #     "path": "future-skill",
    #     "environments": ["dev", "qa"],
    #     "description": "Description of future skill",
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
}

# AWS Configuration
AWS_CONFIG = {
    "account": "060725138335",
    "region": "eu-west-1",
    "profile": "tr-central-preprod",
    "asset_id": "207920",
    "resource_owner": "iridium@trten.onmicrosoft.com",
}

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

    if errors:
        raise ValueError("Registry validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
