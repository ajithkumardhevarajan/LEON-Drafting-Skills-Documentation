"""LLM Configuration for Story Drafting Skill

This module handles loading LLM configuration from environment variables
specific to the story-drafting skill. It uses the shared LLM module but
provides skill-specific deployment configurations.
"""

import os
from dotenv import load_dotenv
from shared.llm import LLMConfig, OrchestratorConfig, DeploymentConfig

load_dotenv()


def load_llm_config() -> LLMConfig:
    """
    Load LLM configuration from environment variables for the story-drafting skill.

    Returns:
        LLMConfig: Configuration object for LLM Orchestrator

    Environment Variables:
        Direct Azure OpenAI:
            - AZURE_OPENAI_ENDPOINT
            - AZURE_OPENAI_API_KEY
            - AZURE_OPENAI_API_VERSION
            - AZURE_DEPLOYMENT_GPT4_1
            - AZURE_DEPLOYMENT_GPT4O
            - AZURE_DEPLOYMENT_GEMINI_2_5_PRO
            - AZURE_TENANT_ID
            - AZURE_CLIENT_ID
            - AZURE_CLIENT_SECRET

        Via Orchestrator:
            - ORCHESTRATOR_ENDPOINT
            - ORCHESTRATOR_ASSET_ID
            - ORCHESTRATOR_CHAT_PROFILE
            - LEON_ORCHESTRATOR_API_KEY
            - ORCHESTRATOR_API_VERSION
            - LEON_ORCHESTRATOR_TENANT_ID
            - LEON_ORCHESTRATOR_CLIENT_ID
            - LEON_ORCHESTRATOR_CLIENT_SECRET
            - LEON_ORCHESTRATOR_RESOURCE
            - ORCHESTRATOR_DEPLOYMENT_GPT4O
            - ORCHESTRATOR_DEPLOYMENT_GPT4_1
            - ORCHESTRATOR_DEPLOYMENT_GEMINI_2_5_PRO
    """
    # Load orchestrator configuration if available
    orchestrator_config = None
    orchestrator_endpoint = os.getenv("ORCHESTRATOR_ENDPOINT")

    if orchestrator_endpoint:
        # Asset ID for LLM profile (matches orchestrator deployment config)
        # Use a209289 which is the registered asset in the orchestrator
        asset_id = os.getenv("ORCHESTRATOR_ASSET_ID", "209289")
        profile_prefix = f"a{asset_id}"

        # Global headers required by orchestrator
        global_headers = {
            "x-tr-chat-profile-name": os.getenv(
                "ORCHESTRATOR_CHAT_PROFILE",
                f"{profile_prefix}-Leon-Skills"
            ),
            "x-tr-user-sensitivity": "blind",
            "x-tr-userid": "Leon-Skills",
            "x-tr-sessionid": "leon-skills-session",
            "x-tr-asset-id": asset_id,
            "x-tr-authorization": "leon-skills",
        }

        # Deployment configurations matching the orchestrator setup
        deployments = {
            "gpt-4o": DeploymentConfig(
                deployment=os.getenv(
                    "ORCHESTRATOR_DEPLOYMENT_GPT4O",
                    f"{profile_prefix}-gpt-4o-2024-08-06/deployments/gpt-4o-2024-08-06"
                ),
                model="gpt-4o",
                api_version="2025-01-01-preview",
                headers={"x-tr-llm-profile-key": f"{profile_prefix}-gpt-4o-2024-08-06"}
            ),
            "gpt-4-1": DeploymentConfig(
                deployment=os.getenv(
                    "ORCHESTRATOR_DEPLOYMENT_GPT4_1",
                    f"{profile_prefix}-gpt-4-1/deployments/gpt-4-1"
                ),
                model="gpt-4-1",
                api_version="2025-01-01-preview",
                headers={"x-tr-llm-profile-key": f"{profile_prefix}-gpt-4-1"}
            ),
            "o1-mini": DeploymentConfig(
                deployment=f"{profile_prefix}-o1-mini-2024-09-12/deployments/o1-mini-2024-09-12",
                model="o1-mini",
                api_version="2024-12-01-preview",
                headers={"x-tr-llm-profile-key": f"{profile_prefix}-o1-mini-2024-09-12"}
            ),
            "o3-mini": DeploymentConfig(
                deployment=f"{profile_prefix}-o3-mini-2025-01-31/deployments/o3-mini-2025-01-31",
                model="o3-mini",
                api_version="2024-12-01-preview",
                headers={"x-tr-llm-profile-key": f"{profile_prefix}-o3-mini-2025-01-31"}
            ),
            "o4-mini": DeploymentConfig(
                deployment=f"{profile_prefix}-o4-mini-2025-04-16/deployments/o4-mini-2025-04-16",
                model="o4-mini",
                api_version="2024-12-01-preview",
                headers={"x-tr-llm-profile-key": f"{profile_prefix}-o4-mini-2025-04-16"}
            ),
            "gemini-2-5-flash": DeploymentConfig(
                deployment=f"{profile_prefix}-gemini-2-5-flash/endpoints/openapi",
                model="google/gemini-2.5-flash",
                api_version="2024-12-01-preview",
                headers={"x-tr-llm-profile-key": f"{profile_prefix}-gemini-2-5-flash"}
            ),
            "gemini-2-5-pro": DeploymentConfig(
                deployment=os.getenv(
                    "ORCHESTRATOR_DEPLOYMENT_GEMINI_2_5_PRO",
                    f"{profile_prefix}-gemini-2-5-pro/endpoints/openapi"
                ),
                model="google/gemini-2.5-pro",
                api_version="2024-12-01-preview",
                headers={"x-tr-llm-profile-key": f"{profile_prefix}-gemini-2-5-pro"}
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
            headers=global_headers,
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
