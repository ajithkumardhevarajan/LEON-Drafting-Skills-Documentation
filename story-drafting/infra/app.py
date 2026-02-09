#!/usr/bin/env python3
"""
CDK App for deploying story-drafting-mcp to AWS ECS using TR CDK Library.
"""

import os
import sys

import aws_cdk as cdk
from aws_cdk import Tags
from tr_cdk_lib import TRCdk, NamingProps, OptionalTRTags, DeploymentEnv, EnvType

from mcp_stack import MCPStack
from config import MCPConfig

def main():
    """Main entry point for CDK app"""

    # Get environment from environment variable or command line argument
    environment = os.environ.get("DEPLOYMENT_ENV", "dev")
    if len(sys.argv) > 1:
        environment = sys.argv[1]

    # Get image tag from environment variable or command line argument
    image_tag = os.environ.get("IMAGE_TAG", "latest")
    if len(sys.argv) > 2:
        image_tag = sys.argv[2]

    # Create config with environment
    config = MCPConfig(environment=environment)

    # Optional TR tags for Thomson Reuters compliance
    optional_tr_tags = OptionalTRTags(
        project_name=config.project_name,
        service_name=config.service_full_name,
    )

    print(f"Deploying {config.mcp_name} to {environment} environment with image tag: {image_tag}")

    # Create CDK app using tr_cdk_lib
    # deployment_env=None uses the default bootstrap (without suffix)
    # All leon-skills share the same default bootstrap for this account/region
    # NamingProps prefix "spx" for sphinx project
    app = TRCdk.new_app(
        asset_id=config.asset_id,
        resource_owner="iridium@trten.onmicrosoft.com",
        deployment_env=None,  # Use default bootstrap shared by all skills
        naming_props=NamingProps(prefix="spx"),  # Sphinx project prefix
        optional_tr_tags=optional_tr_tags,
    )

    # Create the MCP stack
    # Stack name will be: a207920-spx-dev-story-drafting-skill-euw1
    # Format: {asset}-spx-{env}-{service}-skill-{region}
    construct_id = f"{config.environment}-{config.service_name}-skill"
    mcp_stack = MCPStack(
        app,
        construct_id,  # TR CDK adds asset prefix and region suffix
        config=config,
        image_tag=image_tag,
        env=cdk.Environment(
            account=config.aws_account,
            region=config.aws_region
        ),
    )

    # Add additional tags
    Tags.of(mcp_stack).add("Skill-Name", config.mcp_name)
    Tags.of(mcp_stack).add("Service-Type", "Leon-Skill")
    Tags.of(mcp_stack).add("Deployment-Method", "CDK")
    Tags.of(mcp_stack).add("Environment", environment)

    # Synthesize the app
    app.synth()


if __name__ == "__main__":
    main()
