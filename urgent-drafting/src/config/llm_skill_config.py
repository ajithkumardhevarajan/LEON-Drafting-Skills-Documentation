"""LLM Configuration for Urgent Drafting Skill

This module handles loading LLM configuration from environment variables
specific to the urgent-drafting skill.
"""

import os
from dotenv import load_dotenv
from shared.llm import LLMConfig, OrchestratorConfig, DeploymentConfig

load_dotenv()


def load_llm_config() -> LLMConfig:
    """
    Load LLM configuration from environment variables for the urgent-drafting skill.

    Returns:
        LLMConfig: Configuration object for LLM Orchestrator

    Environment Variables:
        Direct Azure OpenAI:
            - AZURE_OPENAI_ENDPOINT
            - AZURE_OPENAI_API_KEY
            - AZURE_OPENAI_API_VERSION
            - AZURE_DEPLOYMENT_GPT4_1
            - AZURE_DEPLOYMENT_GPT4O
            - AZURE_TENANT_ID
            - AZURE_CLIENT_ID
            - AZURE_CLIENT_SECRET

        Via Orchestrator:
            - ORCHESTRATOR_ENDPOINT
            - LEON_ORCHESTRATOR_API_KEY
            - ORCHESTRATOR_API_VERSION
            - LEON_ORCHESTRATOR_TENANT_ID
            - LEON_ORCHESTRATOR_CLIENT_ID
            - LEON_ORCHESTRATOR_CLIENT_SECRET
            - LEON_ORCHESTRATOR_RESOURCE
            - ORCHESTRATOR_DEPLOYMENT_GPT4O
            - ORCHESTRATOR_DEPLOYMENT_GPT4_1
            - ORCHESTRATOR_DEPLOYMENT_O1_MINI
            - ORCHESTRATOR_DEPLOYMENT_O3_MINI
            - ORCHESTRATOR_DEPLOYMENT_O4_MINI
    """
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
