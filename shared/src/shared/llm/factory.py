"""Factory for creating LLM Orchestrator instances"""

from .orchestrator import LLMOrchestrator
from .config import LLMConfig


class LLMOrchestratorFactory:
    """Factory for creating LLM Orchestrator instances with explicit configuration"""

    @staticmethod
    def create(config: LLMConfig) -> LLMOrchestrator:
        """
        Create an LLM Orchestrator instance with the provided configuration.

        Args:
            config: LLM configuration with Azure OpenAI settings

        Returns:
            Configured LLMOrchestrator instance

        Example:
            ```python
            from shared.llm import LLMConfig, LLMOrchestratorFactory

            config = LLMConfig(
                endpoint="https://...",
                api_key="...",
            )
            llm = LLMOrchestratorFactory.create(config)
            ```
        """
        return LLMOrchestrator(config)
