// Domain & Operational Types
export enum UserRole {
  ADMIN = 'ADMIN',
  ENGINEER = 'ENGINEER',
  VIEWER = 'VIEWER',
}

export enum IncidentSeverity {
  CRITICAL = 'CRITICAL',
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW',
}

export enum IncidentStatus {
  OPEN = 'OPEN',
  INVESTIGATING = 'INVESTIGATING',
  MITIGATED = 'MITIGATED',
  RESOLVED = 'RESOLVED',
}

export enum ServiceTier {
  TIER_0 = 'TIER_0',
  TIER_1 = 'TIER_1',
  TIER_2 = 'TIER_2',
  TIER_3 = 'TIER_3',
}

// Auth & Multi-Tenancy
export interface Membership {
  id: string;
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  role: UserRole;
  created_at: string;
  name?: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  memberships: Membership[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface MemberDetail {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  created_at: string;
}

export interface Project {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description?: string | null;
  created_at: string;
}

// Service Catalog & Dependency Topology
export interface ServiceItem {
  id: string;
  organization_id: string;
  project_id?: string | null;
  name: string;
  tier: ServiceTier;
  owner: string;
  description?: string | null;
  created_at: string;
}

export interface ServiceDependency {
  id: number;
  organization_id?: string | null;
  project_id?: string | null;
  source_service: string;
  target_service: string;
  dependency_type: 'DIRECT' | 'HARD' | 'SOFT' | 'ASYNC';
  tier?: string;
  owner?: string;
  created_at: string;
}

export interface ImpactedServiceNode {
  service: string;
  hop_distance?: number;
  tier?: ServiceTier | string;
  owner?: string;
  impact_weight?: number;
}

export interface BlastRadiusSummary {
  origin_service: string;
  total_impacted_services: number;
  impacted_services: ImpactedServiceNode[];
  max_depth: number;
  service?: string;
  blast_radius_score?: number;
}

export interface TopologyCyclesResponse {
  organization_id: string;
  has_cycles: boolean;
  cycle_count: number;
  cycles: string[][];
}

// Incidents & Triage
export interface Incident {
  id: string;
  title: string;
  description: string;
  service_name: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  service_tier: ServiceTier;
  impacted_users: number;
  raw_logs?: string | null;
  source: string;
  incident_key?: string | null;
  organization_id?: string | null;
  project_id?: string | null;
  created_at: string;
  updated_at: string;
  resolution?: IncidentResolution | null;
}

export interface IncidentResolution {
  id: string;
  incident_id: string;
  root_cause: string;
  action_taken: string;
  prevention_steps?: string | null;
  verified_by: string;
  resolved_at: string;
}

export interface TriageQueueItem {
  incident_id: string;
  title: string;
  severity: IncidentSeverity;
  service_tier: ServiceTier;
  impacted_users: number;
  score: number;
  timestamp: number;
}

export interface HistoricalRecallMatch {
  incident_id: string;
  similarity_score: number;
  title: string;
  root_cause?: string | null;
  verified_fix?: string | null;
  caution_notes?: string | null;
}

// AI Investigation Engine
export interface ProbableRootCause {
  hypothesis: string;
  confidence_score: number;
  supporting_evidence_ids?: string[];
  contradicting_evidence_ids?: string[];
  reasoning: string;
  // Optional convenience aliases
  title?: string;
  probability?: number;
}

export interface RecommendedRunbookStep {
  step_number: number;
  action: string;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  command_or_script?: string | null;
}

export interface StructuredInvestigationReport {
  incident_id: string;
  summary: string;
  probable_root_causes: ProbableRootCause[];
  observed_facts?: string[];
  evidence_gaps?: string[];
  suggested_investigation_steps?: string[];
  suggested_resolution?: string[];
  related_historical_incidents?: string[];
  requires_human_review?: boolean;
  hallucinated_evidence_ids?: string[];
  // Optional backward compat
  investigation_summary?: string;
  confidence_score?: number;
  recommended_runbook_steps?: RecommendedRunbookStep[];
  potentially_impacted_services?: string[];
}

export interface InvestigationResponse {
  id: string;
  incident_id: string;
  provider: string;
  model_name: string;
  status: 'PENDING' | 'COMPLETED' | 'FAILED' | string;
  summary?: string | null;
  report?: StructuredInvestigationReport | null;
  structured_result?: string | null;
  created_at: string;
  completed_at?: string | null;
  error_message?: string | null;
}

export interface InvestigationFeedbackCreate {
  approved: boolean;
  verified_by: string;
  root_cause?: string;
  action_taken?: string;
  prevention_steps?: string;
  notes?: string;
  feedback_notes?: string;
}

export interface InvestigationFeedbackResponse {
  investigation_id: string;
  incident_id: string;
  approved: boolean;
  verified_by: string;
  memory_indexed: boolean;
  resolution_id?: string | null;
  incident_status: string;
  message: string;
  status?: string;
  human_decision?: 'APPROVED' | 'REJECTED';
}

// Webhooks
export interface WebhookEventItem {
  id: number;
  provider: 'pagerduty' | 'datadog' | 'alertmanager' | string;
  provider_event_id: string;
  incident_key?: string | null;
  event_type: string;
  service_name?: string | null;
  alert_title?: string | null;
  status: 'PROCESSED' | 'DUPLICATE' | 'FAILED' | 'IGNORED';
  received_at: string;
  processed_at: string;
  internal_incident_id?: string | null;
  raw_payload_summary?: string | null;
  error_message?: string | null;
}

// Audit Logs
export interface AuditLogItem {
  id: string;
  organization_id?: string | null;
  actor_user_id?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  request_id?: string | null;
  metadata_json?: string | null;
  created_at: string;
}

// Health
export interface SystemHealth {
  status: string;
  project: string;
  version: string;
  indexed_memories: number;
  active_triage_count: number;
  services_in_graph: number;
}
