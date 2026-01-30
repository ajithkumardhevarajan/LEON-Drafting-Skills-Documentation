"""
Configuration for urgent-drafting MCP deployment to AWS ECS.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class MCPConfig:
    """Configuration for urgent-drafting MCP deployment"""

    # Environment (required parameter)
    environment: str = "dev"  # Environment name (dev, qa, staging, prod)

    # Basic identifiers
    mcp_name: str = "urgent-drafting-skill"
    service_name: str = "urg-draft"  # Short name for TR CDK naming (avoid 64-char limit)
    service_full_name_display: str = "urgent-drafting"  # Full name for display/logs

    # AWS Configuration
    aws_account: str = "060725138335"
    aws_region: str = "eu-west-1"
    aws_profile: str = "tr-central-preprod"
    asset_id: str = "207920"
    resource_prefix: str = "a207920"

    # ECR Configuration - using full skill name
    ecr_repository_name: str = "a207920/urgent-drafting-skill/dev"
    default_image_tag: str = "latest"

    # ECS Configuration
    cpu: int = 512
    memory_mib: int = 1024
    desired_count: int = 1
    container_port: int = 8000  # Port from Dockerfile EXPOSE

    # Auto Scaling Configuration
    min_capacity: int = 1
    max_capacity: int = 5
    cpu_target_utilization: int = 70
    memory_target_utilization: int = 70

    # Load Balancer Configuration
    public_load_balancer: bool = False  # Internal ALB

    # SSM Parameters - using short name
    ssm_parameter_prefix: str = "/a207920/urg-draft"

    # Tags
    project_name: str = "sphinx"
    service_full_name: str = "sphinx-urgent-drafting-skill"

    def get_stack_name(self) -> str:
        """Get the CDK stack name"""
        return f"{self.resource_prefix}-{self.service_name}-skill-stack"

    def get_ecr_uri(self, tag: str = None) -> str:
        """Get the full ECR URI for the container image"""
        tag = tag or self.default_image_tag
        return f"{self.aws_account}.dkr.ecr.{self.aws_region}.amazonaws.com/{self.ecr_repository_name}:{tag}"

    def get_resource_name(self, resource_type: str) -> str:
        """Generate consistent resource names with environment

        Note: TR CDK automatically adds "a207920-spx-" prefix via NamingProps,
        so we only need to add environment and service name.

        Special handling for resources with strict length limits:
        - ALB names: max 32 chars, use short name
        - Other resources: use full name for clarity
        """
        # Resources with strict length limits use short names
        if resource_type in ["alb", "lb"]:
            return f"{self.environment}-{self.service_name}-{resource_type}"

        # All other resources use full name
        return f"{self.environment}-{self.service_full_name_display}-{resource_type}"

    def get_ssm_parameter_name(self, parameter: str) -> str:
        """Generate SSM parameter names with prefix"""
        return f"{self.ssm_parameter_prefix}/{parameter}"

    def get_environment_variables(self) -> Dict[str, str]:
        """
        Get environment variables for the container.
        Reads ALL variables from .env file in the parent directory.
        """
        env_vars = {
            "MCP_SERVICE_NAME": self.service_name,
            "AWS_DEFAULT_REGION": self.aws_region,
            "MCP_PORT": str(self.container_port),
        }

        # Try to load all variables from .env file
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        # Skip comments and empty lines
                        if line and not line.startswith('#'):
                            if '=' in line:
                                key, value = line.split('=', 1)
                                key = key.strip()
                                value = value.strip()
                                # Add all non-empty variables
                                if key and value:
                                    env_vars[key] = value
            except Exception as e:
                print(f"Warning: Could not read .env file: {e}")

        return env_vars

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for easy access"""
        return {
            'mcp_name': self.mcp_name,
            'service_name': self.service_name,
            'aws_account': self.aws_account,
            'aws_region': self.aws_region,
            'asset_id': self.asset_id,
            'resource_prefix': self.resource_prefix,
            'ecr_repository_name': self.ecr_repository_name,
            'cpu': self.cpu,
            'memory_mib': self.memory_mib,
            'desired_count': self.desired_count,
            'container_port': self.container_port,
            'min_capacity': self.min_capacity,
            'max_capacity': self.max_capacity,
            'public_load_balancer': self.public_load_balancer,
            'project_name': self.project_name,
            'service_full_name': self.service_full_name
        }


# Default configuration instance (for backward compatibility)
# In production, create with specific environment: MCPConfig(environment="dev")
CONFIG = MCPConfig(environment="dev")
