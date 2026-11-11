from __future__ import annotations
import abc
from typing import Dict, Any, Optional
from backend.app.ai.schemas import StructuredInvestigationReport, EvidenceCollection


class LLMError(Exception):
    """Base exception for all LLM provider errors."""
    pass


class LLMConfigurationError(LLMError):
    """Raised when an LLM provider is improperly configured or missing API credentials."""
    pass


class LLMAuthenticationError(LLMError):
    """Raised when provider authentication fails (e.g. invalid API key)."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM API request times out."""
    pass


class LLMResponseParsingError(LLMError):
    """Raised when the LLM returns invalid JSON or schema validation fails."""
    pass


class BaseLLMProvider(abc.ABC):
    """
    Abstract interface for LLM investigation providers (OpenAI, Mock, etc.).
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Identifier of the LLM provider (e.g. 'openai', 'mock')."""
        pass

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Active model identifier (e.g. 'gpt-4o-mini')."""
        pass

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider is properly configured and ready to accept requests."""
        pass

    @abc.abstractmethod
    def validate_configuration(self) -> None:
        """
        Validates configuration and credentials.
        Raises LLMConfigurationError if invalid or missing credentials.
        """
        pass

    @abc.abstractmethod
    def generate_investigation(
        self,
        system_prompt: str,
        user_prompt: str,
        evidence: EvidenceCollection,
        temperature: Optional[float] = None
    ) -> StructuredInvestigationReport:
        """
        Calls the LLM with prompt and evidence context to produce a structured investigation report.
        """
        pass
