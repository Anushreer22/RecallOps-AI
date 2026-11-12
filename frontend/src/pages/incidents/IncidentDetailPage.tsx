import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2,
  BrainCircuit,
  ArrowLeft,
} from 'lucide-react';
import { incidentsApi, IncidentResolveParams } from '../../api/incidents';
import { investigationsApi } from '../../api/investigations';
import { useAuth } from '../../context/AuthContext';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { Input } from '../../components/ui/Input';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';

export const IncidentDetailPage: React.FC = () => {
  const { incidentId } = useParams<{ incidentId: string }>();
  const queryClient = useQueryClient();
  const { isEngineer, user } = useAuth();

  const [showResolveModal, setShowResolveModal] = useState(false);
  const [rootCause, setRootCause] = useState('');
  const [actionTaken, setActionTaken] = useState('');
  const [preventionSteps, setPreventionSteps] = useState('');
  const [verifiedBy, setVerifiedBy] = useState(user?.full_name || 'OnCall-SRE');

  // Fetch Incident Details
  const { data: incident, isLoading: incidentLoading } = useQuery({
    queryKey: ['incident', incidentId],
    queryFn: () => incidentsApi.getById(incidentId!),
    enabled: Boolean(incidentId),
  });

  // Fetch Blast Radius
  const { data: blastRadius, isLoading: blastLoading } = useQuery({
    queryKey: ['blastRadius', incident?.service_name],
    queryFn: () => incidentsApi.getBlastRadius(incident!.service_name),
    enabled: Boolean(incident?.service_name),
  });

  // Fetch Associated Investigations
  const { data: investigations = [], isLoading: invLoading } = useQuery({
    queryKey: ['incidentInvestigations', incidentId],
    queryFn: () => investigationsApi.listByIncident(incidentId!),
    enabled: Boolean(incidentId),
  });

  // Resolve Mutation
  const resolveMutation = useMutation({
    mutationFn: (params: IncidentResolveParams) =>
      incidentsApi.resolve(incidentId!, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incident', incidentId] });
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      setShowResolveModal(false);
    },
  });

  const handleResolveSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    resolveMutation.mutate({
      root_cause: rootCause,
      action_taken: actionTaken,
      prevention_steps: preventionSteps || undefined,
      verified_by: verifiedBy,
    });
  };

  if (incidentLoading || !incident) {
    return <LoadingSpinner message="Loading incident telemetry..." />;
  }

  const isResolved = incident.status === 'RESOLVED';

  return (
    <div className="space-y-6">
      {/* Back Link */}
      <div>
        <Link
          to="/incidents"
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Incidents
        </Link>
      </div>

      {/* Header Banner */}
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="font-mono text-sm font-bold text-indigo-400">{incident.id}</span>
              <Badge variant="severity" value={incident.severity} />
              <Badge variant="status" value={incident.status} />
              <Badge variant="tier" value={incident.service_tier} />
            </div>
            <h1 className="text-xl font-bold tracking-tight text-slate-100">{incident.title}</h1>
            <p className="text-xs text-slate-400 max-w-3xl">{incident.description}</p>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 shrink-0">
            <Link to={`/investigations?incidentId=${incident.id}`}>
              <Button
                variant="secondary"
                size="sm"
                leftIcon={<BrainCircuit className="w-3.5 h-3.5 text-purple-400" />}
              >
                Run AI Investigation
              </Button>
            </Link>

            {isEngineer && !isResolved && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => setShowResolveModal(true)}
                leftIcon={<CheckCircle2 className="w-3.5 h-3.5 text-emerald-300" />}
              >
                Resolve Incident
              </Button>
            )}
          </div>
        </div>

        {/* Telemetry Meta Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 border-t border-slate-800 text-xs">
          <div>
            <span className="text-slate-500 block">Service</span>
            <span className="font-mono font-medium text-slate-200">{incident.service_name}</span>
          </div>
          <div>
            <span className="text-slate-500 block">Impacted Users</span>
            <span className="font-mono font-medium text-slate-200">
              {incident.impacted_users.toLocaleString()}
            </span>
          </div>
          <div>
            <span className="text-slate-500 block">Ingestion Source</span>
            <span className="font-medium text-slate-200">{incident.source}</span>
          </div>
          <div>
            <span className="text-slate-500 block">Reported At</span>
            <span className="text-slate-300">
              {new Date(incident.created_at).toLocaleString()}
            </span>
          </div>
        </div>
      </div>

      {/* Verified Resolution (If Resolved) */}
      {incident.resolution && (
        <Card
          title="Verified Root Cause & Operational Fix"
          subtitle="Indexed into persistent episodic memory to train future incident recall"
          className="border-emerald-500/30 bg-emerald-950/10"
        >
          <div className="space-y-3 text-xs">
            <div>
              <span className="font-semibold text-emerald-400 block mb-1">Identified Root Cause:</span>
              <p className="text-slate-200 bg-slate-900/60 p-3 rounded border border-slate-800 font-mono">
                {incident.resolution.root_cause}
              </p>
            </div>
            <div>
              <span className="font-semibold text-emerald-400 block mb-1">Remediation Action Taken:</span>
              <p className="text-slate-200 bg-slate-900/60 p-3 rounded border border-slate-800">
                {incident.resolution.action_taken}
              </p>
            </div>
            {incident.resolution.prevention_steps && (
              <div>
                <span className="font-semibold text-emerald-400 block mb-1">Prevention Runbook:</span>
                <p className="text-slate-300 bg-slate-900/60 p-3 rounded border border-slate-800">
                  {incident.resolution.prevention_steps}
                </p>
              </div>
            )}
            <div className="flex items-center gap-4 text-[11px] text-slate-400 pt-2 border-t border-slate-800">
              <span>
                Verified By: <strong className="text-slate-200">{incident.resolution.verified_by}</strong>
              </span>
              <span>•</span>
              <span>
                Resolved At: {new Date(incident.resolution.resolved_at).toLocaleString()}
              </span>
            </div>
          </div>
        </Card>
      )}

      {/* Blast Radius & Graph Downstream Propagation */}
      <Card
        title="Downstream Blast Radius (Graph BFS)"
        subtitle={`Computed downstream impact if '${incident.service_name}' experiences failure`}
      >
        {blastLoading ? (
          <LoadingSpinner message="Calculating blast radius on dependency graph..." />
        ) : !blastRadius || blastRadius.total_impacted_services === 0 ? (
          <p className="text-xs text-slate-500 py-3">
            No downstream dependents found for '{incident.service_name}'. Service is an edge node or has no direct consumers.
          </p>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-4 text-xs">
              <span className="text-slate-400">
                Total Impacted Services:{' '}
                <strong className="text-rose-400 font-mono text-sm">
                  {blastRadius.total_impacted_services}
                </strong>
              </span>
              <span>•</span>
              <span className="text-slate-400">
                Max Downstream Depth:{' '}
                <strong className="text-slate-200 font-mono">{blastRadius.max_depth} hops</strong>
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {blastRadius.impacted_services.map((svc) => (
                <div
                  key={svc.service}
                  className="p-3 bg-slate-900/80 border border-slate-800 rounded-lg space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-medium text-slate-200 text-xs">
                      {svc.service}
                    </span>
                    <Badge variant="tier" value={svc.tier} />
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-500">
                    <span>Hop distance: {svc.hop_distance}</span>
                    <span className="text-indigo-400 font-mono">Weight: {svc.impact_weight}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Raw Logs & Stack Trace */}
      {incident.raw_logs && (
        <Card
          title="Raw Logs & Stack Trace"
          subtitle="Unstructured log stream parsed through Prefix Trie for error signatures"
        >
          <pre className="p-4 bg-slate-950 rounded-lg text-xs font-mono text-slate-300 overflow-x-auto border border-slate-800 whitespace-pre-wrap">
            {incident.raw_logs}
          </pre>
        </Card>
      )}

      {/* Investigation Reports History */}
      <Card
        title="AI Investigation Reports"
        subtitle="Automated root cause diagnoses and runbook suggestions for this incident"
      >
        {invLoading ? (
          <LoadingSpinner message="Loading historical AI investigations..." />
        ) : investigations.length === 0 ? (
          <div className="text-center py-6 space-y-2">
            <p className="text-xs text-slate-400">No AI investigations have been executed yet.</p>
            <Link to={`/investigations?incidentId=${incident.id}`}>
              <Button size="sm" variant="secondary">
                Trigger Investigation
              </Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {investigations.map((inv) => (
              <div
                key={inv.id}
                className="p-4 bg-slate-900/60 border border-slate-800 rounded-lg space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <BrainCircuit className="w-4 h-4 text-purple-400" />
                    <span className="font-mono text-xs font-bold text-slate-200">{inv.id}</span>
                    <span className="text-[11px] text-slate-500">
                      via {inv.provider} ({inv.model_name})
                    </span>
                  </div>
                  <Badge variant="status" value={inv.status} />
                </div>
                {inv.summary && <p className="text-xs text-slate-300">{inv.summary}</p>}
                <div className="pt-2 flex items-center justify-between text-[11px] text-slate-500">
                  <span>Created: {new Date(inv.created_at).toLocaleString()}</span>
                  <Link
                    to={`/investigations?investigationId=${inv.id}`}
                    className="text-indigo-400 hover:text-indigo-300 font-medium"
                  >
                    View Full Investigation Report →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Resolve Incident Modal */}
      <Modal
        isOpen={showResolveModal}
        onClose={() => setShowResolveModal(false)}
        title="Resolve Incident & Record SRE Memory"
        description="Records human-verified resolution into persistent database and vector episodic memory."
      >
        <form onSubmit={handleResolveSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Identified Root Cause *
            </label>
            <textarea
              value={rootCause}
              onChange={(e) => setRootCause(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 text-xs bg-slate-950 border border-slate-800 rounded-md text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              placeholder="e.g. Unclosed SQLAlchemy sessions leaked DB connections under spike..."
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Action Taken *
            </label>
            <textarea
              value={actionTaken}
              onChange={(e) => setActionTaken(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 text-xs bg-slate-950 border border-slate-800 rounded-md text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              placeholder="e.g. Scaled PgBouncer connection limit and recycled auth-service pods..."
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Prevention Steps & Runbook Notes
            </label>
            <textarea
              value={preventionSteps}
              onChange={(e) => setPreventionSteps(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 text-xs bg-slate-950 border border-slate-800 rounded-md text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              placeholder="e.g. Add alert threshold on idle in transaction connection states..."
            />
          </div>

          <Input
            label="Verified By"
            value={verifiedBy}
            onChange={(e) => setVerifiedBy(e.target.value)}
            required
            helperText="Only verified resolutions enter trusted episodic memory."
          />

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setShowResolveModal(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={resolveMutation.isPending}
            >
              Confirm & Resolve
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
