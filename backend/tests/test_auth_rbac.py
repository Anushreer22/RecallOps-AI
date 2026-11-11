import json
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.db.base import Base
import backend.app.models
from backend.app.models.auth import (
    User,
    Organization,
    OrganizationMembership,
    Project,
    Service,
    ServiceDependency,
    AuditLog
)
from backend.app.models.incident import Incident
from backend.app.schemas.incident import IncidentCreate, ResolutionCreate
from backend.app.auth.security import hash_password, verify_password, validate_password_strength
from backend.app.auth.jwt import create_access_token, decode_access_token
from backend.app.auth.dependencies import (
    get_current_user,
    get_current_org_context,
)
from backend.app.auth.permissions import (
    require_role,
    require_admin,
    require_engineer,
    require_viewer
)
from backend.app.auth.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    OrganizationCreate,
    MemberAddRequest,
    MemberUpdateRequest,
    ProjectCreate,
    ServiceCreate,
    DependencyCreate,
)
from backend.app.api.v1.endpoints.auth import register, login, get_current_user_profile
from backend.app.api.v1.endpoints.organizations import (
    create_organization,
    list_user_organizations,
    get_organization,
    list_organization_members,
    add_organization_member,
    update_member_role,
)
from backend.app.api.v1.endpoints.projects import (
    create_project,
    list_projects,
    get_project,
)
from backend.app.api.v1.endpoints.services import (
    create_service,
    list_services,
    get_service,
    add_service_dependency,
    get_service_dependencies,
    get_service_blast_radius,
)
from backend.app.api.v1.endpoints.topology import (
    create_dependency,
    delete_dependency,
    list_dependencies,
    get_topology_blast_radius,
    detect_topology_cycles,
)
from backend.app.api.v1.endpoints.incidents import (
    create_incident,
    list_incidents,
    get_incident,
    diagnose_incident,
    resolve_incident,
)
from backend.app.api.v1.endpoints.investigations import (
    run_incident_investigation,
    list_incident_investigations,
    get_investigation_details,
    submit_investigation_feedback,
)
from backend.app.api.v1.endpoints.audit import get_audit_logs
from backend.app.services.topology_service import TopologyService
from backend.app.services.audit_service import audit_service
from backend.app.ai.providers.mock_provider import MockLLMProvider
from backend.app.ai.registry import provider_registry
from backend.app.ai.schemas import InvestigationFeedbackCreate


# Isolated in-memory database with StaticPool for thread-safe test execution
auth_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
AuthTestSession = sessionmaker(autocommit=False, autoflush=False, bind=auth_test_engine)


class DummyClient:
    host = "127.0.0.1"


class DummyRequest:
    client = DummyClient()


dummy_request = DummyRequest()


@pytest.fixture(scope="module", autouse=True)
def setup_auth_db():
    Base.metadata.create_all(bind=auth_test_engine)
    yield
    Base.metadata.drop_all(bind=auth_test_engine)


@pytest.fixture
def db():
    session = AuthTestSession()
    try:
        yield session
    finally:
        session.close()


# ============================================================================
# 1. Password Hashing & Complexity Validation
# ============================================================================

def test_password_hashing_and_verification():
    plain = "SecureP@ssw0rd2026!"
    hashed = hash_password(plain)

    assert hashed != plain
    assert hashed.startswith("$argon2id$")
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongP@ssword", hashed) is False


def test_password_complexity_validation():
    # Less than 8 characters
    with pytest.raises(HTTPException) as exc1:
        validate_password_strength("Pass1!")
    assert exc1.value.status_code == 400
    assert "at least" in exc1.value.detail

    # No letters
    with pytest.raises(HTTPException) as exc2:
        validate_password_strength("1234567890!")
    assert exc2.value.status_code == 400
    assert "letter" in exc2.value.detail

    # No numbers or symbols
    with pytest.raises(HTTPException) as exc3:
        validate_password_strength("AllLettersOnly")
    assert exc3.value.status_code == 400
    assert "number or special character" in exc3.value.detail

    # Valid password passes without exception
    validate_password_strength("ValidP@ssword123")


# ============================================================================
# 2. JWT Generation & Verification
# ============================================================================

def test_jwt_creation_and_decoding():
    payload = {"sub": "USR-12345", "email": "test@recallops.ai", "role": "ADMIN"}
    token = create_access_token(payload)
    assert isinstance(token, str)

    decoded = decode_access_token(token)
    assert decoded["sub"] == "USR-12345"
    assert decoded["email"] == "test@recallops.ai"
    assert decoded["role"] == "ADMIN"
    assert "exp" in decoded
    assert "iat" in decoded


def test_jwt_tampered_or_invalid():
    with pytest.raises(HTTPException) as exc:
        decode_access_token("invalid.token.structure")
    assert exc.value.status_code == 401


# ============================================================================
# 3. User Registration, Login & Authentication Flows
# ============================================================================

def test_user_registration_flow(db):
    req = UserRegisterRequest(
        email="alice@company.com",
        password="AlicePassword123!",
        full_name="Alice SRE",
        organization_name="Acme Corp"
    )
    resp = register(payload=req, request=dummy_request, db=db)

    assert resp.access_token is not None
    assert resp.user.email == "alice@company.com"
    assert resp.user.full_name == "Alice SRE"
    assert len(resp.user.memberships) == 1
    assert resp.user.memberships[0].role == "ADMIN"
    assert resp.user.memberships[0].organization_name == "Acme Corp"

    # User in database
    db_user = db.query(User).filter(User.email == "alice@company.com").first()
    assert db_user is not None
    assert verify_password("AlicePassword123!", db_user.hashed_password) is True

    # Default organization created with seeded microservices
    org_id = resp.user.memberships[0].organization_id
    services = db.query(Service).filter(Service.organization_id == org_id).all()
    assert len(services) >= 10


def test_user_registration_duplicate_email(db):
    req = UserRegisterRequest(
        email="alice@company.com",
        password="AnotherPassword123!",
        full_name="Alice Duplicate"
    )
    with pytest.raises(HTTPException) as exc:
        register(payload=req, request=dummy_request, db=db)
    assert exc.value.status_code == 409


def test_user_login_success(db):
    login_req = UserLoginRequest(
        email="alice@company.com",
        password="AlicePassword123!"
    )
    resp = login(payload=login_req, request=dummy_request, db=db)
    assert resp.access_token is not None
    assert resp.user.email == "alice@company.com"


def test_user_login_invalid_password(db):
    login_req = UserLoginRequest(
        email="alice@company.com",
        password="WrongPassword123!"
    )
    with pytest.raises(HTTPException) as exc:
        login(payload=login_req, request=dummy_request, db=db)
    assert exc.value.status_code == 401


def test_user_login_nonexistent_user(db):
    login_req = UserLoginRequest(
        email="ghost@company.com",
        password="GhostPassword123!"
    )
    with pytest.raises(HTTPException) as exc:
        login(payload=login_req, request=dummy_request, db=db)
    assert exc.value.status_code == 401


def test_get_current_user_profile(db):
    user = db.query(User).filter(User.email == "alice@company.com").first()
    profile = get_current_user_profile(user=user)
    assert profile.email == "alice@company.com"
    assert len(profile.memberships) >= 1


# ============================================================================
# 4. RBAC Roles, Hierarchy & Membership Permissions
# ============================================================================

def test_rbac_dependencies_and_hierarchy(db):
    # Setup test organization and 3 users: Admin, Engineer, Viewer
    org = Organization(id="ORG-TEST-RBAC", name="RBAC Test Org", slug="rbac-test-org")
    db.add(org)

    u_admin = User(id="USR-A", email="admin@test.com", hashed_password="h", full_name="Admin User")
    u_eng = User(id="USR-E", email="eng@test.com", hashed_password="h", full_name="Eng User")
    u_view = User(id="USR-V", email="view@test.com", hashed_password="h", full_name="View User")
    db.add_all([u_admin, u_eng, u_view])
    db.commit()

    m_admin = OrganizationMembership(id="MEM-A", organization_id=org.id, user_id=u_admin.id, role="ADMIN")
    m_eng = OrganizationMembership(id="MEM-E", organization_id=org.id, user_id=u_eng.id, role="ENGINEER")
    m_view = OrganizationMembership(id="MEM-V", organization_id=org.id, user_id=u_view.id, role="VIEWER")
    db.add_all([m_admin, m_eng, m_view])
    db.commit()

    # 1. require_admin check
    admin_checker = require_admin
    assert admin_checker(m_admin) == m_admin
    with pytest.raises(HTTPException) as exc1:
        admin_checker(m_eng)
    assert exc1.value.status_code == 403

    with pytest.raises(HTTPException) as exc2:
        admin_checker(m_view)
    assert exc2.value.status_code == 403

    # 2. require_engineer check
    eng_checker = require_engineer
    assert eng_checker(m_admin) == m_admin
    assert eng_checker(m_eng) == m_eng
    with pytest.raises(HTTPException) as exc3:
        eng_checker(m_view)
    assert exc3.value.status_code == 403

    # 3. require_viewer check
    view_checker = require_viewer
    assert view_checker(m_admin) == m_admin
    assert view_checker(m_eng) == m_eng
    assert view_checker(m_view) == m_view


def test_organization_membership_management_rbac(db):
    # Register bob
    req_bob = UserRegisterRequest(
        email="bob@company.com",
        password="BobPassword123!",
        full_name="Bob Admin",
        organization_name="Beta Org"
    )
    resp_bob = register(payload=req_bob, request=dummy_request, db=db)
    org_id = resp_bob.user.memberships[0].organization_id

    # Create user charlie without membership
    charlie = User(
        id="USR-CHARLIE",
        email="charlie@company.com",
        hashed_password=hash_password("CharliePass123!"),
        full_name="Charlie Dev"
    )
    db.add(charlie)
    db.commit()

    bob_user = db.query(User).filter(User.id == resp_bob.user.id).first()

    # Bob (Admin) adds Charlie as ENGINEER
    add_req = MemberAddRequest(email="charlie@company.com", role="ENGINEER")
    member_resp = add_organization_member(org_id=org_id, payload=add_req, user=bob_user, db=db)
    assert member_resp.email == "charlie@company.com"
    assert member_resp.role == "ENGINEER"

    # Non-admin (Charlie) attempting to add members fails with 403
    charlie_user = db.query(User).filter(User.id == charlie.id).first()
    with pytest.raises(HTTPException) as exc:
        add_organization_member(
            org_id=org_id,
            payload=MemberAddRequest(email="dave@company.com", role="VIEWER"),
            user=charlie_user,
            db=db
        )
    assert exc.value.status_code == 403

    # Bob (Admin) updates Charlie's role to VIEWER
    upd_resp = update_member_role(
        org_id=org_id,
        target_user_id=charlie.id,
        payload=MemberUpdateRequest(role="VIEWER"),
        user=bob_user,
        db=db
    )
    assert upd_resp.role == "VIEWER"

    # Charlie attempting to update role fails with 403
    with pytest.raises(HTTPException) as exc2:
        update_member_role(
            org_id=org_id,
            target_user_id=bob_user.id,
            payload=MemberUpdateRequest(role="VIEWER"),
            user=charlie_user,
            db=db
        )
    assert exc2.value.status_code == 403


# ============================================================================
# 5. Organization-Scoped Projects & Services
# ============================================================================

def test_project_crud_and_tenant_isolation(db):
    org1 = Organization(id="ORG-P1", name="Project Org 1", slug="proj-org-1")
    org2 = Organization(id="ORG-P2", name="Project Org 2", slug="proj-org-2")
    db.add_all([org1, org2])

    u1 = User(id="USR-P1", email="p1@test.com", hashed_password="h", full_name="User P1")
    u2 = User(id="USR-P2", email="p2@test.com", hashed_password="h", full_name="User P2")
    db.add_all([u1, u2])
    db.commit()

    m1_eng = OrganizationMembership(id="MEM-P1", organization_id=org1.id, user_id=u1.id, role="ENGINEER")
    m2_eng = OrganizationMembership(id="MEM-P2", organization_id=org2.id, user_id=u2.id, role="ENGINEER")
    db.add_all([m1_eng, m2_eng])
    db.commit()

    # Org1 Engineer creates project
    p1 = create_project(
        payload=ProjectCreate(name="Core Infrastructure", description="Core routing and networking"),
        membership=m1_eng,
        db=db
    )
    assert p1.organization_id == org1.id
    assert p1.name == "Core Infrastructure"

    # Org1 lists projects: finds p1
    projects_org1 = list_projects(membership=m1_eng, db=db)
    assert len(projects_org1) == 1
    assert projects_org1[0].id == p1.id

    # Org2 lists projects: empty
    projects_org2 = list_projects(membership=m2_eng, db=db)
    assert len(projects_org2) == 0

    # Org2 requests Org1 project: 404 access denied
    with pytest.raises(HTTPException) as exc:
        get_project(project_id=p1.id, membership=m2_eng, db=db)
    assert exc.value.status_code == 404


def test_service_crud_and_tenant_isolation(db):
    org = Organization(id="ORG-SVC", name="Service Org", slug="svc-org")
    db.add(org)
    u_eng = User(id="USR-SVC-E", email="svce@test.com", hashed_password="h", full_name="Svc Eng")
    u_view = User(id="USR-SVC-V", email="svcv@test.com", hashed_password="h", full_name="Svc View")
    db.add_all([u_eng, u_view])
    db.commit()

    m_eng = OrganizationMembership(id="MEM-SVC-E", organization_id=org.id, user_id=u_eng.id, role="ENGINEER")
    m_view = OrganizationMembership(id="MEM-SVC-V", organization_id=org.id, user_id=u_view.id, role="VIEWER")
    db.add_all([m_eng, m_view])
    db.commit()

    # Engineer creates custom service
    svc = create_service(
        payload=ServiceCreate(name="billing-worker", tier="TIER_1", owner="Billing-Team"),
        membership=m_eng,
        db=db
    )
    assert svc.name == "billing-worker"
    assert svc.organization_id == org.id

    # Duplicate service name fails with 409
    with pytest.raises(HTTPException) as exc1:
        create_service(
            payload=ServiceCreate(name="billing-worker", tier="TIER_1"),
            membership=m_eng,
            db=db
        )
    assert exc1.value.status_code == 409

    # Viewer attempting to create service fails with 403
    with pytest.raises(HTTPException) as exc2:
        create_service(
            payload=ServiceCreate(name="viewer-svc"),
            membership=m_view,
            db=db
        )
    assert exc2.value.status_code == 403


# ============================================================================
# 6. Persistent Service Topology, Graph Rehydration & Blast Radius
# ============================================================================

def test_persistent_service_topology_across_service_recreation(db):
    org = Organization(id="ORG-TOPO-RESTART", name="Topo Restart Org", slug="topo-restart-org")
    db.add(org)
    u = User(id="USR-TOPO-1", email="topo1@test.com", hashed_password="h", full_name="Topo User")
    db.add(u)
    db.commit()

    m_eng = OrganizationMembership(id="MEM-TOPO-1", organization_id=org.id, user_id=u.id, role="ENGINEER")
    db.add(m_eng)
    db.commit()

    # Add custom microservices & dependencies
    dep1 = create_dependency(
        payload=DependencyCreate(source_service="edge-router", target_service="auth-service"),
        membership=m_eng,
        db=db
    )
    dep2 = create_dependency(
        payload=DependencyCreate(source_service="checkout-frontend", target_service="edge-router"),
        membership=m_eng,
        db=db
    )

    assert dep1.id is not None
    assert dep2.id is not None

    # Simulate Application Restart: instantiate a new TopologyService instance with zero RAM cache
    fresh_topo = TopologyService()
    # Rehydrate from the database
    rehydrated_graph = fresh_topo.rehydrate_from_db(db, organization_id=org.id)

    # Compute blast radius if auth-service fails:
    # Downstream dependents of auth-service: edge-router (depth 1) -> checkout-frontend (depth 2)
    blast = fresh_topo.get_blast_radius("auth-service", organization_id=org.id, db=db)
    impacted_names = [item["service"] for item in blast["impacted_services"]]

    assert blast["origin_service"] == "auth-service"
    assert "edge-router" in impacted_names
    assert "checkout-frontend" in impacted_names
    assert blast["total_impacted_services"] >= 2


def test_topology_dependency_deletion(db):
    org = Organization(id="ORG-TOPO-DEL", name="Topo Del Org", slug="topo-del-org")
    db.add(org)
    u = User(id="USR-TOPO-2", email="topo2@test.com", hashed_password="h", full_name="Topo Del User")
    db.add(u)
    db.commit()

    m_eng = OrganizationMembership(id="MEM-TOPO-2", organization_id=org.id, user_id=u.id, role="ENGINEER")
    db.add(m_eng)
    db.commit()

    # Create dependency
    dep = create_dependency(
        payload=DependencyCreate(source_service="gateway-a", target_service="backend-b"),
        membership=m_eng,
        db=db
    )
    dep_id = dep.id

    # Delete dependency
    del_res = delete_dependency(dependency_id=dep_id, membership=m_eng, db=db)
    assert del_res["status"] == "deleted"

    # Verify deleted from DB
    assert db.query(ServiceDependency).filter(ServiceDependency.id == dep_id).first() is None


def test_topology_cycle_detection(db):
    org = Organization(id="ORG-TOPO-CYCLE", name="Topo Cycle Org", slug="topo-cycle-org")
    db.add(org)
    u = User(id="USR-TOPO-3", email="topo3@test.com", hashed_password="h", full_name="Cycle User")
    db.add(u)
    db.commit()

    m_eng = OrganizationMembership(id="MEM-TOPO-3", organization_id=org.id, user_id=u.id, role="ENGINEER")
    db.add(m_eng)
    db.commit()

    # Create circular dependencies: NodeA -> NodeB -> NodeC -> NodeA
    create_dependency(payload=DependencyCreate(source_service="NodeA", target_service="NodeB"), membership=m_eng, db=db)
    create_dependency(payload=DependencyCreate(source_service="NodeB", target_service="NodeC"), membership=m_eng, db=db)
    create_dependency(payload=DependencyCreate(source_service="NodeC", target_service="NodeA"), membership=m_eng, db=db)

    cycle_info = detect_topology_cycles(membership=m_eng, db=db)
    assert cycle_info["has_cycles"] is True
    assert cycle_info["cycle_count"] >= 1


def test_multitenant_topology_isolation(db):
    orgA = Organization(id="ORG-A-TOPO", name="Org A", slug="org-a-topo")
    orgB = Organization(id="ORG-B-TOPO", name="Org B", slug="org-b-topo")
    db.add_all([orgA, orgB])

    uA = User(id="USR-A-T", email="ua@test.com", hashed_password="h", full_name="User A")
    uB = User(id="USR-B-T", email="ub@test.com", hashed_password="h", full_name="User B")
    db.add_all([uA, uB])
    db.commit()

    mA = OrganizationMembership(id="MEM-A-T", organization_id=orgA.id, user_id=uA.id, role="ENGINEER")
    mB = OrganizationMembership(id="MEM-B-T", organization_id=orgB.id, user_id=uB.id, role="ENGINEER")
    db.add_all([mA, mB])
    db.commit()

    # OrgA registers unique dependency
    create_dependency(
        payload=DependencyCreate(source_service="special-app", target_service="secret-db"),
        membership=mA,
        db=db
    )

    # OrgB queries dependencies: special-app -> secret-db must NOT be present
    deps_b = list_dependencies(membership=mB, db=db)
    dep_pairs_b = [(d.source_service, d.target_service) for d in deps_b]
    assert ("special-app", "secret-db") not in dep_pairs_b

    # OrgB blast radius for secret-db must be 0
    blast_b = get_topology_blast_radius(service="secret-db", membership=mB, db=db)
    assert blast_b.total_impacted_services == 0


# ============================================================================
# 7. Strict Multi-Tenant Isolation on Incidents & Investigations
# ============================================================================

def test_multitenant_incident_and_investigation_isolation(db):
    org1 = Organization(id="ORG-TENANT-1", name="Tenant 1", slug="tenant-1")
    org2 = Organization(id="ORG-TENANT-2", name="Tenant 2", slug="tenant-2")
    db.add_all([org1, org2])

    u1 = User(id="USR-T1", email="t1@company.com", hashed_password="h", full_name="Tenant 1 Eng")
    u2 = User(id="USR-T2", email="t2@company.com", hashed_password="h", full_name="Tenant 2 Eng")
    db.add_all([u1, u2])
    db.commit()

    m1 = OrganizationMembership(id="MEM-T1", organization_id=org1.id, user_id=u1.id, role="ENGINEER")
    m2 = OrganizationMembership(id="MEM-T2", organization_id=org2.id, user_id=u2.id, role="ENGINEER")
    db.add_all([m1, m2])
    db.commit()

    # 1. Org 1 creates an incident
    inc1 = create_incident(
        incident_in=IncidentCreate(
            title="Org 1 Private Incident",
            description="Tenant 1 confidential issue",
            service_name="auth-service",
            severity="CRITICAL",
            service_tier="TIER_1",
            impacted_users=500
        ),
        db=db,
        org_context=m1
    )
    assert inc1.organization_id == org1.id

    # 2. Org 2 lists incidents: must not include Org 1 incident
    inc_list_org2 = list_incidents(db=db, org_context=m2)
    assert not any(i.id == inc1.id for i in inc_list_org2)

    # 3. Org 2 attempts to fetch Org 1 incident directly: 404
    with pytest.raises(HTTPException) as exc1:
        get_incident(incident_id=inc1.id, db=db, org_context=m2)
    assert exc1.value.status_code == 404

    # 4. Org 2 attempts to diagnose Org 1 incident: 404
    with pytest.raises(HTTPException) as exc2:
        diagnose_incident(incident_id=inc1.id, db=db, org_context=m2)
    assert exc2.value.status_code == 404

    # 5. Org 2 attempts to resolve Org 1 incident: 404
    with pytest.raises(HTTPException) as exc3:
        resolve_incident(
            incident_id=inc1.id,
            resolution_in=ResolutionCreate(
                root_cause="Cross-tenant hack",
                action_taken="None",
                verified_by="Hacker"
            ),
            db=db,
            org_context=m2
        )
    assert exc3.value.status_code == 404

    # 6. Run AI investigation on Org 1 incident
    mock_provider = MockLLMProvider()
    provider_registry.register(mock_provider)

    inv_res = run_incident_investigation(
        incident_id=inc1.id,
        provider="mock",
        db=db,
        org_context=m1
    )
    assert inv_res.id is not None

    # 7. Org 2 attempts to view Org 1 investigation: 404
    with pytest.raises(HTTPException) as exc4:
        get_investigation_details(investigation_id=inv_res.id, db=db, org_context=m2)
    assert exc4.value.status_code == 404

    # 8. Org 2 attempts to submit feedback on Org 1 investigation: 404
    with pytest.raises(HTTPException) as exc5:
        submit_investigation_feedback(
            investigation_id=inv_res.id,
            feedback=InvestigationFeedbackCreate(approved=True, verified_by="Bad Actor"),
            db=db,
            org_context=m2
        )
    assert exc5.value.status_code == 404


def test_viewer_role_incident_actions_forbidden(db):
    org = Organization(id="ORG-VIEW-RESTRICT", name="Viewer Restrict Org", slug="viewer-restrict-org")
    db.add(org)
    u_view = User(id="USR-V-R", email="vr@test.com", hashed_password="h", full_name="Viewer Only")
    db.add(u_view)
    db.commit()

    m_view = OrganizationMembership(id="MEM-V-R", organization_id=org.id, user_id=u_view.id, role="VIEWER")
    db.add(m_view)
    db.commit()

    inc = create_incident(
        incident_in=IncidentCreate(
            title="Read Only Incident",
            description="Testing viewer limitations",
            service_name="payment-service",
            severity="MEDIUM"
        ),
        db=db,
        org_context=None
    )

    # Viewer attempting to resolve incident fails with 403
    with pytest.raises(HTTPException) as exc:
        resolve_incident(
            incident_id=inc.id,
            resolution_in=ResolutionCreate(
                root_cause="Viewer fix",
                action_taken="Viewer restart",
                verified_by="Viewer"
            ),
            db=db,
            org_context=m_view
        )
    assert exc.value.status_code == 403


# ============================================================================
# 8. Security Audit Logging & Secret Redaction
# ============================================================================

def test_audit_logging_and_credential_sanitization(db):
    org = Organization(id="ORG-AUDIT-TEST", name="Audit Org", slug="audit-org")
    db.add(org)
    u = User(id="USR-AUD-1", email="auditor@test.com", hashed_password="h", full_name="Auditor")
    db.add(u)
    db.commit()

    m = OrganizationMembership(id="MEM-AUD-1", organization_id=org.id, user_id=u.id, role="ADMIN")
    db.add(m)
    db.commit()

    # Log action with sensitive metadata
    audit_service.log(
        db=db,
        action="AUTH_LOGIN",
        resource_type="auth",
        actor_user_id=u.id,
        organization_id=org.id,
        metadata={
            "email": "auditor@test.com",
            "password": "SuperSecretPassword123!",
            "access_token": "eyJhbGciOi...",
            "safe_detail": "Login successful"
        }
    )

    logs = get_audit_logs(membership=m, db=db)
    assert len(logs) >= 1

    entry = logs[0]
    assert entry.action == "AUTH_LOGIN"
    assert entry.organization_id == org.id

    meta = json.loads(entry.metadata_json)
    assert meta["password"] == "[REDACTED]"
    assert meta["access_token"] == "[REDACTED]"
    assert meta["safe_detail"] == "Login successful"


# ============================================================================
# 9. Additional Security & Isolation Edge Cases
# ============================================================================

def test_unauthenticated_access_to_protected_dependencies(db):
    # Missing token -> 401
    with pytest.raises(HTTPException) as exc1:
        get_current_user(token=None, db=db)
    assert exc1.value.status_code == 401

    # Tampered token -> 401
    with pytest.raises(HTTPException) as exc2:
        get_current_user(token="tampered.jwt.payload", db=db)
    assert exc2.value.status_code == 401


def test_inactive_user_access_blocked(db):
    u = User(
        id="USR-INACTIVE",
        email="inactive@company.com",
        hashed_password="h",
        full_name="Inactive User",
        is_active=False
    )
    db.add(u)
    db.commit()

    token = create_access_token({"sub": u.id, "email": u.email})
    with pytest.raises(HTTPException) as exc:
        get_current_user(token=token, db=db)
    assert exc.value.status_code == 403
    assert "deactivated" in exc.value.detail.lower()


def test_cross_tenant_service_and_dependency_operations(db):
    orgA = Organization(id="ORG-ISO-A", name="Iso Org A", slug="iso-a")
    orgB = Organization(id="ORG-ISO-B", name="Iso Org B", slug="iso-b")
    db.add_all([orgA, orgB])

    uA = User(id="USR-ISO-A", email="isoa@test.com", hashed_password="h", full_name="User Iso A")
    uB = User(id="USR-ISO-B", email="isob@test.com", hashed_password="h", full_name="User Iso B")
    db.add_all([uA, uB])
    db.commit()

    mA = OrganizationMembership(id="MEM-ISO-A", organization_id=orgA.id, user_id=uA.id, role="ENGINEER")
    mB = OrganizationMembership(id="MEM-ISO-B", organization_id=orgB.id, user_id=uB.id, role="ENGINEER")
    db.add_all([mA, mB])
    db.commit()

    # Org A creates a service
    svcA = create_service(
        payload=ServiceCreate(name="vault-service", tier="TIER_0"),
        membership=mA,
        db=db
    )

    # Org B attempts to get Org A's service -> 404
    with pytest.raises(HTTPException) as exc1:
        get_service(service_id=svcA.id, membership=mB, db=db)
    assert exc1.value.status_code == 404

    # Org A creates a dependency
    depA = create_dependency(
        payload=DependencyCreate(source_service="vault-client", target_service="vault-service"),
        membership=mA,
        db=db
    )

    # Org B attempts to delete Org A's dependency -> 404
    with pytest.raises(HTTPException) as exc2:
        delete_dependency(dependency_id=depA.id, membership=mB, db=db)
    assert exc2.value.status_code == 404


def test_multiorg_switching_via_header(db):
    org1 = Organization(id="ORG-MULTI-1", name="Multi Org 1", slug="multi-1")
    org2 = Organization(id="ORG-MULTI-2", name="Multi Org 2", slug="multi-2")
    org3 = Organization(id="ORG-MULTI-3", name="Multi Org 3", slug="multi-3")
    db.add_all([org1, org2, org3])

    u = User(id="USR-MULTI", email="multi@company.com", hashed_password="h", full_name="Multi Org User")
    db.add(u)
    db.commit()

    # User is member of Org1 (Admin) and Org2 (Viewer), but NOT Org3
    m1 = OrganizationMembership(id="MEM-M1", organization_id=org1.id, user_id=u.id, role="ADMIN")
    m2 = OrganizationMembership(id="MEM-M2", organization_id=org2.id, user_id=u.id, role="VIEWER")
    db.add_all([m1, m2])
    db.commit()

    # Default without header -> Org 1
    ctx_default = get_current_org_context(user=u, x_organization_id=None, db=db)
    assert ctx_default.organization_id == org1.id
    assert ctx_default.role == "ADMIN"

    # Switching to Org 2 with header -> Org 2
    ctx_org2 = get_current_org_context(user=u, x_organization_id=org2.id, db=db)
    assert ctx_org2.organization_id == org2.id
    assert ctx_org2.role == "VIEWER"

    # Attempting to switch to Org 3 (not a member) -> 403 Forbidden
    with pytest.raises(HTTPException) as exc:
        get_current_org_context(user=u, x_organization_id=org3.id, db=db)
    assert exc.value.status_code == 403

