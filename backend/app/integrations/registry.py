from typing import Dict, Optional, List
from backend.app.integrations.base import BaseWebhookAdapter
from backend.app.integrations.pagerduty import PagerDutyAdapter
from backend.app.integrations.datadog import DatadogAdapter
from backend.app.integrations.alertmanager import AlertmanagerAdapter


class WebhookAdapterRegistry:
    """
    Registry for managing available webhook adapters.
    """

    def __init__(self):
        self._adapters: Dict[str, BaseWebhookAdapter] = {}
        # Register standard built-in adapters
        self.register(PagerDutyAdapter())
        self.register(DatadogAdapter())
        self.register(AlertmanagerAdapter())

    def register(self, adapter: BaseWebhookAdapter) -> None:
        self._adapters[adapter.provider.lower()] = adapter

    def get(self, provider: str) -> Optional[BaseWebhookAdapter]:
        return self._adapters.get(provider.lower())

    def list_providers(self) -> List[str]:
        return list(self._adapters.keys())


# Global singleton instance
adapter_registry = WebhookAdapterRegistry()
