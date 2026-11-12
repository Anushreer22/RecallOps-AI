import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { TopologyPage } from '../pages/topology/TopologyPage';
import { topologyApi } from '../api/topology';
import { servicesApi } from '../api/services';
import { ServiceTier } from '../types';

vi.mock('../api/topology', () => ({
  topologyApi: {
    listDependencies: vi.fn(),
    createDependency: vi.fn(),
    deleteDependency: vi.fn(),
    getBlastRadius: vi.fn(),
    getCycles: vi.fn(),
  },
}));

vi.mock('../api/services', () => ({
  servicesApi: {
    list: vi.fn(),
  },
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'usr-1', email: 'sre@recallops.io', full_name: 'Lead SRE' },
    activeOrg: { id: 'org-1', organization_name: 'Core Infra' },
    role: 'ADMIN',
    isAdmin: true,
    isEngineer: true,
    isViewer: false,
  }),
}));

const mockDependencies = [
  {
    id: 1,
    source_service: 'checkout-service',
    target_service: 'payment-service',
    dependency_type: 'DIRECT' as const,
    tier: 'TIER_1',
    owner: 'Payments Team',
    created_at: new Date().toISOString(),
  },
  {
    id: 2,
    source_service: 'payment-service',
    target_service: 'user-db',
    dependency_type: 'HARD' as const,
    tier: 'TIER_0',
    owner: 'Database SRE',
    created_at: new Date().toISOString(),
  },
];

const mockServices = [
  {
    id: 's-1',
    organization_id: 'org-1',
    name: 'checkout-service',
    tier: ServiceTier.TIER_2,
    owner: 'Frontend Team',
    created_at: new Date().toISOString(),
  },
  {
    id: 's-2',
    organization_id: 'org-1',
    name: 'payment-service',
    tier: ServiceTier.TIER_1,
    owner: 'Payments Team',
    created_at: new Date().toISOString(),
  },
];

const mockBlastRadius = {
  origin_service: 'user-db',
  total_impacted_services: 2,
  impacted_services: [
    {
      service: 'payment-service',
      hop_distance: 1,
      tier: ServiceTier.TIER_1,
      owner: 'Payments Team',
      impact_weight: 0.8,
    },
    {
      service: 'checkout-service',
      hop_distance: 2,
      tier: ServiceTier.TIER_2,
      owner: 'Frontend Team',
      impact_weight: 0.6,
    },
  ],
  max_depth: 2,
};

describe('Service Dependency Topology & Blast Radius Engine', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders declared dependency edges and architecture summary', async () => {
    (topologyApi.listDependencies as any).mockResolvedValueOnce(mockDependencies);
    (servicesApi.list as any).mockResolvedValueOnce(mockServices);
    (topologyApi.getCycles as any).mockResolvedValueOnce({
      organization_id: 'org-1',
      has_cycles: false,
      cycle_count: 0,
      cycles: [],
    });

    render(<TopologyPage />);

    expect(await screen.findByText('Service Dependency Topology')).toBeInTheDocument();
    expect(screen.getByText('checkout-service')).toBeInTheDocument();
    expect(screen.getAllByText('payment-service').length).toBeGreaterThan(0);
    expect(screen.getByText(/Total Edges: 2/)).toBeInTheDocument();
  });

  it('displays cycle warning banner when circular dependencies are detected by DFS', async () => {
    (topologyApi.listDependencies as any).mockResolvedValueOnce(mockDependencies);
    (servicesApi.list as any).mockResolvedValueOnce(mockServices);
    (topologyApi.getCycles as any).mockResolvedValueOnce({
      organization_id: 'org-1',
      has_cycles: true,
      cycle_count: 1,
      cycles: [['auth-service', 'token-service', 'auth-service']],
    });

    render(<TopologyPage />);

    expect(
      await screen.findByText(/Circular Dependency Detected \(1 cycle\)/)
    ).toBeInTheDocument();
    expect(screen.getByText('auth-service → token-service → auth-service')).toBeInTheDocument();
  });

  it('calculates BFS cascading blast radius for selected root service', async () => {
    (topologyApi.listDependencies as any).mockResolvedValue(mockDependencies);
    (servicesApi.list as any).mockResolvedValue(mockServices);
    (topologyApi.getCycles as any).mockResolvedValue({
      organization_id: 'org-1',
      has_cycles: false,
      cycle_count: 0,
      cycles: [],
    });
    (topologyApi.getBlastRadius as any).mockResolvedValueOnce(mockBlastRadius);

    render(<TopologyPage />);

    expect(await screen.findByText('Service Dependency Topology')).toBeInTheDocument();

    const option = await screen.findByRole('option', { name: 'user-db' });
    expect(option).toBeInTheDocument();

    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'user-db' } });

    await waitFor(() => {
      expect(topologyApi.getBlastRadius).toHaveBeenCalledWith('user-db');
      expect(
        screen.getByText(/Cascading Blast Radius for 'user-db'/)
      ).toBeInTheDocument();
      expect(screen.getByText(/Impact Score: 2/)).toBeInTheDocument();
    });
  });
});
