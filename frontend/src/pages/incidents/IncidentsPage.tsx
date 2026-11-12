import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  Plus,
  Search,
  Flame,
} from 'lucide-react';
import { incidentsApi, IncidentCreateParams } from '../../api/incidents';
import { useAuth } from '../../context/AuthContext';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { IncidentSeverity, ServiceTier } from '../../types';

export const IncidentsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { isEngineer } = useAuth();

  const [activeTab, setActiveTab] = useState<string>('ALL');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [viewTriageQueue, setViewTriageQueue] = useState<boolean>(false);

  // New Incident Form State
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newServiceName, setNewServiceName] = useState('');
  const [newSeverity, setNewSeverity] = useState<IncidentSeverity>(IncidentSeverity.HIGH);
  const [newServiceTier, setNewServiceTier] = useState<ServiceTier>(ServiceTier.TIER_1);
  const [newImpactedUsers, setNewImpactedUsers] = useState<number>(0);
  const [newRawLogs, setNewRawLogs] = useState('');

  // Fetch Incidents
  const { data: incidents = [], isLoading: incidentsLoading } = useQuery({
    queryKey: ['incidents', activeTab],
    queryFn: () => incidentsApi.list(activeTab === 'ALL' ? undefined : activeTab),
  });

  // Fetch Priority Triage Queue
  const { data: triageQueue = [], isLoading: triageLoading } = useQuery({
    queryKey: ['triageQueue'],
    queryFn: () => incidentsApi.getTriageQueue(),
    enabled: viewTriageQueue,
  });

  // Create Incident Mutation
  const createMutation = useMutation({
    mutationFn: (data: IncidentCreateParams) => incidentsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      queryClient.invalidateQueries({ queryKey: ['triageQueue'] });
      setShowCreateModal(false);
      resetForm();
    },
  });

  const resetForm = () => {
    setNewTitle('');
    setNewDescription('');
    setNewServiceName('');
    setNewSeverity(IncidentSeverity.HIGH);
    setNewServiceTier(ServiceTier.TIER_1);
    setNewImpactedUsers(0);
    setNewRawLogs('');
  };

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate({
      title: newTitle,
      description: newDescription,
      service_name: newServiceName,
      severity: newSeverity,
      service_tier: newServiceTier,
      impacted_users: Number(newImpactedUsers),
      raw_logs: newRawLogs || undefined,
      source: 'Manual SRE Console',
    });
  };

  // Filtered Incident List
  const filteredIncidents = incidents.filter((inc) => {
    if (severityFilter !== 'ALL' && inc.severity !== severityFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = inc.title.toLowerCase().includes(q);
      const matchService = inc.service_name.toLowerCase().includes(q);
      const matchId = inc.id.toLowerCase().includes(q);
      return matchTitle || matchService || matchId;
    }
    return true;
  });

  const statusTabs = [
    { id: 'ALL', label: 'All Incidents' },
    { id: 'OPEN', label: 'Open' },
    { id: 'INVESTIGATING', label: 'Investigating' },
    { id: 'MITIGATED', label: 'Mitigated' },
    { id: 'RESOLVED', label: 'Resolved' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            Incident Management & Triage
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Track active production outages, multivariate priority triage, and blast radius
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant={viewTriageQueue ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setViewTriageQueue(!viewTriageQueue)}
            leftIcon={<Flame className="w-3.5 h-3.5" />}
          >
            {viewTriageQueue ? 'Show Standard List' : 'Priority Queue (Heap)'}
          </Button>

          {isEngineer && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setShowCreateModal(true)}
              leftIcon={<Plus className="w-3.5 h-3.5" />}
            >
              Declare Incident
            </Button>
          )}
        </div>
      </div>

      {/* Triage Queue View */}
      {viewTriageQueue ? (
        <Card
          title="Active Max-Heap Priority Triage Queue"
          subtitle="Real-time multi-factor prioritization: Score = 0.40*Severity + 0.30*Tier + 0.20*Log(Impact+1)"
        >
          {triageLoading ? (
            <LoadingSpinner message="Calculating dynamic heap scores..." />
          ) : triageQueue.length === 0 ? (
            <EmptyState
              icon={Flame}
              title="Triage Queue Empty"
              description="No active unmitigated incidents currently require immediate priority sorting."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
                    <th className="py-3 px-3">Priority Score</th>
                    <th className="py-3 px-3">Incident ID</th>
                    <th className="py-3 px-3">Title</th>
                    <th className="py-3 px-3">Severity</th>
                    <th className="py-3 px-3">Tier</th>
                    <th className="py-3 px-3 text-right">Affected Users</th>
                    <th className="py-3 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {triageQueue.map((item, idx) => (
                    <tr key={item.incident_id} className="hover:bg-slate-800/40 transition">
                      <td className="py-3 px-3 font-mono font-bold text-rose-400 text-sm">
                        #{idx + 1} ({item.score})
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-300 font-medium">
                        {item.incident_id}
                      </td>
                      <td className="py-3 px-3 font-medium text-slate-100 max-w-xs truncate">
                        {item.title}
                      </td>
                      <td className="py-3 px-3">
                        <Badge variant="severity" value={item.severity} />
                      </td>
                      <td className="py-3 px-3">
                        <Badge variant="tier" value={item.service_tier} />
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-slate-300">
                        {item.impacted_users.toLocaleString()}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <Link
                          to={`/incidents/${item.incident_id}`}
                          className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                        >
                          Investigate →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : (
        /* Standard Incident List */
        <div className="space-y-4">
          {/* Filter Bar & Tabs */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-800 pb-3">
            {/* Status Tabs */}
            <div className="flex items-center gap-1 overflow-x-auto">
              {statusTabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition select-none ${
                    activeTab === tab.id
                      ? 'bg-indigo-600/15 text-indigo-300 border border-indigo-500/30'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Search and Severity Filter */}
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Filter by title, service..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1 text-xs bg-slate-900 border border-slate-800 rounded-md text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="px-2 py-1 text-xs bg-slate-900 border border-slate-800 rounded-md text-slate-300 focus:outline-none focus:border-indigo-500"
              >
                <option value="ALL">All Severities</option>
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
            </div>
          </div>

          {/* Incidents Table */}
          <Card>
            {incidentsLoading ? (
              <LoadingSpinner message="Fetching incidents..." />
            ) : filteredIncidents.length === 0 ? (
              <EmptyState
                icon={AlertTriangle}
                title="No Incidents Found"
                description={
                  searchQuery || severityFilter !== 'ALL'
                    ? 'No incidents matched your query filter.'
                    : 'Your organization currently has zero reported incidents.'
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
                      <th className="py-3 px-3">ID</th>
                      <th className="py-3 px-3">Title</th>
                      <th className="py-3 px-3">Service</th>
                      <th className="py-3 px-3">Severity</th>
                      <th className="py-3 px-3">Status</th>
                      <th className="py-3 px-3">Tier</th>
                      <th className="py-3 px-3 text-right">Users</th>
                      <th className="py-3 px-3 text-right">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {filteredIncidents.map((inc) => (
                      <tr
                        key={inc.id}
                        className="hover:bg-slate-800/40 transition group cursor-pointer"
                      >
                        <td className="py-3 px-3 font-mono font-medium text-slate-400 group-hover:text-indigo-400 transition">
                          <Link to={`/incidents/${inc.id}`} className="hover:underline">
                            {inc.id}
                          </Link>
                        </td>
                        <td className="py-3 px-3 font-medium text-slate-100 max-w-sm truncate">
                          <Link to={`/incidents/${inc.id}`} className="hover:underline">
                            {inc.title}
                          </Link>
                        </td>
                        <td className="py-3 px-3 font-mono text-slate-300">{inc.service_name}</td>
                        <td className="py-3 px-3">
                          <Badge variant="severity" value={inc.severity} />
                        </td>
                        <td className="py-3 px-3">
                          <Badge variant="status" value={inc.status} />
                        </td>
                        <td className="py-3 px-3">
                          <Badge variant="tier" value={inc.service_tier} />
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-slate-300">
                          {inc.impacted_users.toLocaleString()}
                        </td>
                        <td className="py-3 px-3 text-right text-slate-400">
                          {new Date(inc.created_at).toLocaleDateString([], {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Declare Incident Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Declare New Production Incident"
        description="Persists to database, triggers log tokenization & enqueues into priority triage."
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          <Input
            label="Incident Title"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="e.g. Connection pool exhaustion in auth-service"
            required
          />

          <Input
            label="Service Name"
            value={newServiceName}
            onChange={(e) => setNewServiceName(e.target.value)}
            placeholder="e.g. auth-service"
            required
          />

          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Severity"
              value={newSeverity}
              onChange={(e) => setNewSeverity(e.target.value as IncidentSeverity)}
              options={[
                { value: 'CRITICAL', label: 'CRITICAL (P0)' },
                { value: 'HIGH', label: 'HIGH (P1)' },
                { value: 'MEDIUM', label: 'MEDIUM (P2)' },
                { value: 'LOW', label: 'LOW (P3)' },
              ]}
            />

            <Select
              label="Service Tier"
              value={newServiceTier}
              onChange={(e) => setNewServiceTier(e.target.value as ServiceTier)}
              options={[
                { value: 'TIER_0', label: 'Tier 0 (Core Datastore / Infrastructure)' },
                { value: 'TIER_1', label: 'Tier 1 (Customer Facing / Revenue Path)' },
                { value: 'TIER_2', label: 'Tier 2 (Internal Platform / Async)' },
                { value: 'TIER_3', label: 'Tier 3 (Batch / BI Analytics)' },
              ]}
            />
          </div>

          <Input
            label="Estimated Impacted Users"
            type="number"
            min="0"
            value={newImpactedUsers}
            onChange={(e) => setNewImpactedUsers(Number(e.target.value))}
            placeholder="0"
          />

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Incident Description
            </label>
            <textarea
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 text-sm bg-slate-950/80 border border-slate-800 rounded-md text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              placeholder="Symptoms, alerts observed, caller error rates..."
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Raw Logs / Stack Trace
            </label>
            <textarea
              value={newRawLogs}
              onChange={(e) => setNewRawLogs(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 text-xs font-mono bg-slate-950/80 border border-slate-800 rounded-md text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              placeholder="Paste raw log lines or stack trace to tokenize through Prefix Trie..."
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setShowCreateModal(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={createMutation.isPending}
            >
              Declare Incident
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
