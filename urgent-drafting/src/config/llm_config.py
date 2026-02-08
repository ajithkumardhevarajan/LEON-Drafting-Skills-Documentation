"""LLM Configuration for Azure OpenAI and Orchestrator"""

import os
from dataclasses import dataclass, field
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DeploymentConfig:
    """Configuration for a specific model deployment"""
    deployment: str  # Deployment name/path
    model: Optional[str] = None  # Actual model name (if different from deployment)
    api_version: Optional[str] = None  # Override API version for this deployment
    headers: Optional[Dict[str, str]] = None  # Deployment-specific headers


@dataclass
class OrchestratorConfig:
    """Configuration for LLM Orchestrator proxy service"""
    endpoint: str
    api_key: str
    api_version: str = "2025-01-01-preview"
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    resource: Optional[str] = None  # Azure AD resource scope
    headers: Optional[Dict[str, str]] = None  # Global headers for all requests
    deployments: Dict[str, DeploymentConfig] = field(default_factory=dict)


@dataclass
class LLMConfig:
    """Configuration for Azure OpenAI LLM"""
    endpoint: str
    api_key: str
    api_version: str = "2025-01-01-preview"
    gpt4_1_deployment: str = "gpt-4-1"
    gpt4o_deployment: str = "gpt-4o"
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    orchestrator: Optional[OrchestratorConfig] = None


def get_llm_config() -> LLMConfig:
    """Load LLM configuration from environment variables"""

    # Load orchestrator configuration if available
    orchestrator_config = None
    orchestrator_endpoint = os.getenv("ORCHESTRATOR_ENDPOINT")

    if orchestrator_endpoint:
        # Default deployment configurations for common models
        deployments = {
            "gpt-4o": DeploymentConfig(
                deployment=os.getenv("ORCHESTRATOR_DEPLOYMENT_GPT4O", "gpt-4o"),
                model="gpt-4o"
            ),
            "gpt-4-1": DeploymentConfig(
                deployment=os.getenv("ORCHESTRATOR_DEPLOYMENT_GPT4_1", "gpt-4-1"),
                model="gpt-4-1"
            ),
            "o1-mini": DeploymentConfig(
                deployment=os.getenv("ORCHESTRATOR_DEPLOYMENT_O1_MINI", "o1-mini"),
                model="o1-mini"
            ),
            "o3-mini": DeploymentConfig(
                deployment=os.getenv("ORCHESTRATOR_DEPLOYMENT_O3_MINI", "o3-mini"),
                model="o3-mini"
            ),
            "o4-mini": DeploymentConfig(
                deployment=os.getenv("ORCHESTRATOR_DEPLOYMENT_O4_MINI", "o4-mini"),
                model="o4-mini"
            ),
        }

        orchestrator_config = OrchestratorConfig(
            endpoint=orchestrator_endpoint,
            api_key=os.getenv("LEON_ORCHESTRATOR_API_KEY", ""),
            api_version=os.getenv("ORCHESTRATOR_API_VERSION", "2025-01-01-preview"),
            tenant_id=os.getenv("LEON_ORCHESTRATOR_TENANT_ID"),
            client_id=os.getenv("LEON_ORCHESTRATOR_CLIENT_ID"),
            client_secret=os.getenv("LEON_ORCHESTRATOR_CLIENT_SECRET"),
            resource=os.getenv("LEON_ORCHESTRATOR_RESOURCE"),
            deployments=deployments
        )

    return LLMConfig(
        endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        gpt4_1_deployment=os.getenv("AZURE_DEPLOYMENT_GPT4_1", "gpt-4-1"),
        gpt4o_deployment=os.getenv("AZURE_DEPLOYMENT_GPT4O", "gpt-4o"),
        tenant_id=os.getenv("AZURE_TENANT_ID"),
        client_id=os.getenv("AZURE_CLIENT_ID"),
        client_secret=os.getenv("AZURE_CLIENT_SECRET"),
        orchestrator=orchestrator_config
    )
