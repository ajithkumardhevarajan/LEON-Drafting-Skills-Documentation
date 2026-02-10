"""LLM Orchestrator Service for Azure OpenAI and Standard OpenAI"""

from openai import AzureOpenAI
from typing import List, Dict, Optional, Type, TypeVar
from pydantic import BaseModel
import logging
from .config import LLMConfig
from .constants import is_mini_model, Models
from .azure_token import generate_azure_token, AzureTokenConfig

T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)

# Models that use standard OpenAI URL pattern instead of Azure OpenAI
# These use: {endpoint}/{deployment}/chat/completions
# Instead of: {endpoint}/openai/deployments/{deployment}/chat/completions
STANDARD_OPENAI_MODELS = {"gemini-2-5-pro", "gemini-2-5-flash", "gemini-3-pro-preview", "simba"}


class LLMOrchestrator:
    """Azure OpenAI client for urgent drafting with LLM orchestration"""

    def __init__(self, config: LLMConfig):
        """
        Initialize LLM Orchestrator

        Args:
            config: LLM configuration with Azure OpenAI settings
        """
        self.config = config
        self._client = None

    def _uses_orchestrator(self) -> bool:
        """Check if orchestrator configuration is available"""
        return self.config.orchestrator is not None

    def _is_mini_model(self, model: str) -> bool:
        """Check if model is a mini model that doesn't support system messages"""
        return is_mini_model(model)

    def _uses_standard_openai_pattern(self, model: str) -> bool:
        """Check if model uses standard OpenAI URL pattern instead of Azure OpenAI.

        Standard OpenAI: {endpoint}/{deployment}/chat/completions
        Azure OpenAI: {endpoint}/openai/deployments/{deployment}/chat/completions
        """
        return model in STANDARD_OPENAI_MODELS

    def _get_deployment(self, model: str) -> str:
        """Get deployment name for a model"""
        if self._uses_orchestrator():
            orchestrator = self.config.orchestrator
            deployment_config = orchestrator.deployments.get(model)
            if not deployment_config:
                logger.warning(f"No orchestrator deployment found for {model}, using model name as deployment")
                return model
            return deployment_config.deployment

        # Fallback to direct Azure OpenAI deployments
        if model == "gpt-4-1":
            return self.config.gpt4_1_deployment
        elif model == "gpt-4o":
            return self.config.gpt4o_deployment
        else:
            return model

    def _get_api_version(self, model: str) -> str:
        """Get API version for a model, with deployment-specific override"""
        if self._uses_orchestrator():
            orchestrator = self.config.orchestrator
            deployment_config = orchestrator.deployments.get(model)
            if deployment_config and deployment_config.api_version:
                return deployment_config.api_version
            return orchestrator.api_version
        return self.config.api_version

    def _get_model_name(self, model: str) -> str:
        """Get actual model name for a deployment"""
        if self._uses_orchestrator():
            orchestrator = self.config.orchestrator
            deployment_config = orchestrator.deployments.get(model)
            if deployment_config and deployment_config.model:
                return deployment_config.model
        return model

    def _get_deployment_headers(self, model: str) -> Dict[str, str]:
        """Get deployment-specific headers"""
        if self._uses_orchestrator():
            orchestrator = self.config.orchestrator
            deployment_config = orchestrator.deployments.get(model)
            if deployment_config and deployment_config.headers:
                return deployment_config.headers
        return {}

    async def _initialize_client(
        self,
        model: str,
        deployment: Optional[str] = None
    ) -> AzureOpenAI:
        """
        Initialize Azure OpenAI client with orchestrator support.

        Creates a new client with token authentication if using orchestrator,
        otherwise uses direct Azure OpenAI with API key.

        Args:
            model: Model name to get configuration for
            deployment: Optional deployment override

        Returns:
            Configured AzureOpenAI client
        """
        if self._uses_orchestrator():
            orchestrator = self.config.orchestrator

            # Debug: log configuration status (not values!)
            logger.info(
                f"Orchestrator config: endpoint={orchestrator.endpoint}, "
                f"api_key={'SET' if orchestrator.api_key else 'NOT SET'}, "
                f"tenant_id={'SET' if orchestrator.tenant_id else 'NOT SET'}, "
                f"client_id={'SET' if orchestrator.client_id else 'NOT SET'}, "
                f"client_secret={'SET' if orchestrator.client_secret else 'NOT SET'}, "
                f"resource={'SET' if orchestrator.resource else 'NOT SET'}"
            )

            # Generate Azure AD token
            token = None
            if orchestrator.tenant_id and orchestrator.client_id and orchestrator.client_secret:
                token_config = AzureTokenConfig(
                    tenant_id=orchestrator.tenant_id,
                    client_id=orchestrator.client_id,
                    client_secret=orchestrator.client_secret,
                    resource=orchestrator.resource or "https://cognitiveservices.azure.com/.default"
                )
                token = await generate_azure_token(token_config)

                if not token:
                    raise RuntimeError("Failed to generate Azure AD token for LLM Orchestrator")

            # Build headers
            default_headers = {
                "Content-Type": "application/json",
            }

            # Add authentication headers
            # Note: Some orchestrators may require both token AND api-key
            if token:
                default_headers["Authorization"] = f"Bearer {token}"
                logger.info("Using Azure AD token authentication for orchestrator")

            # Always add api-key if available (may be needed alongside token)
            if orchestrator.api_key:
                default_headers["api-key"] = orchestrator.api_key
                logger.debug("Added api-key header to request")

            # Ensure at least one auth method is present
            if not token and not orchestrator.api_key:
                raise RuntimeError("No authentication method available for orchestrator")

            # Add global headers from config
            if orchestrator.headers:
                default_headers.update(orchestrator.headers)
                logger.debug(f"Applied {len(orchestrator.headers)} global headers")

            # Add deployment-specific headers
            deployment_headers = self._get_deployment_headers(model)
            if deployment_headers:
                default_headers.update(deployment_headers)
                logger.debug(f"Applied {len(deployment_headers)} deployment-specific headers")

            actual_deployment = deployment or self._get_deployment(model)
            api_key_value = orchestrator.api_key if orchestrator.api_key else "not-used-with-token-auth"

            # Check if this model uses standard OpenAI URL pattern (gemini, simba)
            # These models use azure_deployment in client init + actual model name in API call
            if self._uses_standard_openai_pattern(model):
                logger.info(
                    f"Creating Azure OpenAI client (gemini pattern): "
                    f"endpoint={orchestrator.endpoint}, deployment={actual_deployment}, "
                    f"model_name={self._get_model_name(model)}"
                )

                client = AzureOpenAI(
                    api_key=api_key_value,
                    api_version=self._get_api_version(model),
                    azure_endpoint=orchestrator.endpoint,
                    azure_deployment=actual_deployment,  # Set deployment in client
                    default_headers=default_headers
                )

                return client

            else:
                # Standard Azure OpenAI pattern (gpt models)
                # These use deployment name as model parameter in API call
                logger.info(
                    f"Creating Azure OpenAI client: endpoint={orchestrator.endpoint}, "
                    f"model={model}, deployment={actual_deployment}"
                )

                client = AzureOpenAI(
                    api_key=api_key_value,
                    api_version=self._get_api_version(model),
                    azure_endpoint=orchestrator.endpoint,
                    default_headers=default_headers
                )

                return client

        else:
            # Fallback: Direct Azure OpenAI connection
            logger.info(f"Creating direct Azure OpenAI client: endpoint={self.config.endpoint}")
            return AzureOpenAI(
                api_key=self.config.api_key,
                api_version=self.config.api_version,
                azure_endpoint=self.config.endpoint,
            )

    async def invoke(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4-1",
        temperature: float = 0.05,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Invoke LLM with messages and return response

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use ("gpt-4-1", "gpt-4o", "o1-mini", etc.)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response

        Returns:
            Generated text response
        """
        try:
            # Initialize client with model-specific configuration
            client = await self._initialize_client(model)

            # Get deployment and model name
            deployment = self._get_deployment(model)
            model_name = self._get_model_name(model)

            # Handle mini models: convert system messages to user messages
            formatted_messages = messages
            if self._is_mini_model(model):
                formatted_messages = [
                    {"role": "user", "content": msg["content"]} if msg["role"] == "system" else msg
                    for msg in messages
                ]
                logger.debug(
                    f"Converted system messages to user messages for mini model {model}"
                )

            # For standard OpenAI pattern (gemini), use actual model name
            # For Azure OpenAI pattern, use deployment name
            api_model = model_name if self._uses_standard_openai_pattern(model) else deployment

            logger.info(
                f"LLM Request: model={model}, deployment={deployment}, api_model={api_model}, "
                f"messages={len(formatted_messages)}, temp={temperature}, "
                f"uses_orchestrator={self._uses_orchestrator()}"
            )

            # Make the API call
            response = client.chat.completions.create(
                model=api_model,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            content = response.choices[0].message.content

            logger.info(
                f"LLM Response: {len(content)} characters, "
                f"tokens={response.usage.total_tokens if response.usage else 'N/A'}"
            )

            return content

        except Exception as e:
            logger.error(
                f"LLM invocation failed: model={model}, error={str(e)}",
                exc_info=True
            )
            raise

    async def invoke_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        model: str = "gpt-4o",
        temperature: float = 0.05,
        max_tokens: Optional[int] = None
    ) -> T:
        """
        Invoke LLM with structured output using Pydantic model schema

        This method uses OpenAI's structured output feature to guarantee
        the response matches the provided Pydantic model schema. This is
        much more reliable than asking the LLM to return JSON text.

        Args:
            messages: List of message dicts with 'role' and 'content'
            response_model: Pydantic model class defining the response structure
            model: Model to use (default "gpt-4o" - structured outputs require compatible models)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response

        Returns:
            Parsed Pydantic model instance with guaranteed schema compliance

        Raises:
            RuntimeError: If LLM call fails or response cannot be parsed

        Example:
            ```python
            class Answer(BaseModel):
                action: Literal["yes", "no"]
                reason: str

            result = await llm.invoke_structured(
                messages=[{"role": "user", "content": "Is the sky blue?"}],
                response_model=Answer
            )
            print(result.action)  # "yes"
            print(result.reason)  # "The sky appears blue due to..."
            ```
        """
        try:
            # Initialize client with model-specific configuration
            client = await self._initialize_client(model)

            # Get deployment and model name
            deployment = self._get_deployment(model)
            model_name = self._get_model_name(model)

            # Handle mini models: convert system messages to user messages
            formatted_messages = messages
            if self._is_mini_model(model):
                formatted_messages = [
                    {"role": "user", "content": msg["content"]} if msg["role"] == "system" else msg
                    for msg in messages
                ]
                logger.debug(
                    f"Converted system messages to user messages for mini model {model}"
                )

            # For standard OpenAI pattern (gemini), use actual model name
            # For Azure OpenAI pattern, use deployment name
            api_model = model_name if self._uses_standard_openai_pattern(model) else deployment

            logger.info(
                f"LLM Structured Request: model={model}, deployment={deployment}, api_model={api_model}, "
                f"response_model={response_model.__name__}, messages={len(formatted_messages)}, "
                f"temp={temperature}, uses_orchestrator={self._uses_orchestrator()}"
            )

            # Make the API call with structured output
            completion = client.beta.chat.completions.parse(
                model=api_model,
                messages=formatted_messages,
                response_format=response_model,
                temperature=temperature,
                max_tokens=max_tokens
            )

            # Extract parsed response
            parsed_response = completion.choices[0].message.parsed

            if parsed_response is None:
                raise RuntimeError(
                    f"LLM returned null parsed response. Refusal: {completion.choices[0].message.refusal}"
                )

            logger.info(
                f"LLM Structured Response: model={response_model.__name__}, "
                f"tokens={completion.usage.total_tokens if completion.usage else 'N/A'}"
            )

            return parsed_response

        except Exception as e:
            logger.error(
                f"LLM structured invocation failed: model={model}, "
                f"response_model={response_model.__name__}, error={str(e)}",
                exc_info=True
            )
            raise
