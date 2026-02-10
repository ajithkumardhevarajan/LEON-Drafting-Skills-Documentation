"""LLM Configuration for Azure OpenAI and Orchestrator"""

from dataclasses import dataclass, field
from typing import Optional, Dict


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
    """Pure configuration for Azure OpenAI LLM - no environment dependencies"""
    endpoint: str
    api_key: str
    api_version: str = "2025-01-01-preview"
    gpt4_1_deployment: str = "gpt-4-1"
    gpt4o_deployment: str = "gpt-4o"
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    orchestrator: Optional[OrchestratorConfig] = None
