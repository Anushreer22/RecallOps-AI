import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Server,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  Layers,
} from 'lucide-react';
import { servicesApi, ServiceCreateParams } from '../../api/services';
import { projectsApi } from '../../api/projects';
import { ServiceItem, ServiceTier, Project, BlastRadiusSummary } from '../../types';
import { Card, CardBody } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { Input, Select, Textarea } from '../../components/ui/Input';
import { Badge, TierBadge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { useAuth } from '../../context/AuthContext';

export const ServicesPage: React.FC = () => {
  const { isViewer } = useAuth();
  const [services, setServices] = useState<ServiceItem[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedTier, setSelectedTier] = useState<string>('ALL');

  // Register Service Modal
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [tier, setTier] = useState<ServiceTier>(ServiceTier.TIER_2);
  const [owner, setOwner] = useState('');
  const [projectId, setProjectId] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Blast Radius Modal
  const [blastModalOpen, setBlastModalOpen] = useState(false);
  const [blastService, setBlastService] = useState<ServiceItem | null>(null);
  const [blastData, setBlastData] = useState<BlastRadiusSummary | null>(null);
  const [loadingBlast, setLoadingBlast] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [svcList, projList] = await Promise.all([
        servicesApi.list(),
        projectsApi.list().catch(() => []),
      ]);
      setServices(svcList);
      setProjects(projList);
      if (projList.length > 0 && !projectId) {
        setProjectId(projList[0].id);
      }
    } catch (err: any) {
      console.error('Failed to load services', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreate = async () => {
    if (!name.trim() || !owner.trim()) {
      alert('Service name and owner are required.');
      return;
    }
    setSubmitting(true);
    try {
      const payload: ServiceCreateParams = {
        name: name.trim().toLowerCase(),
        tier,
        owner: owner.trim(),
        project_id: projectId || undefined,
        description: description.trim() || undefined,
      };
      await servicesApi.create(payload);
      setModalOpen(false);
      setName('');
      setOwner('');
      setDescription('');
      await fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || err.message || 'Failed to create service');
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenBlastRadius = async (svc: ServiceItem) => {
    setBlastService(svc);
    setBlastModalOpen(true);
    setLoadingBlast(true);
    try {
      const res = await servicesApi.getBlastRadius(svc.id);
      setBlastData(res);
    } catch (err: any) {
      console.error('Failed to load blast radius', err);
    } finally {
      setLoadingBlast(false);
    }
  };

  const filteredServices = services.filter((svc) => {
    const matchesSearch =
      svc.name.toLowerCase().includes(search.toLowerCase()) ||
      svc.owner.toLowerCase().includes(search.toLowerCase());
    const matchesTier = selectedTier === 'ALL' || svc.tier === selectedTier;
    return matchesSearch && matchesTier;
  });

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-200 dark:border-surface-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-white">
              Service Catalog
            </h1>
            <Badge variant="blue" size="sm">
              <Server className="w-3 h-3 mr-1" />
              {services.length} Registered
            </Badge>
          </div>
          <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
            Authoritative inventory of operational services, tier classifications, ownership, and blast-radius metrics.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link to="/topology">
            <Button variant="outline" size="sm">
              <Layers className="w-4 h-4 mr-1.5" />
              View Topology Graph
            </Button>
          </Link>

          <Button
            variant="primary"
            size="sm"
            onClick={() => setModalOpen(true)}
            disabled={isViewer}
            title={isViewer ? 'Requires Engineer role or higher' : undefined}
          >
            <Plus className="w-4 h-4 mr-1.5" />
            Register Service
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-surface-400" />
          <input
            type="text"
            placeholder="Search by service name or owner..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-surface-50 dark:bg-surface-900 border border-surface-300 dark:border-surface-700 text-surface-900 dark:text-surface-100 text-xs rounded-lg pl-9 pr-3 py-2 focus:ring-1 focus:ring-brand-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs text-surface-500">Tier:</span>
          <select
            value={selectedTier}
            onChange={(e) => setSelectedTier(e.target.value)}
            className="bg-surface-50 dark:bg-surface-900 border border-surface-300 dark:border-surface-700 text-surface-900 dark:text-surface-100 text-xs rounded-lg px-3 py-2"
          >
            <option value="ALL">All Tiers</option>
            <option value="TIER_1">Tier 1 (Mission Critical)</option>
            <option value="TIER_2">Tier 2 (High Business Value)</option>
            <option value="TIER_3">Tier 3 (Supporting/Internal)</option>
          </select>

          <Button variant="ghost" size="sm" onClick={fetchData}>
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardBody className="p-0">
          {loading ? (
            <div className="py-16 flex justify-center">
              <LoadingSpinner size="lg" />
            </div>
          ) : filteredServices.length === 0 ? (
            <EmptyState
              title="No services found"
              message={search ? 'No services match your query.' : 'Register your first service to begin.'}
              action={
                !isViewer ? (
                  <Button variant="primary" size="sm" onClick={() => setModalOpen(true)}>
                    <Plus className="w-4 h-4 mr-1.5" /> Register Service
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-50 dark:bg-surface-800/50 text-surface-500 dark:text-surface-400 border-b border-surface-200 dark:border-surface-800 uppercase tracking-wider font-semibold">
                  <tr>
                    <th className="px-6 py-3.5">Service Name</th>
                    <th className="px-6 py-3.5">Tier</th>
                    <th className="px-6 py-3.5">Owner / Team</th>
                    <th className="px-6 py-3.5">Description</th>
                    <th className="px-6 py-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-200 dark:divide-surface-800">
                  {filteredServices.map((svc) => (
                    <tr
                      key={svc.id}
                      className="hover:bg-surface-50/50 dark:hover:bg-surface-800/30 transition-colors"
                    >
                      <td className="px-6 py-4 font-mono font-bold text-surface-900 dark:text-white">
                        {svc.name}
                      </td>
                      <td className="px-6 py-4">
                        <TierBadge tier={svc.tier} />
                      </td>
                      <td className="px-6 py-4 text-surface-600 dark:text-surface-300 font-medium">
                        {svc.owner}
                      </td>
                      <td className="px-6 py-4 text-surface-500 dark:text-surface-400 max-w-xs truncate">
                        {svc.description || '—'}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenBlastRadius(svc)}
                            title="Inspect Blast Radius"
                          >
                            <ShieldAlert className="w-3.5 h-3.5 mr-1 text-warning-500" />
                            Blast Radius
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Register Service Modal */}
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Register Service in Catalog">
        <div className="space-y-4 text-sm">
          <Input
            label="Service Identifier *"
            placeholder="e.g. auth-service"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />

          <Select
            label="Service Tier *"
            value={tier}
            onChange={(e) => setTier(e.target.value as ServiceTier)}
            options={[
              { value: ServiceTier.TIER_1, label: 'Tier 1 (Mission Critical - Direct Revenue/User Impact)' },
              { value: ServiceTier.TIER_2, label: 'Tier 2 (High Business Value - Asynchronous/Backend)' },
              { value: ServiceTier.TIER_3, label: 'Tier 3 (Supporting - Analytics/Internal Tools)' },
            ]}
          />

          <Input
            label="Owner / On-Call Team *"
            placeholder="e.g. Core Platform SRE"
            value={owner}
            onChange={(e) => setOwner(e.target.value)}
          />

          {projects.length > 0 && (
            <Select
              label="Assigned Project"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              options={projects.map((p) => ({ value: p.id, label: p.name }))}
            />
          )}

          <Textarea
            label="Description (Optional)"
            rows={2}
            placeholder="Key responsibilities and SLAs of this service..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />

          <div className="flex justify-end gap-3 pt-3 border-t border-surface-200 dark:border-surface-800">
            <Button variant="ghost" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCreate} loading={submitting}>
              Register Service
            </Button>
          </div>
        </div>
      </Modal>

      {/* Blast Radius Modal */}
      <Modal
        isOpen={blastModalOpen}
        onClose={() => setBlastModalOpen(false)}
        title={`Cascading Blast Radius: ${blastService?.name || ''}`}
        size="md"
      >
        <div className="space-y-4 text-sm">
          {loadingBlast ? (
            <div className="py-8 flex justify-center">
              <LoadingSpinner size="md" />
            </div>
          ) : blastData ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded-lg bg-surface-100 dark:bg-surface-800">
                <span className="text-xs font-semibold text-surface-500 uppercase">Impact Score</span>
                <span className="font-mono font-bold text-sm text-warning-500">
                  {blastData.total_impacted_services ?? blastData.blast_radius_score ?? 0}
                </span>
              </div>

              <div>
                <span className="text-xs font-semibold text-surface-500 uppercase block mb-1.5">
                  Downstream Impacted Services ({blastData.impacted_services.length})
                </span>
                {blastData.impacted_services.length === 0 ? (
                  <p className="text-xs text-surface-500 italic">
                    No downstream dependencies detected. Service failure remains isolated.
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {blastData.impacted_services.map((item, idx) => {
                      const name = typeof item === 'string' ? item : item.service;
                      return (
                        <span
                          key={`${name}-${idx}`}
                          className="px-2 py-1 rounded font-mono text-xs font-medium bg-warning-500/10 text-warning-500 border border-warning-500/20"
                        >
                          {name}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="pt-3 border-t border-surface-200 dark:border-surface-800 flex justify-end">
                <Button variant="primary" size="sm" onClick={() => setBlastModalOpen(false)}>
                  Close
                </Button>
              </div>
            </div>
          ) : (
            <p className="text-xs text-surface-500">No blast radius telemetry available.</p>
          )}
        </div>
      </Modal>
    </div>
  );
};
