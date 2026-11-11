import json
import time
from typing import Optional
import httpx
from pydantic import ValidationError

from backend.app.core.config import settings
from backend.app.ai.base import (
    BaseLLMProvider,
    LLMError,
    LLMConfigurationError,
    LLMAuthenticationError,
    LLMTimeoutError,
    LLMResponseParsingError,
)
from backend.app.ai.schemas import StructuredInvestigationReport, EvidenceCollection


class OpenAIProvider(BaseLLMProvider):
    """
    Production OpenAI LLM Provider utilizing the official Chat Completions API with structured JSON output.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        base_url: str = "https://api.openai.com/v1"
    ):
        self._api_key = api_key or settings.LLM_API_KEY
        self._model_name = model_name or settings.LLM_MODEL
        self._timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.LLM_TIMEOUT_SECONDS
        self._max_retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES
        self._base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def validate_configuration(self) -> None:
        if not self._api_key or not self._api_key.strip():
            raise LLMConfigurationError(
                "OpenAI provider is not configured: LLM_API_KEY is missing or empty. "
                "Set LLM_API_KEY in your environment to enable real LLM investigations."
            )

    def generate_investigation(
        self,
        system_prompt: str,
        user_prompt: str,
        evidence: EvidenceCollection,
        temperature: Optional[float] = None
    ) -> StructuredInvestigationReport:
        self.validate_configuration()

        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temp,
            "response_format": {"type": "json_object"}
        }

        retries = 0
        last_error = None

        while retries <= self._max_retries:
            try:
                with httpx.Client(timeout=self._timeout_seconds) as client:
                    resp = client.post(url, headers=headers, json=payload)

                    if resp.status_code == 401:
                        raise LLMAuthenticationError("OpenAI authentication failed: invalid or revoked API key.")
                    if resp.status_code == 429:
                        raise LLMError(f"OpenAI rate limit exceeded: {resp.text}")
                    if resp.status_code >= 500:
                        retries += 1
                        last_error = LLMError(f"OpenAI service error (HTTP {resp.status_code}): {resp.text}")
                        time.sleep(0.5 * retries)
                        continue

                    resp.raise_for_status()
                    data = resp.json()

                    # Extract model output
                    choices = data.get("choices") or []
                    if not choices:
                        raise LLMResponseParsingError("OpenAI returned empty choices in response.")

                    message_content = choices[0].get("message", {}).get("content", "")
                    if not message_content:
                        raise LLMResponseParsingError("OpenAI returned empty message content.")

                    try:
                        parsed_json = json.loads(message_content)
                    except json.JSONDecodeError as exc:
                        raise LLMResponseParsingError(f"Malformed JSON returned by OpenAI: {str(exc)}")

                    try:
                        report = StructuredInvestigationReport.model_validate(parsed_json)
                        return report
                    except ValidationError as val_err:
                        raise LLMResponseParsingError(f"LLM response failed schema validation: {str(val_err)}")

            except httpx.TimeoutException as exc:
                retries += 1
                last_error = LLMTimeoutError(
                    f"OpenAI API request timed out after {self._timeout_seconds}s (attempt {retries}/{self._max_retries + 1}): {str(exc)}"
                )
                if retries <= self._max_retries:
                    time.sleep(0.5 * retries)
                    continue
                raise last_error

            except (LLMAuthenticationError, LLMResponseParsingError, LLMConfigurationError):
                raise

            except Exception as e:
                retries += 1
                last_error = LLMError(f"Failed to communicate with OpenAI API: {str(e)}")
                if retries <= self._max_retries:
                    time.sleep(0.5 * retries)
                    continue
                raise last_error

        if last_error:
            raise last_error
        raise LLMError("OpenAI request failed after maximum retries.")
