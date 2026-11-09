from typing import Dict, Any, List
from backend.app.core.algorithms import ServiceTopologyGraph


class TopologyService:
    """Manages microservice dependency graphs, cycle detection, and blast radius calculation."""

    def __init__(self):
        self.graph = ServiceTopologyGraph()
        self._seed_default_topology()

    def _seed_default_topology(self):
        """Builds standard production microservice architecture graph."""
        # Tier 0 Services
        self.graph.add_service("user-db", tier="TIER_0", owner="Database-SRE")
        self.graph.add_service("payment-gateway", tier="TIER_0", owner="Payments-Team")
        self.graph.add_service("redis-session-cache", tier="TIER_0", owner="Infra-Platform")
        self.graph.add_service("kafka-broker", tier="TIER_0", owner="Data-Platform")

        # Tier 1 Services
        self.graph.add_service("auth-service", tier="TIER_1", owner="Security-Team")
        self.graph.add_service("payment-service", tier="TIER_1", owner="Payments-Team")
        self.graph.add_service("inventory-service", tier="TIER_1", owner="Logistics-Team")
        self.graph.add_service("api-gateway", tier="TIER_1", owner="Core-Routing")

        # Tier 2 Services
        self.graph.add_service("notification-service", tier="TIER_2", owner="Growth-Team")
        self.graph.add_service("analytics-service", tier="TIER_2", owner="BI-Team")
        self.graph.add_service("checkout-web", tier="TIER_2", owner="Frontend-Team")

        # Dependencies (Source -> Target: Source relies on Target)
        # If Target fails, Source is impacted downstream
        self.graph.add_dependency("auth-service", "user-db")
        self.graph.add_dependency("auth-service", "redis-session-cache")

        self.graph.add_dependency("payment-service", "payment-gateway")
        self.graph.add_dependency("payment-service", "user-db")

        self.graph.add_dependency("inventory-service", "user-db")

        self.graph.add_dependency("notification-service", "kafka-broker")

        self.graph.add_dependency("api-gateway", "auth-service")
        self.graph.add_dependency("api-gateway", "payment-service")
        self.graph.add_dependency("api-gateway", "inventory-service")

        self.graph.add_dependency("checkout-web", "api-gateway")
        self.graph.add_dependency("checkout-web", "payment-service")

        self.graph.add_dependency("analytics-service", "kafka-broker")

    def get_blast_radius(self, failed_service: str) -> Dict[str, Any]:
        return self.graph.calculate_blast_radius(failed_service)

    def check_for_cycles(self) -> List[List[str]]:
        return self.graph.detect_cycles()

    def register_dependency(self, source_service: str, target_service: str, tier: str = "TIER_1", owner: str = "Engineering"):
        self.graph.add_service(source_service, tier=tier, owner=owner)
        self.graph.add_service(target_service, tier=tier, owner=owner)
        self.graph.add_dependency(source_service, target_service)

    def service_count(self) -> int:
        return len(self.graph.node_metadata)


# Global shared instance
topology_service = TopologyService()
