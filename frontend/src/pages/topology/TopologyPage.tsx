import React, { useState, useEffect, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Node,
  Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Layers,
  AlertTriangle,
  Plus,
  Trash2,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';
import { topologyApi, DependencyCreateParams } from '../../api/topology';
import { servicesApi } from '../../api/services';
import { ServiceDependency, BlastRadiusSummary, ServiceItem } from '../../types';
import { ServiceNode } from './ServiceNode';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { Input, Select } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { useAuth } from '../../context/AuthContext';

const nodeTypes = {
  serviceNode: ServiceNode,
};

export const TopologyPage: React.FC = () => {
  const { isViewer } = useAuth();
  const [dependencies, setDependencies] = useState<ServiceDependency[]>([]);
  const [services, setServices] = useState<ServiceItem[]>([]);
  const [cycles, setCycles] = useState<string[][]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Blast radius calculation state
  const [selectedService, setSelectedService] = useState<string>('');
  const [blastRadius, setBlastRadius] = useState<BlastRadiusSummary | null>(null);
  const [calculatingBlast, setCalculatingBlast] = useState(false);

  // Add edge modal state
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [sourceService, setSourceService] = useState('');
  const [targetService, setTargetService] = useState('');
  const [depType, setDepType] = useState<'DIRECT' | 'HARD' | 'SOFT' | 'ASYNC'>('DIRECT');
  const [depTier, setDepTier] = useState('TIER_2');
  const [depOwner, setDepOwner] = useState('');
  const [submittingEdge, setSubmittingEdge] = useState(false);

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Load topology data
  const fetchData = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [deps, svcList, cyclesRes] = await Promise.all([
        topologyApi.listDependencies(),
        servicesApi.list().catch(() => []),
        topologyApi.getCycles().catch(() => ({ has_cycles: false, cycles: [] })),
      ]);
      setDependencies(deps);
      setServices(svcList);
      setCycles(cyclesRes.cycles || []);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to load topology');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Compute graph nodes and edges layout
  useEffect(() => {
    // Unique services from both dependencies and services list
    const serviceMap = new Map<string, { tier?: string; owner?: string }>();

    services.forEach((s) => {
      serviceMap.set(s.name, { tier: s.tier, owner: s.owner });
    });

    dependencies.forEach((d) => {
      if (!serviceMap.has(d.source_service)) {
        serviceMap.set(d.source_service, { tier: d.tier, owner: d.owner });
      }
      if (!serviceMap.has(d.target_service)) {
        serviceMap.set(d.target_service, {});
      }
    });

    const serviceNames = Array.from(serviceMap.keys());
    if (serviceNames.length === 0) {
      setNodes([]);
      setEdges([]);
      return;
    }

    // Grid layout for nodes
    const cols = Math.max(3, Math.ceil(Math.sqrt(serviceNames.length * 1.5)));
    const nodeWidth = 240;
    const nodeHeight = 140;

    const impactedNames = (blastRadius?.impacted_services || []).map((item) =>
      typeof item === 'string' ? item : item.service
    );
    const impactedSet = new Set(impactedNames);

    const newNodes: Node[] = serviceNames.map((name, index) => {
      const row = Math.floor(index / cols);
      const col = index % cols;
      const meta = serviceMap.get(name);
      const isOrigin = selectedService === name;
      const isImpacted = impactedSet.has(name);

      return {
        id: name,
        type: 'serviceNode',
        position: { x: col * nodeWidth + 50, y: row * nodeHeight + 50 },
        data: {
          label: name,
          tier: meta?.tier,
          owner: meta?.owner,
          isOrigin,
          isImpacted,
        },
      };
    });

    const newEdges: Edge[] = dependencies.map((dep) => {
      const isOriginSource = dep.source_service === selectedService;
      const isImpactedEdge =
        isOriginSource ||
        (impactedSet.has(dep.source_service) && impactedSet.has(dep.target_service));

      return {
        id: `e-${dep.id}-${dep.source_service}-${dep.target_service}`,
        source: dep.source_service,
        target: dep.target_service,
        animated: isImpactedEdge,
        style: {
          stroke: isImpactedEdge ? '#f59e0b' : '#64748b',
          strokeWidth: isImpactedEdge ? 2.5 : 1.5,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isImpactedEdge ? '#f59e0b' : '#64748b',
        },
      };
    });

    setNodes(newNodes);
    setEdges(newEdges);
  }, [dependencies, services, blastRadius, selectedService, setNodes, setEdges]);

  // Handle Blast Radius Calculation
  const handleCalculateBlastRadius = async (svc: string) => {
    if (!svc) {
      setSelectedService('');
      setBlastRadius(null);
      return;
    }
    setSelectedService(svc);
    setCalculatingBlast(true);
    try {
      const res = await topologyApi.getBlastRadius(svc);
      setBlastRadius(res);
    } catch (err: any) {
      console.error('Blast radius calculation failed', err);
    } finally {
      setCalculatingBlast(false);
    }
  };

  const handleClearSimulation = () => {
    setSelectedService('');
    setBlastRadius(null);
  };

  const handleCreateDependency = async () => {
    if (!sourceService.trim() || !targetService.trim()) {
      alert('Source and Target services are required.');
      return;
    }
    if (sourceService.trim() === targetService.trim()) {
      alert('A service cannot depend on itself.');
      return;
    }

    setSubmittingEdge(true);
    try {
      const payload: DependencyCreateParams = {
        source_service: sourceService.trim(),
        target_service: targetService.trim(),
        dependency_type: depType,
        tier: depTier,
        owner: depOwner.trim() || undefined,
      };
      await topologyApi.createDependency(payload);
      setAddModalOpen(false);
      setSourceService('');
      setTargetService('');
      setDepOwner('');
      await fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || err.message || 'Failed to create dependency');
    } finally {
      setSubmittingEdge(false);
    }
  };

  const handleDeleteDependency = async (id: number) => {
    if (!confirm('Are you sure you want to delete this dependency edge?')) return;
    try {
      await topologyApi.deleteDependency(id);
      await fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || err.message || 'Failed to delete dependency');
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-200 dark:border-surface-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-white">
              Service Dependency Topology
            </h1>
            <Badge variant="blue" size="sm">
              <Layers className="w-3 h-3 mr-1" />
              Graph Engine
            </Badge>
          </div>
          <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
            Live directed acyclic service graph with automated DFS cycle detection and BFS blast-radius modeling.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={fetchData} loading={loading}>
            <RefreshCw className="w-4 h-4 mr-1.5" />
            Refresh
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => setAddModalOpen(true)}
            disabled={isViewer}
            title={isViewer ? 'Requires Engineer role or higher' : undefined}
          >
            <Plus className="w-4 h-4 mr-1.5" />
            Add Dependency
          </Button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-lg bg-danger-500/10 border border-danger-500/20 text-danger-500 text-sm">
          {errorMsg}
        </div>
      )}

      {/* Cycle Detection Warning Banner */}
      {cycles.length > 0 && (
        <div className="p-4 rounded-xl bg-danger-500/10 border border-danger-500/30 text-danger-500 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <div className="font-bold text-sm">
              Circular Dependency Detected ({cycles.length} cycle{cycles.length > 1 ? 's' : ''})
            </div>
            <p className="text-danger-400">
              Circular dependencies can cause cascading deadlock during failure storms. Review and decouple:
            </p>
            <ul className="list-disc pl-5 space-y-0.5 font-mono">
              {cycles.map((cycle, idx) => (
                <li key={idx}>{cycle.join(' → ')}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Blast Radius Simulation Control Bar */}
      <div className="p-4 rounded-xl bg-surface-50 dark:bg-surface-800/60 border border-surface-200 dark:border-surface-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-warning-500/10 text-warning-500 flex items-center justify-center">
            <ShieldAlert className="w-4 h-4" />
          </div>
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 block">
              Blast Radius Simulator
            </span>
            <span className="text-xs text-surface-700 dark:text-surface-300">
              Select any root service to trace downstream cascading blast radius via breadth-first search.
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={selectedService}
            onChange={(e) => handleCalculateBlastRadius(e.target.value)}
            disabled={calculatingBlast}
            className="bg-white dark:bg-surface-900 border border-surface-300 dark:border-surface-700 text-surface-900 dark:text-surface-100 text-xs rounded-lg px-3 py-2 focus:ring-1 focus:ring-brand-500"
          >
            <option value="">-- Choose Root Service --</option>
            {Array.from(new Set(nodes.map((n) => n.id))).map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>

          {selectedService && (
            <Button variant="ghost" size="sm" onClick={handleClearSimulation}>
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* Blast Radius Summary Card if active */}
      {blastRadius && (
        <div className="p-4 rounded-xl bg-warning-500/10 border border-warning-500/30 text-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-bold text-sm text-warning-500 flex items-center gap-1.5">
              <ShieldAlert className="w-4 h-4" />
              Cascading Blast Radius for '{blastRadius.origin_service || blastRadius.service}'
            </span>
            <span className="font-mono text-warning-600 dark:text-warning-400 font-bold">
              Impact Score: {blastRadius.total_impacted_services ?? blastRadius.blast_radius_score ?? 0}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-surface-700 dark:text-surface-300">
              Downstream Impacted ({blastRadius.impacted_services.length}):
            </span>
            {blastRadius.impacted_services.length === 0 ? (
              <span className="text-surface-500 italic">None (Isolated root)</span>
            ) : (
              blastRadius.impacted_services.map((item, idx) => {
                const name = typeof item === 'string' ? item : item.service;
                return (
                  <span
                    key={`${name}-${idx}`}
                    className="px-2 py-0.5 rounded font-mono font-bold bg-warning-500/20 text-warning-600 dark:text-warning-400 border border-warning-500/30"
                  >
                    {name}
                  </span>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Main Canvas */}
      <div className="h-[600px] w-full rounded-2xl border border-surface-200 dark:border-surface-800 bg-surface-50 dark:bg-surface-950 overflow-hidden relative shadow-inner">
        {loading ? (
          <div className="h-full flex items-center justify-center">
            <LoadingSpinner size="lg" />
          </div>
        ) : nodes.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center p-6 text-center">
            <Layers className="w-12 h-12 text-surface-400 mb-3" />
            <h3 className="text-base font-semibold text-surface-900 dark:text-white">
              No Services in Topology
            </h3>
            <p className="text-xs text-surface-500 max-w-sm mt-1 mb-4">
              Declare service dependencies or register services to construct the architecture graph.
            </p>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setAddModalOpen(true)}
              disabled={isViewer}
            >
              <Plus className="w-4 h-4 mr-1.5" />
              Add First Dependency
            </Button>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            minZoom={0.2}
            maxZoom={1.8}
          >
            <Background color="#64748b" gap={20} size={1} />
            <Controls className="!bg-white dark:!bg-surface-800 !border-surface-300 dark:!border-surface-700 !shadow-lg" />
            <MiniMap
              className="!bg-white/80 dark:!bg-surface-900/80 !border-surface-300 dark:!border-surface-700 !rounded-xl"
              nodeColor={() => '#6366f1'}
            />
          </ReactFlow>
        )}
      </div>

      {/* Dependency Table & Management */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold text-surface-900 dark:text-white">
                Declared Dependency Edges
              </h3>
              <p className="text-xs text-surface-500 dark:text-surface-400">
                Directional relationships: Source service depends on Target service
              </p>
            </div>
            <span className="text-xs font-mono text-surface-500 dark:text-surface-400">
              Total Edges: {dependencies.length}
            </span>
          </div>
        </CardHeader>
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-50 dark:bg-surface-800/50 text-surface-500 dark:text-surface-400 border-b border-surface-200 dark:border-surface-800 uppercase tracking-wider font-semibold">
                <tr>
                  <th className="px-6 py-3">Source Service</th>
                  <th className="px-6 py-3">Relationship</th>
                  <th className="px-6 py-3">Target Service</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3">Owner / Tier</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-200 dark:divide-surface-800">
                {dependencies.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-8 text-center text-surface-500">
                      No dependency edges declared.
                    </td>
                  </tr>
                ) : (
                  dependencies.map((dep) => (
                    <tr key={dep.id} className="hover:bg-surface-50/50 dark:hover:bg-surface-800/30">
                      <td className="px-6 py-3 font-mono font-semibold text-surface-900 dark:text-white">
                        {dep.source_service}
                      </td>
                      <td className="px-6 py-3 text-surface-400 font-mono">
                        ── depends on ──▶
                      </td>
                      <td className="px-6 py-3 font-mono font-semibold text-brand-500">
                        {dep.target_service}
                      </td>
                      <td className="px-6 py-3">
                        <Badge variant="blue" size="sm">
                          {dep.dependency_type || 'DIRECT'}
                        </Badge>
                      </td>
                      <td className="px-6 py-3 text-surface-600 dark:text-surface-300">
                        {dep.owner || '—'} {dep.tier ? `(${dep.tier})` : ''}
                      </td>
                      <td className="px-6 py-3 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteDependency(dep.id)}
                          disabled={isViewer}
                          className="text-danger-500 hover:text-danger-600"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      {/* Add Dependency Modal */}
      <Modal
        isOpen={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        title="Declare New Service Dependency"
        size="md"
      >
        <div className="space-y-4 text-sm">
          <Input
            label="Source Service *"
            placeholder="e.g. checkout-service"
            value={sourceService}
            onChange={(e) => setSourceService(e.target.value)}
          />

          <Input
            label="Target Service (Dependency) *"
            placeholder="e.g. payment-gateway"
            value={targetService}
            onChange={(e) => setTargetService(e.target.value)}
          />

          <div className="grid grid-cols-2 gap-3">
            <Select
              label="Dependency Type"
              value={depType}
              onChange={(e) => setDepType(e.target.value as any)}
              options={[
                { value: 'DIRECT', label: 'DIRECT (Synchronous RPC)' },
                { value: 'HARD', label: 'HARD (Critical Path)' },
                { value: 'SOFT', label: 'SOFT (Degrades Gracefully)' },
                { value: 'ASYNC', label: 'ASYNC (Message Queue)' },
              ]}
            />

            <Select
              label="Target Service Tier"
              value={depTier}
              onChange={(e) => setDepTier(e.target.value)}
              options={[
                { value: 'TIER_1', label: 'Tier 1 (Mission Critical)' },
                { value: 'TIER_2', label: 'Tier 2 (High Business Value)' },
                { value: 'TIER_3', label: 'Tier 3 (Supporting/Internal)' },
              ]}
            />
          </div>

          <Input
            label="Service Owner (Optional)"
            placeholder="e.g. Payments Engineering"
            value={depOwner}
            onChange={(e) => setDepOwner(e.target.value)}
          />

          <div className="flex justify-end gap-3 pt-3 border-t border-surface-200 dark:border-surface-800">
            <Button variant="ghost" onClick={() => setAddModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCreateDependency} loading={submittingEdge}>
              Add Dependency
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
