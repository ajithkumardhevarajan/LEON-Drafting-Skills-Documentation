"""
Configuration for story-drafting MCP deployment to AWS ECS.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


# Environment-specific configuration
ENVIRONMENT_CONFIGS = {
    "dev": {
        "aws_account": "060725138335",
        "aws_region": "eu-west-1",
        "aws_profile": "tr-central-preprod",
        "cpu": 512,
        "memory_mib": 1024,
        "desired_count": 1,
        "min_capacity": 1,
        "max_capacity": 3,
        "cpu_target_utilization": 70,
        "memory_target_utilization": 70,
        "public_load_balancer": False,
        "secrets_arn": "arn:aws:secretsmanager:eu-west-1:060725138335:secret:a207920-leon-skills-vWvmX7",
        "orchestrator_chat_profile": "a209289-Lynx-Editor-Online-NonProd",
        "sphinx_api_url": "https://api.sphinx-test.thomsonreuters.com",
        "sphinx_base_url": "https://sphinx-test.thomsonreuters.com",
        "shared_alb_tg_cf_export": "a207920-leon-skills-shared-alb-ci-tg-story",
    },
    "qa": {
        "aws_account": "060725138335",
        "aws_region": "eu-west-1",
        "aws_profile": "tr-central-preprod",
        "cpu": 1024,
        "memory_mib": 2048,
        "desired_count": 2,
        "min_capacity": 2,
        "max_capacity": 5,
        "cpu_target_utilization": 70,
        "memory_target_utilization": 70,
        "public_load_balancer": False,
        "secrets_arn": "arn:aws:secretsmanager:eu-west-1:060725138335:secret:a207920-leon-skills-vWvmX7",
        "orchestrator_chat_profile": "a209289-Lynx-Editor-Online-NonProd",
        "sphinx_api_url": "https://api.sphinx-test.thomsonreuters.com",
        "sphinx_base_url": "https://sphinx-test.thomsonreuters.com",
        "shared_alb_tg_cf_export": "a207920-leon-skills-shared-alb-test-tg-story",
    },
    "staging": {
        "aws_account": "060725138335",
        "aws_region": "eu-west-1",
        "aws_profile": "tr-central-preprod",
        "cpu": 1024,
        "memory_mib": 2048,
        "desired_count": 2,
        "min_capacity": 2,
        "max_capacity": 8,
        "cpu_target_utilization": 70,
        "memory_target_utilization": 70,
        "public_load_balancer": False,
        "secrets_arn": "arn:aws:secretsmanager:eu-west-1:060725138335:secret:a207920-leon-skills-vWvmX7",
        "orchestrator_chat_profile": "a209289-Lynx-Editor-Online-NonProd",
        "sphinx_api_url": "https://api.sphinx-test.thomsonreuters.com",
        "sphinx_base_url": "https://sphinx-test.thomsonreuters.com",
    },
    "uat": {
        "aws_account": "304853478528",
        "aws_region": "eu-west-1",
        "aws_profile": "tr-central-prod",
        "cpu": 2048,
        "memory_mib": 4096,
        "desired_count": 3,
        "min_capacity": 3,
        "max_capacity": 10,
        "cpu_target_utilization": 70,
        "memory_target_utilization": 70,
        "public_load_balancer": False,
        "secrets_arn": "arn:aws:secretsmanager:eu-west-1:304853478528:secret:a207920-leon-skills-dxbeCU",
        "orchestrator_chat_profile": "a209289-Lynx-Editor-Online-Prod",
        "sphinx_api_url": "https://api.sphinx-uat.thomsonreuters.com",
        "sphinx_base_url": "https://sphinx-uat.thomsonreuters.com",
    },
    "prod-euw1": {
        "aws_account": "304853478528",
        "aws_region": "eu-west-1",
        "aws_profile": "tr-central-prod",
        "cpu": 2048,
        "memory_mib": 4096,
        "desired_count": 3,
        "min_capacity": 3,
        "max_capacity": 10,
        "cpu_target_utilization": 70,
        "memory_target_utilization": 70,
        "public_load_balancer": False,
        "secrets_arn": "arn:aws:secretsmanager:eu-west-1:304853478528:secret:a207920-leon-skills-prod-dia2c6",
        "orchestrator_chat_profile": "a209289-Lynx-Editor-Online-Prod",
        "sphinx_api_url": "https://api.sphinx.thomsonreuters.com",
        "sphinx_base_url": "https://sphinx.thomsonreuters.com",
        "ecr_repository_name": "a207920/story-drafting-skill/prod",
    },
    "prod-use1": {
        "aws_account": "304853478528",
        "aws_region": "us-east-1",
        "aws_profile": "tr-central-prod",
        "cpu": 2048,
        "memory_mib": 4096,
        "desired_count": 3,
        "min_capacity": 3,
        "max_capacity": 10,
        "cpu_target_utilization": 70,
        "memory_target_utilization": 70,
        "public_load_balancer": False,
        "secrets_arn": "arn:aws:secretsmanager:us-east-1:304853478528:secret:a207920-leon-skills-prod-dia2c6",
        "orchestrator_chat_profile": "a209289-Lynx-Editor-Online-Prod",
        "sphinx_api_url": "https://api.sphinx.thomsonreuters.com",
        "sphinx_base_url": "https://sphinx.thomsonreuters.com",
        "ecr_repository_name": "a207920/story-drafting-skill/prod",
    },
}


@dataclass
class MCPConfig:
    """Configuration for story-drafting MCP deployment"""

    # Environment (required parameter)
    environment: str = "dev"  # Environment name (dev, qa, staging, prod)

    # Basic identifiers
    mcp_name: str = "story-drafting-skill"
    service_name: str = "story-draft"  # Short name for TR CDK naming (avoid 64-char limit)
    service_full_name_display: str = "story-drafting"  # Full name for display/logs

    # AWS Configuration - dynamically set based on environment
    aws_account: str = field(init=False)
    aws_region: str = field(init=False)
    aws_profile: str = field(init=False)
    asset_id: str = "207920"
    resource_prefix: str = "a207920"

    # ECR Configuration - dynamically set based on environment
    ecr_repository_name: str = field(init=False)
    default_image_tag: str = ""  # Force explicit version (auto-computed from VERSION file)

    # ECS Configuration - dynamically set based on environment
    cpu: int = field(init=False)
    memory_mib: int = field(init=False)
    desired_count: int = field(init=False)
    container_port: int = 8000  # Port from Dockerfile EXPOSE

    # Auto Scaling Configuration - dynamically set based on environment
    min_capacity: int = field(init=False)
    max_capacity: int = field(init=False)
    cpu_target_utilization: int = field(init=False)
    memory_target_utilization: int = field(init=False)

    # Load Balancer Configuration - dynamically set based on environment
    public_load_balancer: bool = field(init=False)

    # SSM Parameters - dynamically set based on environment
    ssm_parameter_prefix: str = field(init=False)

    # AWS Secrets Manager - orchestrator configuration (dynamically set)
    secrets_arn: str = field(init=False)
    secret_name: str = field(init=False)

    # Tags
    project_name: str = "sphinx"
    service_full_name: str = "sphinx-story-drafting-skill"

    # Optional: shared ALB target group CF export (POC: ci/test only)
    shared_alb_tg_cf_export: Optional[str] = None

    def __post_init__(self):
        """Initialize environment-specific configuration after dataclass initialization"""
        # Validate environment
        if self.environment not in ENVIRONMENT_CONFIGS:
            raise ValueError(
                f"Invalid environment: {self.environment}. "
                f"Must be one of: {', '.join(ENVIRONMENT_CONFIGS.keys())}"
            )

        # Load environment-specific configuration
        env_config = ENVIRONMENT_CONFIGS[self.environment]

        # Load AWS configuration from environment config
        self.aws_account = env_config["aws_account"]
        self.aws_region = env_config["aws_region"]
        self.aws_profile = env_config["aws_profile"]

        # Load resource sizing configuration
        self.cpu = env_config["cpu"]
        self.memory_mib = env_config["memory_mib"]
        self.desired_count = env_config["desired_count"]
        self.min_capacity = env_config["min_capacity"]
        self.max_capacity = env_config["max_capacity"]
        self.cpu_target_utilization = env_config["cpu_target_utilization"]
        self.memory_target_utilization = env_config["memory_target_utilization"]
        self.public_load_balancer = env_config["public_load_balancer"]

        # Set ECR repository name — use explicit override if provided, otherwise derive from environment
        if "ecr_repository_name" in env_config:
            self.ecr_repository_name = env_config["ecr_repository_name"]
        else:
            self.ecr_repository_name = f"{self.resource_prefix}/{self.mcp_name}/{self.environment}"

        # Set Secrets Manager secret name (used for cross-account lookup by name)
        self.secret_name = f"{self.resource_prefix}-leon-skills"

        # Set Secrets Manager ARN from environment config (includes the correct suffix per account)
        self.secrets_arn = env_config["secrets_arn"]

        # Set orchestrator chat profile (NonProd vs Prod endpoint)
        self.orchestrator_chat_profile = env_config["orchestrator_chat_profile"]

        # Set Sphinx API URLs
        self.sphinx_api_url = env_config["sphinx_api_url"]
        self.sphinx_base_url = env_config["sphinx_base_url"]

        # Set SSM parameter prefix with environment
        self.ssm_parameter_prefix = f"/a207920/story-draft/{self.environment}"

        # Load optional shared ALB target group CF export (POC: ci/test only)
        self.shared_alb_tg_cf_export = env_config.get("shared_alb_tg_cf_export")

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
            "ORCHESTRATOR_CHAT_PROFILE": self.orchestrator_chat_profile,
            "SPHINX_API_URL": self.sphinx_api_url,
            "SPHINX_BASE_URL": self.sphinx_base_url,
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


# Default configuration instance
# Reads environment from DEPLOYMENT_ENV environment variable (set by deploy.sh)
# Falls back to "dev" if not set
CONFIG = MCPConfig(environment=os.environ.get("DEPLOYMENT_ENV", "dev"))
