import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { IncidentsPage } from '../pages/incidents/IncidentsPage';
import { incidentsApi } from '../api/incidents';
import { IncidentSeverity, IncidentStatus, ServiceTier } from '../types';

vi.mock('../api/incidents', () => ({
  incidentsApi: {
    list: vi.fn(),
    getTriageQueue: vi.fn(),
    create: vi.fn(),
  },
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'usr-1', email: 'test@sre.io', full_name: 'Test SRE' },
    activeOrg: { id: 'org-1', organization_name: 'Test Org' },
    role: 'ADMIN',
    isAdmin: true,
    isEngineer: true,
    isViewer: false,
  }),
}));

const mockIncidents = [
  {
    id: 'inc-1',
    title: 'High latency on Payment Gateway',
    description: 'Postgres connection pool exhausted under load',
    service_name: 'payment-service',
    severity: IncidentSeverity.CRITICAL,
    status: IncidentStatus.OPEN,
    service_tier: ServiceTier.TIER_1,
    impacted_users: 15400,
    source: 'datadog',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 'inc-2',
    title: 'Notification dispatch backlog',
    description: 'Kafka partition lag exceeded 50,000 messages',
    service_name: 'notification-service',
    severity: IncidentSeverity.MEDIUM,
    status: IncidentStatus.INVESTIGATING,
    service_tier: ServiceTier.TIER_2,
    impacted_users: 1200,
    source: 'alertmanager',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

const mockTriageQueue = [
  {
    incident_id: 'inc-1',
    title: 'High latency on Payment Gateway',
    severity: IncidentSeverity.CRITICAL,
    service_tier: ServiceTier.TIER_1,
    impacted_users: 15400,
    score: 95.8,
    timestamp: Date.now(),
  },
];

describe('Incidents & Priority Triage Workspace', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <IncidentsPage />
        </BrowserRouter>
      </QueryClientProvider>
    );
  };

  it('renders incidents list with severity badges, services, and impacted users', async () => {
    (incidentsApi.list as any).mockResolvedValueOnce(mockIncidents);

    renderComponent();

    expect(await screen.findByText('High latency on Payment Gateway')).toBeInTheDocument();
    expect(screen.getByText('Notification dispatch backlog')).toBeInTheDocument();
    expect(screen.getByText('payment-service')).toBeInTheDocument();
    expect(screen.getByText('15,400')).toBeInTheDocument();
  });

  it('switches between standard table view and dynamic max-heap triage queue', async () => {
    (incidentsApi.list as any).mockResolvedValue(mockIncidents);
    (incidentsApi.getTriageQueue as any).mockResolvedValue(mockTriageQueue);

    renderComponent();

    await screen.findByText('High latency on Payment Gateway');

    const triageToggle = screen.getByRole('button', { name: /priority queue/i });
    fireEvent.click(triageToggle);

    await waitFor(() => {
      expect(incidentsApi.getTriageQueue).toHaveBeenCalled();
      expect(screen.getByText(/95.8/)).toBeInTheDocument();
    });
  });

  it('opens manual incident declaration modal and submits valid incident payload', async () => {
    (incidentsApi.list as any).mockResolvedValue([]);
    (incidentsApi.create as any).mockResolvedValueOnce(mockIncidents[0]);

    renderComponent();

    const declareBtn = await screen.findByRole('button', { name: /declare incident/i });
    fireEvent.click(declareBtn);

    expect(screen.getByText('Declare New Production Incident')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/incident title/i), {
      target: { value: 'Authentication DB Timeout' },
    });
    fireEvent.change(screen.getByLabelText(/service name/i), {
      target: { value: 'auth-service' },
    });

    const form = screen.getByRole('dialog').querySelector('form')!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(incidentsApi.create).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Authentication DB Timeout',
          service_name: 'auth-service',
        })
      );
    });
  });
});
