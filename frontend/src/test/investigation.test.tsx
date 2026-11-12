import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { InvestigationPage } from '../pages/investigations/InvestigationPage';
import { incidentsApi } from '../api/incidents';
import { investigationsApi } from '../api/investigations';
import { IncidentSeverity, IncidentStatus, ServiceTier } from '../types';

vi.mock('../api/incidents', () => ({
  incidentsApi: {
    list: vi.fn(),
    getById: vi.fn(),
    searchMemory: vi.fn(),
  },
}));

vi.mock('../api/investigations', () => ({
  investigationsApi: {
    run: vi.fn(),
    listByIncident: vi.fn(),
    getById: vi.fn(),
    submitFeedback: vi.fn(),
  },
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'usr-1', email: 'sre@recallops.io', full_name: 'Lead SRE' },
    activeOrg: { id: 'org-1', organization_name: 'Platform SRE' },
    role: 'ENGINEER',
    isAdmin: false,
    isEngineer: true,
    isViewer: false,
  }),
}));

const mockIncident = {
  id: 'inc-investigate-1',
  title: 'Database connection pool starvation',
  description: 'HikariCP exhausted max connections',
  service_name: 'order-service',
  severity: IncidentSeverity.CRITICAL,
  status: IncidentStatus.OPEN,
  service_tier: ServiceTier.TIER_1,
  impacted_users: 28000,
  raw_logs: 'Caused by: ConnectionTimeout: Connection is not available, request timed out after 30000ms',
  source: 'datadog',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const mockInvestigation = {
  id: 'inv-report-1',
  incident_id: 'inc-investigate-1',
  provider: 'openai',
  model_name: 'gpt-4o',
  status: 'COMPLETED',
  summary: 'Connection pool starvation caused by unindexed analytical queries blocking transaction slots.',
  report: {
    incident_id: 'inc-investigate-1',
    summary: 'Connection pool starvation caused by unindexed analytical queries blocking transaction slots.',
    probable_root_causes: [
      {
        hypothesis: 'Analytical long-running query saturated HikariCP pool',
        confidence_score: 0.94,
        supporting_evidence_ids: ['EVID-INC-1', 'EVID-LOG-1'],
        reasoning: 'Log timestamps correlate with 30,000ms HikariCP timeout and heavy SELECT * query execution.',
      },
    ],
    observed_facts: ['HikariCP timeout is 30000ms', 'Active database pool size is 20'],
    suggested_resolution: [
      'Terminate long-running query PID 4412 on PostgreSQL replica',
      'Increase pool maxLifetime from 30s to 60s',
    ],
  },
  created_at: new Date().toISOString(),
};

const mockMemoryMatches = [
  {
    incident_id: 'inc-past-99',
    similarity_score: 0.88,
    title: 'PostgreSQL thread exhaustion during Black Friday',
    root_cause: 'Unindexed customer search query hung 50 connections',
    verified_fix: 'Added composite B-Tree index on (org_id, created_at) and killed idle transactions.',
  },
];

describe('AI Investigation Engine & Human Oversight Loop', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <BrowserRouter>
        <InvestigationPage />
      </BrowserRouter>
    );
  };

  it('renders grounded investigation findings with confidence score, evidence tags, and runbook', async () => {
    (incidentsApi.list as any).mockResolvedValueOnce([mockIncident]);
    (incidentsApi.getById as any).mockResolvedValueOnce(mockIncident);
    (investigationsApi.listByIncident as any).mockResolvedValueOnce([mockInvestigation]);
    (incidentsApi.searchMemory as any).mockResolvedValueOnce(mockMemoryMatches);

    renderComponent();

    expect(await screen.findByText('AI Incident Investigation')).toBeInTheDocument();

    // Verify executive summary
    expect(
      await screen.findByText(/Connection pool starvation caused by unindexed analytical queries/)
    ).toBeInTheDocument();

    // Verify grounded root cause hypothesis and confidence
    expect(
      screen.getByText('Analytical long-running query saturated HikariCP pool')
    ).toBeInTheDocument();
    expect(screen.getByText('94%')).toBeInTheDocument();

    // Verify grounded evidence tags
    expect(screen.getByText('EVID-INC-1')).toBeInTheDocument();
    expect(screen.getByText('EVID-LOG-1')).toBeInTheDocument();

    // Verify recommended remediation steps
    expect(
      screen.getByText(/Terminate long-running query PID 4412 on PostgreSQL replica/)
    ).toBeInTheDocument();

    // Verify episodic memory recall match
    expect(
      screen.getByText('PostgreSQL thread exhaustion during Black Friday')
    ).toBeInTheDocument();
  });

  it('handles human approval modal and commits verified resolution to episodic memory', async () => {
    (incidentsApi.list as any).mockResolvedValueOnce([mockIncident]);
    (incidentsApi.getById as any).mockResolvedValue(mockIncident);
    (investigationsApi.listByIncident as any).mockResolvedValueOnce([mockInvestigation]);
    (incidentsApi.searchMemory as any).mockResolvedValueOnce(mockMemoryMatches);

    (investigationsApi.submitFeedback as any).mockResolvedValueOnce({
      investigation_id: 'inv-report-1',
      incident_id: 'inc-investigate-1',
      approved: true,
      verified_by: 'Alice SRE',
      memory_indexed: true,
      incident_status: 'RESOLVED',
      message: 'Resolution verified and committed to vector episodic memory.',
    });

    renderComponent();

    const approveBtn = await screen.findByRole('button', { name: /approve & commit to memory/i });
    fireEvent.click(approveBtn);

    expect(
      await screen.findByText('Approve AI Resolution & Index Memory')
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/verifying on-call engineer/i), {
      target: { value: 'Alice Chen (Senior SRE)' },
    });

    const confirmBtn = screen.getByRole('button', { name: /confirm & resolve/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(investigationsApi.submitFeedback).toHaveBeenCalledWith(
        'inv-report-1',
        expect.objectContaining({
          approved: true,
          verified_by: 'Alice Chen (Senior SRE)',
        })
      );
      expect(
        screen.getByText(/Verified & resolved! Episodic memory indexed: Yes/)
      ).toBeInTheDocument();
    });
  });
});
