import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.core.algorithms import ServiceTopologyGraph
from backend.app.models.auth import Service, ServiceDependency


class TopologyService:
    """
    Manages microservice dependency graphs, cycle detection, and blast radius calculation.
    Supports persistent database storage with organization-level graph isolation
    and dynamic in-memory graph rehydration.
    """

    def __init__(self):
        # In-memory graph cache keyed by organization_id (None for default global fallback)
        self._graphs: Dict[Optional[str], ServiceTopologyGraph] = {}
        self._default_graph = ServiceTopologyGraph()
        self._seed_in_memory_default(self._default_graph)
        self._graphs[None] = self._default_graph

    @property
    def graph(self) -> ServiceTopologyGraph:
        """Backwards compatibility property for existing tests that access topology_service.graph."""
        return self._default_graph

    def _seed_in_memory_default(self, target_graph: ServiceTopologyGraph):
        """Builds standard production microservice architecture graph in memory."""
        # Tier 0 Services
        target_graph.add_service("user-db", tier="TIER_0", owner="Database-SRE")
        target_graph.add_service("payment-gateway", tier="TIER_0", owner="Payments-Team")
        target_graph.add_service("redis-session-cache", tier="TIER_0", owner="Infra-Platform")
        target_graph.add_service("kafka-broker", tier="TIER_0", owner="Data-Platform")

        # Tier 1 Services
        target_graph.add_service("auth-service", tier="TIER_1", owner="Security-Team")
        target_graph.add_service("payment-service", tier="TIER_1", owner="Payments-Team")
        target_graph.add_service("inventory-service", tier="TIER_1", owner="Logistics-Team")
        target_graph.add_service("api-gateway", tier="TIER_1", owner="Core-Routing")

        # Tier 2 Services
        target_graph.add_service("notification-service", tier="TIER_2", owner="Growth-Team")
        target_graph.add_service("analytics-service", tier="TIER_2", owner="BI-Team")
        target_graph.add_service("checkout-web", tier="TIER_2", owner="Frontend-Team")

        # Dependencies (Source -> Target: Source relies on Target)
        target_graph.add_dependency("auth-service", "user-db")
        target_graph.add_dependency("auth-service", "redis-session-cache")
        target_graph.add_dependency("payment-service", "payment-gateway")
        target_graph.add_dependency("payment-service", "user-db")
        target_graph.add_dependency("inventory-service", "user-db")
        target_graph.add_dependency("notification-service", "kafka-broker")
        target_graph.add_dependency("api-gateway", "auth-service")
        target_graph.add_dependency("api-gateway", "payment-service")
        target_graph.add_dependency("api-gateway", "inventory-service")
        target_graph.add_dependency("checkout-web", "api-gateway")
        target_graph.add_dependency("checkout-web", "payment-service")
        target_graph.add_dependency("analytics-service", "kafka-broker")

    def seed_default_topology_for_org(
        self,
        db: Session,
        organization_id: str,
        project_id: Optional[str] = None
    ) -> None:
        """
        Seeds standard microservice topology into the persistent database
        for a given organization and initializes its graph cache.
        """
        default_services = [
            ("user-db", "TIER_0", "Database-SRE"),
            ("payment-gateway", "TIER_0", "Payments-Team"),
            ("redis-session-cache", "TIER_0", "Infra-Platform"),
            ("kafka-broker", "TIER_0", "Data-Platform"),
            ("auth-service", "TIER_1", "Security-Team"),
            ("payment-service", "TIER_1", "Payments-Team"),
            ("inventory-service", "TIER_1", "Logistics-Team"),
            ("api-gateway", "TIER_1", "Core-Routing"),
            ("notification-service", "TIER_2", "Growth-Team"),
            ("analytics-service", "TIER_2", "BI-Team"),
            ("checkout-web", "TIER_2", "Frontend-Team"),
        ]

        default_dependencies = [
            ("auth-service", "user-db"),
            ("auth-service", "redis-session-cache"),
            ("payment-service", "payment-gateway"),
            ("payment-service", "user-db"),
            ("inventory-service", "user-db"),
            ("notification-service", "kafka-broker"),
            ("api-gateway", "auth-service"),
            ("api-gateway", "payment-service"),
            ("api-gateway", "inventory-service"),
            ("checkout-web", "api-gateway"),
            ("checkout-web", "payment-service"),
            ("analytics-service", "kafka-broker"),
        ]

        # Insert services if not present
        for name, tier, owner in default_services:
            existing = db.query(Service).filter(
                Service.organization_id == organization_id,
                Service.name == name
            ).first()
            if not existing:
                svc = Service(
                    id=f"SVC-{uuid.uuid4().hex[:12]}",
                    organization_id=organization_id,
                    project_id=project_id,
                    name=name,
                    tier=tier,
                    owner=owner,
                    description=f"Seeded {name} service"
                )
                db.add(svc)

        db.commit()

        # Insert dependencies if not present
        for src, tgt in default_dependencies:
            existing_dep = db.query(ServiceDependency).filter(
                ServiceDependency.organization_id == organization_id,
                ServiceDependency.source_service == src,
                ServiceDependency.target_service == tgt
            ).first()
            if not existing_dep:
                dep = ServiceDependency(
                    organization_id=organization_id,
                    project_id=project_id,
                    source_service=src,
                    target_service=tgt,
                    dependency_type="DIRECT",
                    tier="TIER_1",
                    owner="Engineering"
                )
                db.add(dep)

        db.commit()
        self.rehydrate_from_db(db, organization_id=organization_id)

    def rehydrate_from_db(self, db: Session, organization_id: Optional[str] = None) -> ServiceTopologyGraph:
        """
        Reconstructs in-memory graph cache directly from persistent database tables
        for a given organization (or global if organization_id is None).
        """
        graph = ServiceTopologyGraph()

        # Query services
        svc_query = db.query(Service)
        if organization_id:
            svc_query = svc_query.filter(Service.organization_id == organization_id)
        services = svc_query.all()

        for s in services:
            graph.add_service(s.name, tier=s.tier, owner=s.owner)

        # Query dependencies
        dep_query = db.query(ServiceDependency)
        if organization_id:
            dep_query = dep_query.filter(ServiceDependency.organization_id == organization_id)
        dependencies = dep_query.all()

        for d in dependencies:
            graph.add_dependency(d.source_service, d.target_service)

        self._graphs[organization_id] = graph
        if organization_id is None:
            self._default_graph = graph

        return graph

    def get_graph(
        self,
        organization_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> ServiceTopologyGraph:
        """
        Retrieves the graph for an organization.
        If not loaded and db is provided, rehydrates from database.
        """
        if organization_id in self._graphs:
            return self._graphs[organization_id]

        if db is not None and organization_id is not None:
            # Check if there are records in the database
            svc_count = db.query(Service).filter(Service.organization_id == organization_id).count()
            if svc_count == 0:
                self.seed_default_topology_for_org(db, organization_id)
            else:
                self.rehydrate_from_db(db, organization_id)
            return self._graphs.get(organization_id, self._default_graph)

        return self._graphs.get(organization_id, self._default_graph)

    def get_blast_radius(
        self,
        failed_service: str,
        organization_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Calculates downstream blast radius using BFS on the organization's topology graph."""
        active_graph = self.get_graph(organization_id=organization_id, db=db)
        return active_graph.calculate_blast_radius(failed_service)

    def check_for_cycles(
        self,
        organization_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> List[List[str]]:
        """Detects circular dependencies in the organization's topology graph using DFS."""
        active_graph = self.get_graph(organization_id=organization_id, db=db)
        return active_graph.detect_cycles()

    def register_dependency(
        self,
        source_service: str,
        target_service: str,
        tier: str = "TIER_1",
        owner: str = "Engineering",
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        dependency_type: str = "DIRECT",
        db: Optional[Session] = None
    ) -> ServiceDependency:
        """
        Registers a dependency both in memory and persistently in the database.
        """
        active_graph = self.get_graph(organization_id=organization_id, db=db)
        active_graph.add_service(source_service, tier=tier, owner=owner)
        active_graph.add_service(target_service, tier=tier, owner=owner)
        active_graph.add_dependency(source_service, target_service)

        dep_record = None
        if db is not None:
            # Ensure services exist in DB
            for svc_name in [source_service, target_service]:
                existing_svc = db.query(Service).filter(
                    Service.organization_id == organization_id,
                    Service.name == svc_name
                ).first()
                if not existing_svc and organization_id:
                    db.add(Service(
                        id=f"SVC-{uuid.uuid4().hex[:12]}",
                        organization_id=organization_id,
                        project_id=project_id,
                        name=svc_name,
                        tier=tier,
                        owner=owner
                    ))
            db.commit()

            # Insert or update dependency
            dep_record = db.query(ServiceDependency).filter(
                ServiceDependency.organization_id == organization_id,
                ServiceDependency.source_service == source_service,
                ServiceDependency.target_service == target_service
            ).first()

            if not dep_record:
                dep_record = ServiceDependency(
                    organization_id=organization_id,
                    project_id=project_id,
                    source_service=source_service,
                    target_service=target_service,
                    dependency_type=dependency_type,
                    tier=tier,
                    owner=owner
                )
                db.add(dep_record)
                db.commit()
                db.refresh(dep_record)

        return dep_record

    def remove_dependency(
        self,
        dependency_id: int,
        organization_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> bool:
        """Deletes a dependency from the database and updates the graph."""
        if db is None:
            return False

        query = db.query(ServiceDependency).filter(ServiceDependency.id == dependency_id)
        if organization_id:
            query = query.filter(ServiceDependency.organization_id == organization_id)
        dep = query.first()

        if not dep:
            return False

        db.delete(dep)
        db.commit()

        # Rehydrate graph
        self.rehydrate_from_db(db, organization_id=organization_id)
        return True

    def service_count(self, organization_id: Optional[str] = None, db: Optional[Session] = None) -> int:
        """Returns the number of nodes in the organization's graph."""
        active_graph = self.get_graph(organization_id=organization_id, db=db)
        return len(active_graph.node_metadata)


# Global shared instance
topology_service = TopologyService()
