#!/usr/bin/env python3
"""
CDK App for CI/CD Pipelines for Sphinx Leon Assistant Skills.

This app creates one CodePipeline per skill per environment.
Each pipeline has path-based filtering to only trigger on changes to its skill directory.

Usage:
    cdk deploy --all                    # Deploy all pipelines
    cdk deploy urgent-drafting-dev      # Deploy specific pipeline
    cdk diff --all                      # See changes to all pipelines
    cdk destroy --all                   # Remove all pipelines

To add a new skill:
    1. Add entry to config/skills_registry.py
    2. Run: cdk deploy --all
"""

import aws_cdk as cdk
from aws_cdk import Tags

from tr_cdk_lib import TRCdk, NamingProps, OptionalTRTags

from config.skills_registry import (
    SKILLS_REGISTRY,
    ENVIRONMENTS,
    AWS_CONFIGS,
    GITHUB_CONFIG,
    get_skill_pipeline_name,
    get_skill_path_filter,
    get_aws_config_for_environment,
    validate_registry,
)
from stacks.pipeline_stack import SkillPipelineStack


def main():
    """Create pipeline stacks for all skills in all environments."""

    # Validate registry before creating any stacks
    try:
        validate_registry()
    except ValueError as e:
        print(f"ERROR: {e}")
        exit(1)

    # Optional TR tags for Thomson Reuters compliance
    optional_tr_tags = OptionalTRTags(
        project_name="sphinx",
        service_name="sphinx-skills-cicd",
    )

    # Create CDK app using tr_cdk_lib
    # deployment_env=None uses the default bootstrap (a207920-TrcdkToolkit)
    # asset_id and resource_owner are identical across accounts
    app = TRCdk.new_app(
        asset_id=AWS_CONFIGS["preprod"]["asset_id"],
        resource_owner=AWS_CONFIGS["preprod"]["resource_owner"],
        deployment_env=None,  # Use default bootstrap shared by all skills
        naming_props=NamingProps(prefix="spx"),  # Sphinx project prefix
        optional_tr_tags=optional_tr_tags,
    )

    # Create one pipeline per skill per environment
    pipelines_created = []
    for skill_name, skill_config in SKILLS_REGISTRY.items():
        skill_path = skill_config["path"]
        skill_description = skill_config.get("description", skill_name)

        # Extract notification configuration
        notification_config = skill_config.get("notifications", {})
        notification_emails = notification_config.get("emails", []) if notification_config.get("enabled", True) else []

        for environment in skill_config["environments"]:
            if environment not in ENVIRONMENTS:
                print(f"WARNING: Skipping unknown environment '{environment}' for skill '{skill_name}'")
                continue

            env_config = ENVIRONMENTS[environment]
            aws_config = get_aws_config_for_environment(environment)

            # Create unique construct ID for this pipeline
            # Format: urgent-drafting-dev-pipeline
            construct_id = f"{skill_name}-{environment}-pipeline"

            # Create the pipeline stack
            pipeline_stack = SkillPipelineStack(
                app,
                construct_id,
                skill_name=skill_name,
                skill_path=skill_path,
                environment=environment,
                branch_name=env_config["branch"],
                path_filters=get_skill_path_filter(skill_name),
                codestar_connection_arn=aws_config["codestar_connection_arn"],
                github_owner=GITHUB_CONFIG["owner"],
                github_repo=GITHUB_CONFIG["repo"],
                require_approval=env_config["require_approval"],
                notification_emails=notification_emails,
                env=cdk.Environment(
                    account=aws_config["account"],
                    region=aws_config["region"],
                ),
            )

            # Add tags
            Tags.of(pipeline_stack).add("Skill-Name", skill_name)
            Tags.of(pipeline_stack).add("Environment", environment)
            Tags.of(pipeline_stack).add("Pipeline-Type", "Skill-CI-CD")
            Tags.of(pipeline_stack).add("Skill-Description", skill_description)

            pipelines_created.append(f"{skill_name}-{environment}")

            print(f"✓ Created pipeline: {skill_name}-{environment} (branch: {env_config['branch']}, path: {skill_path}/**)")

    print(f"\nTotal pipelines created: {len(pipelines_created)}")
    print(f"Pipelines: {', '.join(pipelines_created)}")

    # Synthesize the app
    app.synth()


if __name__ == "__main__":
    main()
