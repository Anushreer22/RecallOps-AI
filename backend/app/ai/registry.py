from typing import Dict, Optional, List
from backend.app.core.config import settings
from backend.app.ai.base import BaseLLMProvider, LLMConfigurationError
from backend.app.ai.providers.openai_provider import OpenAIProvider
from backend.app.ai.providers.mock_provider import MockLLMProvider


class LLMProviderRegistry:
    """
    Registry for managing and resolving LLM providers.
    """

    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {}
        # Register standard providers
        self.register(OpenAIProvider())
        self.register(MockLLMProvider())

    def register(self, provider: BaseLLMProvider) -> None:
        self._providers[provider.provider_name.lower()] = provider

    def get(self, provider_name: Optional[str] = None) -> BaseLLMProvider:
        name = (provider_name or settings.LLM_PROVIDER or "openai").lower()
        if name not in self._providers:
            # If unknown, try default or raise error
            raise LLMConfigurationError(
                f"Configured LLM provider '{name}' is not registered. "
                f"Available providers: {list(self._providers.keys())}"
            )
        return self._providers[name]

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())


# Global singleton instance
provider_registry = LLMProviderRegistry()
