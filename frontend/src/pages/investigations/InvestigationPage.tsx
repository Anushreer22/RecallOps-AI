import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  Brain,
  Sparkles,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileText,
  ShieldCheck,
  ChevronRight,
  Database,
} from 'lucide-react';
import { incidentsApi } from '../../api/incidents';
import { investigationsApi } from '../../api/investigations';
import {
  Incident,
  InvestigationResponse,
  HistoricalRecallMatch,
  InvestigationFeedbackCreate,
} from '../../types';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge, SeverityBadge, StatusBadge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { Input, Textarea } from '../../components/ui/Input';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { useAuth } from '../../context/AuthContext';

export const InvestigationPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const incidentParam = searchParams.get('incidentId');
  const { isViewer } = useAuth();

  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>(incidentParam || '');
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [investigations, setInvestigations] = useState<InvestigationResponse[]>([]);
  const [activeInvestigation, setActiveInvestigation] = useState<InvestigationResponse | null>(null);
  const [memoryMatches, setMemoryMatches] = useState<HistoricalRecallMatch[]>([]);

  const [loadingIncidents, setLoadingIncidents] = useState(false);
  const [loadingInvestigation, setLoadingInvestigation] = useState(false);
  const [runningInvestigation, setRunningInvestigation] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string>('mock');

  // Approval / Rejection modal state
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [reviewAction, setReviewAction] = useState<'APPROVE' | 'REJECT'>('APPROVE');
  const [verifiedBy, setVerifiedBy] = useState('');
  const [rootCauseInput, setRootCauseInput] = useState('');
  const [actionTakenInput, setActionTakenInput] = useState('');
  const [preventionInput, setPreventionInput] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [submittingReview, setSubmittingReview] = useState(false);
  const [reviewSuccessMsg, setReviewSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load list of incidents for selector
  useEffect(() => {
    const fetchIncidents = async () => {
      setLoadingIncidents(true);
      try {
        const list = await incidentsApi.list(undefined, 0, 50);
        setIncidents(list);
        if (!selectedIncidentId && list.length > 0) {
          setSelectedIncidentId(list[0].id);
        }
      } catch (err: any) {
        console.error('Failed to load incidents', err);
      } finally {
        setLoadingIncidents(false);
      }
    };
    fetchIncidents();
  }, []);

  // Update URL param when selected incident changes
  useEffect(() => {
    if (selectedIncidentId) {
      setSearchParams({ incidentId: selectedIncidentId });
    }
  }, [selectedIncidentId, setSearchParams]);

  // Load incident details and existing investigations
  useEffect(() => {
    if (!selectedIncidentId) return;

    const loadData = async () => {
      setLoadingInvestigation(true);
      setErrorMsg(null);
      setReviewSuccessMsg(null);
      try {
        const [inc, invs, mem] = await Promise.all([
          incidentsApi.getById(selectedIncidentId),
          investigationsApi.listByIncident(selectedIncidentId).catch(() => []),
          incidentsApi.searchMemory(selectedIncidentId).catch(() => []),
        ]);
        setSelectedIncident(inc);
        setInvestigations(invs);
        setMemoryMatches(mem);

        if (invs.length > 0) {
          setActiveInvestigation(invs[0]);
          // Pre-populate approval form from top hypothesis if available
          const topHypothesis = invs[0].report?.probable_root_causes?.[0]?.hypothesis || invs[0].summary || '';
          setRootCauseInput(topHypothesis);
          const topRemediation = invs[0].report?.suggested_resolution?.join('; ') || '';
          setActionTakenInput(topRemediation);
        } else {
          setActiveInvestigation(null);
        }
      } catch (err: any) {
        setErrorMsg(err.response?.data?.detail || err.message || 'Failed to load investigation data');
      } finally {
        setLoadingInvestigation(false);
      }
    };

    loadData();
  }, [selectedIncidentId]);

  const handleRunInvestigation = async () => {
    if (!selectedIncidentId || isViewer) return;
    setRunningInvestigation(true);
    setErrorMsg(null);
    setReviewSuccessMsg(null);
    try {
      const inv = await investigationsApi.run(selectedIncidentId, selectedProvider);
      setActiveInvestigation(inv);
      setInvestigations((prev) => [inv, ...prev.filter((item) => item.id !== inv.id)]);

      // Pre-fill modal
      const topHypothesis = inv.report?.probable_root_causes?.[0]?.hypothesis || inv.summary || '';
      setRootCauseInput(topHypothesis);
      const topRemediation = inv.report?.suggested_resolution?.join('; ') || '';
      setActionTakenInput(topRemediation);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Investigation run failed');
    } finally {
      setRunningInvestigation(false);
    }
  };

  const openReviewModal = (action: 'APPROVE' | 'REJECT') => {
    setReviewAction(action);
    setReviewModalOpen(true);
  };

  const handleSubmitReview = async () => {
    if (!activeInvestigation) return;
    if (reviewAction === 'APPROVE' && !verifiedBy.trim()) {
      alert('Please specify the on-call engineer or SRE verifying this resolution.');
      return;
    }

    setSubmittingReview(true);
    setErrorMsg(null);
    try {
      const payload: InvestigationFeedbackCreate = {
        approved: reviewAction === 'APPROVE',
        verified_by: verifiedBy.trim() || 'On-Call Engineer',
        root_cause: rootCauseInput.trim() || undefined,
        action_taken: actionTakenInput.trim() || undefined,
        prevention_steps: preventionInput.trim() || undefined,
        notes: reviewNotes.trim() || undefined,
      };

      const res = await investigationsApi.submitFeedback(activeInvestigation.id, payload);
      setReviewModalOpen(false);
      setReviewSuccessMsg(
        reviewAction === 'APPROVE'
          ? `Verified & resolved! Episodic memory indexed: ${res.memory_indexed ? 'Yes' : 'No'}.`
          : 'Investigation rejected. Incident remains open for manual triage.'
      );

      // Refresh incident state
      if (selectedIncidentId) {
        const updated = await incidentsApi.getById(selectedIncidentId);
        setSelectedIncident(updated);
      }
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Feedback submission failed');
    } finally {
      setSubmittingReview(false);
    }
  };

  const report = activeInvestigation?.report;

  return (
    <div className="space-y-6">
      {/* Top Header & Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-surface-200 dark:border-surface-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-white">
              AI Incident Investigation
            </h1>
            <Badge variant="purple" size="sm">
              <Sparkles className="w-3 h-3 mr-1" />
              SRE Copilot
            </Badge>
          </div>
          <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
            Grounded multi-modal root cause deduction with episodic memory retrieval and human review loop.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Incident Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400">
              Target Incident:
            </span>
            <select
              value={selectedIncidentId}
              onChange={(e) => setSelectedIncidentId(e.target.value)}
              className="bg-surface-50 dark:bg-surface-900 border border-surface-300 dark:border-surface-700 text-surface-900 dark:text-surface-100 text-sm rounded-lg px-3 py-1.5 focus:ring-1 focus:ring-brand-500"
            >
              {loadingIncidents ? (
                <option>Loading incidents...</option>
              ) : incidents.length === 0 ? (
                <option value="">No incidents found</option>
              ) : (
                incidents.map((inc) => (
                  <option key={inc.id} value={inc.id}>
                    [{inc.severity}] {inc.title.slice(0, 36)}... ({inc.service_name})
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Provider Selector */}
          <select
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
            disabled={isViewer || runningInvestigation}
            className="bg-surface-50 dark:bg-surface-900 border border-surface-300 dark:border-surface-700 text-surface-900 dark:text-surface-100 text-sm rounded-lg px-3 py-1.5 focus:ring-1 focus:ring-brand-500"
          >
            <option value="mock">Engine: Deterministic Mock</option>
            <option value="openai">Engine: OpenAI GPT-4o</option>
          </select>

          {/* Run Investigation Button */}
          <Button
            variant="primary"
            onClick={handleRunInvestigation}
            loading={runningInvestigation}
            disabled={!selectedIncidentId || isViewer}
            title={isViewer ? 'Requires Engineer role or higher' : undefined}
          >
            <Brain className="w-4 h-4 mr-2" />
            {runningInvestigation ? 'Investigating...' : 'Run Investigation'}
          </Button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-lg bg-danger-500/10 border border-danger-500/20 text-danger-500 text-sm flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-xs font-semibold hover:underline">
            Dismiss
          </button>
        </div>
      )}

      {reviewSuccessMsg && (
        <div className="p-4 rounded-lg bg-success-500/10 border border-success-500/20 text-success-500 text-sm flex items-center justify-between">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            {reviewSuccessMsg}
          </span>
          <button onClick={() => setReviewSuccessMsg(null)} className="text-xs font-semibold hover:underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Main Grid: Left Column Incident Telemetry + Right Column AI Output */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Incident Telemetry & Memory Context (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          {/* Incident Telemetry Card */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400">
                  Incident Telemetry
                </span>
                {selectedIncident && (
                  <Link
                    to={`/incidents/${selectedIncident.id}`}
                    className="text-xs text-brand-500 hover:text-brand-400 flex items-center gap-1 font-medium"
                  >
                    View Incident <ChevronRight className="w-3 h-3" />
                  </Link>
                )}
              </div>
              <h2 className="text-base font-semibold text-surface-900 dark:text-white mt-1">
                {selectedIncident ? selectedIncident.title : 'No Incident Selected'}
              </h2>
            </CardHeader>

            <CardBody className="space-y-4 text-sm">
              {loadingInvestigation ? (
                <div className="py-8 flex justify-center">
                  <LoadingSpinner size="md" />
                </div>
              ) : selectedIncident ? (
                <>
                  <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-surface-50 dark:bg-surface-800/50 border border-surface-200 dark:border-surface-800">
                    <div>
                      <span className="text-xs text-surface-500 dark:text-surface-400 block">Severity</span>
                      <SeverityBadge severity={selectedIncident.severity} />
                    </div>
                    <div>
                      <span className="text-xs text-surface-500 dark:text-surface-400 block">Status</span>
                      <StatusBadge status={selectedIncident.status} />
                    </div>
                    <div>
                      <span className="text-xs text-surface-500 dark:text-surface-400 block">Service</span>
                      <span className="font-mono text-xs font-semibold text-surface-900 dark:text-surface-100">
                        {selectedIncident.service_name}
                      </span>
                    </div>
                    <div>
                      <span className="text-xs text-surface-500 dark:text-surface-400 block">Impacted Users</span>
                      <span className="font-semibold text-surface-900 dark:text-surface-100">
                        {selectedIncident.impacted_users.toLocaleString()}
                      </span>
                    </div>
                  </div>

                  <div>
                    <span className="text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 block mb-1">
                      Raw Logs / Error Signature
                    </span>
                    <pre className="p-2.5 rounded-lg bg-surface-900 text-surface-200 font-mono text-xs overflow-x-auto max-h-48 border border-surface-800 leading-relaxed whitespace-pre-wrap">
                      {selectedIncident.raw_logs || 'No raw logs attached to this event.'}
                    </pre>
                  </div>

                  {selectedIncident.resolution && (
                    <div className="p-3 rounded-lg bg-success-500/10 border border-success-500/20 text-xs space-y-1">
                      <div className="font-semibold text-success-500 flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Verified Human Resolution
                      </div>
                      <p className="text-surface-600 dark:text-surface-300">
                        <strong className="text-surface-900 dark:text-white">Cause:</strong>{' '}
                        {selectedIncident.resolution.root_cause}
                      </p>
                      <p className="text-surface-600 dark:text-surface-300">
                        <strong className="text-surface-900 dark:text-white">Fix:</strong>{' '}
                        {selectedIncident.resolution.action_taken}
                      </p>
                    </div>
                  )}
                </>
              ) : (
                <EmptyState title="No Incident Selected" message="Select an incident above to start." />
              )}
            </CardBody>
          </Card>

          {/* Historical Episodic Memory Matches */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-brand-500" />
                <h3 className="text-sm font-semibold text-surface-900 dark:text-white">
                  Episodic Memory Recall
                </h3>
              </div>
              <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                Top vector-similarity historical resolutions rehydrated from DB
              </p>
            </CardHeader>
            <CardBody className="space-y-3">
              {memoryMatches.length === 0 ? (
                <div className="text-xs text-surface-500 dark:text-surface-400 py-3 text-center">
                  No similar historical incidents found in persistent memory.
                </div>
              ) : (
                memoryMatches.map((match, idx) => (
                  <div
                    key={match.incident_id || idx}
                    className="p-3 rounded-lg bg-surface-50 dark:bg-surface-800/40 border border-surface-200 dark:border-surface-800 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-surface-900 dark:text-white truncate max-w-[200px]">
                        {match.title}
                      </span>
                      <Badge variant="purple" size="sm">
                        {(match.similarity_score * 100).toFixed(0)}% match
                      </Badge>
                    </div>
                    {match.root_cause && (
                      <p className="text-xs text-surface-600 dark:text-surface-300 line-clamp-2">
                        <strong className="text-surface-900 dark:text-surface-100">Root Cause:</strong>{' '}
                        {match.root_cause}
                      </p>
                    )}
                    {match.verified_fix && (
                      <p className="text-xs text-emerald-600 dark:text-emerald-400 line-clamp-2">
                        <strong>Fix:</strong> {match.verified_fix}
                      </p>
                    )}
                  </div>
                ))
              )}
            </CardBody>
          </Card>
        </div>

        {/* Right Column: AI Investigation Findings & Review Panel (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          {loadingInvestigation || runningInvestigation ? (
            <Card className="p-12 flex flex-col items-center justify-center text-center space-y-4">
              <LoadingSpinner size="lg" />
              <div>
                <h4 className="text-base font-semibold text-surface-900 dark:text-white">
                  {runningInvestigation ? 'Deducing Root Cause with AI...' : 'Loading Investigation...'}
                </h4>
                <p className="text-xs text-surface-500 dark:text-surface-400 max-w-md mt-1">
                  Ingesting telemetry, tracing dependency blast radius, querying persistent episodic memory, and
                  grounding hypotheses.
                </p>
              </div>
            </Card>
          ) : !activeInvestigation ? (
            <Card className="p-12 text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-brand-500/10 text-brand-500 flex items-center justify-center mx-auto">
                <Brain className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-surface-900 dark:text-white">
                  No Active Investigation Found
                </h3>
                <p className="text-sm text-surface-500 dark:text-surface-400 max-w-md mx-auto mt-1">
                  Run the AI investigation engine to analyze logs, trace blast radius, evaluate historical resolutions,
                  and generate grounded remediation runbooks.
                </p>
              </div>
              <Button
                variant="primary"
                onClick={handleRunInvestigation}
                disabled={!selectedIncidentId || isViewer}
              >
                <Sparkles className="w-4 h-4 mr-2" />
                Run Investigation Now
              </Button>
            </Card>
          ) : (
            <>
              {/* Executive Summary Card */}
              <Card>
                <CardHeader>
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant="success" size="sm">
                          <CheckCircle2 className="w-3 h-3 mr-1" />
                          Investigation Complete {investigations.length > 1 ? `(${investigations.length})` : ''}
                        </Badge>
                        <span className="text-xs font-mono text-surface-500 dark:text-surface-400">
                          ID: {activeInvestigation.id.slice(0, 8)}
                        </span>
                      </div>
                      <h2 className="text-lg font-bold text-surface-900 dark:text-white mt-1">
                        Executive Diagnostic Summary
                      </h2>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <span className="text-[10px] uppercase font-semibold text-surface-500 dark:text-surface-400 block">
                          Provider / Model
                        </span>
                        <span className="text-xs font-mono font-medium text-surface-900 dark:text-surface-100">
                          {activeInvestigation.provider} ({activeInvestigation.model_name})
                        </span>
                      </div>
                    </div>
                  </div>
                </CardHeader>

                <CardBody className="space-y-4">
                  <div className="p-4 rounded-lg bg-surface-50 dark:bg-surface-800/40 border border-surface-200 dark:border-surface-800 text-sm leading-relaxed text-surface-800 dark:text-surface-200">
                    {report?.summary || activeInvestigation.summary || 'Summary unavailable.'}
                  </div>

                  {/* Observed Facts */}
                  {report?.observed_facts && report.observed_facts.length > 0 && (
                    <div>
                      <span className="text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 block mb-2">
                        Observed Grounded Facts
                      </span>
                      <ul className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {report.observed_facts.map((fact, idx) => (
                          <li
                            key={idx}
                            className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-800/30 border border-surface-200 dark:border-surface-800/60 text-xs flex items-start gap-2"
                          >
                            <ShieldCheck className="w-3.5 h-3.5 text-brand-500 flex-shrink-0 mt-0.5" />
                            <span className="text-surface-700 dark:text-surface-300">{fact}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </CardBody>
              </Card>

              {/* Probable Root Causes */}
              <Card>
                <CardHeader>
                  <h3 className="text-base font-semibold text-surface-900 dark:text-white flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-warning-500" />
                    Probable Root Causes & Grounded Evidence
                  </h3>
                </CardHeader>
                <CardBody className="space-y-4">
                  {(!report?.probable_root_causes || report.probable_root_causes.length === 0) ? (
                    <div className="text-sm text-surface-500 dark:text-surface-400">
                      No distinct root cause hypotheses returned.
                    </div>
                  ) : (
                    report.probable_root_causes.map((cause, idx) => {
                      const confidence = Math.round((cause.confidence_score ?? cause.probability ?? 0.8) * 100);
                      return (
                        <div
                          key={idx}
                          className="p-4 rounded-lg bg-surface-50 dark:bg-surface-800/40 border border-surface-200 dark:border-surface-800 space-y-3"
                        >
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <h4 className="font-semibold text-sm text-surface-900 dark:text-white">
                              {cause.hypothesis || cause.title || 'Failure Hypothesis'}
                            </h4>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-surface-500 dark:text-surface-400">Confidence:</span>
                              <div className="w-24 bg-surface-200 dark:bg-surface-700 h-2 rounded-full overflow-hidden">
                                <div
                                  className="bg-brand-500 h-full rounded-full transition-all"
                                  style={{ width: `${confidence}%` }}
                                />
                              </div>
                              <span className="text-xs font-mono font-bold text-surface-900 dark:text-white">
                                {confidence}%
                              </span>
                            </div>
                          </div>

                          <p className="text-xs text-surface-700 dark:text-surface-300 leading-relaxed">
                            {cause.reasoning}
                          </p>

                          {/* Grounded Evidence IDs */}
                          {cause.supporting_evidence_ids && cause.supporting_evidence_ids.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1.5 pt-1">
                              <span className="text-[11px] font-semibold text-surface-500 dark:text-surface-400 mr-1">
                                Grounded In:
                              </span>
                              {cause.supporting_evidence_ids.map((evId) => (
                                <span
                                  key={evId}
                                  className="px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-brand-500/10 text-brand-500 border border-brand-500/20"
                                >
                                  {evId}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </CardBody>
              </Card>

              {/* Recommended Action / Runbook Steps */}
              <Card>
                <CardHeader>
                  <h3 className="text-base font-semibold text-surface-900 dark:text-white flex items-center gap-2">
                    <FileText className="w-4 h-4 text-emerald-500" />
                    Recommended Remediation Runbook
                  </h3>
                </CardHeader>
                <CardBody className="space-y-3">
                  {report?.suggested_resolution && report.suggested_resolution.length > 0 ? (
                    report.suggested_resolution.map((step, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-lg bg-surface-50 dark:bg-surface-800/40 border border-surface-200 dark:border-surface-800 flex items-start gap-3"
                      >
                        <span className="w-6 h-6 rounded-full bg-surface-200 dark:bg-surface-700 text-surface-800 dark:text-surface-200 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                          {idx + 1}
                        </span>
                        <div className="text-xs text-surface-800 dark:text-surface-200 leading-relaxed">
                          {step}
                        </div>
                      </div>
                    ))
                  ) : report?.suggested_investigation_steps && report.suggested_investigation_steps.length > 0 ? (
                    report.suggested_investigation_steps.map((step, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-lg bg-surface-50 dark:bg-surface-800/40 border border-surface-200 dark:border-surface-800 flex items-start gap-3"
                      >
                        <span className="w-6 h-6 rounded-full bg-surface-200 dark:bg-surface-700 text-surface-800 dark:text-surface-200 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                          {idx + 1}
                        </span>
                        <div className="text-xs text-surface-800 dark:text-surface-200 leading-relaxed">
                          {step}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-xs text-surface-500 dark:text-surface-400">
                      No automated runbook steps recommended.
                    </div>
                  )}
                </CardBody>
              </Card>

              {/* Human-in-the-Loop Decision Panel */}
              <Card className="border-brand-500/30 dark:border-brand-500/30 shadow-md">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-5 h-5 text-brand-500" />
                      <div>
                        <h3 className="text-base font-bold text-surface-900 dark:text-white">
                          Human-in-the-Loop Review
                        </h3>
                        <p className="text-xs text-surface-500 dark:text-surface-400">
                          Verify AI findings. Approved resolutions are permanently indexed into episodic memory.
                        </p>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardBody>
                  <div className="flex flex-col sm:flex-row items-center gap-3">
                    <Button
                      variant="primary"
                      onClick={() => openReviewModal('APPROVE')}
                      disabled={isViewer}
                      className="w-full sm:w-auto"
                    >
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                      Approve & Commit to Memory
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => openReviewModal('REJECT')}
                      disabled={isViewer}
                      className="w-full sm:w-auto text-danger-500 hover:text-danger-600 border-danger-500/30"
                    >
                      <XCircle className="w-4 h-4 mr-2" />
                      Reject AI Hypothesis
                    </Button>
                  </div>
                </CardBody>
              </Card>
            </>
          )}
        </div>
      </div>

      {/* Human Review Modal */}
      <Modal
        isOpen={reviewModalOpen}
        onClose={() => setReviewModalOpen(false)}
        title={reviewAction === 'APPROVE' ? 'Approve AI Resolution & Index Memory' : 'Reject AI Hypothesis'}
        size="lg"
      >
        <div className="space-y-4 text-sm">
          <p className="text-surface-600 dark:text-surface-300 text-xs">
            {reviewAction === 'APPROVE'
              ? 'Approving marks this incident as RESOLVED, creates an authoritative resolution record, and persists this knowledge into TF-IDF vector memory for future automatic triage.'
              : 'Rejecting prevents false or ungrounded AI recommendations from entering the trusted knowledge base. The incident will remain active.'}
          </p>

          <Input
            label="Verifying On-Call Engineer *"
            placeholder="e.g. Alice Chen (Senior SRE)"
            value={verifiedBy}
            onChange={(e) => setVerifiedBy(e.target.value)}
          />

          {reviewAction === 'APPROVE' && (
            <>
              <Textarea
                label="Confirmed Root Cause"
                rows={2}
                value={rootCauseInput}
                onChange={(e) => setRootCauseInput(e.target.value)}
                placeholder="Confirmed failure mechanism..."
              />

              <Textarea
                label="Action Taken / Remediation"
                rows={2}
                value={actionTakenInput}
                onChange={(e) => setActionTakenInput(e.target.value)}
                placeholder="Remediation steps executed..."
              />

              <Textarea
                label="Prevention Steps (Optional)"
                rows={2}
                value={preventionInput}
                onChange={(e) => setPreventionInput(e.target.value)}
                placeholder="Guardrails, alerting or circuit breaker additions..."
              />
            </>
          )}

          <Textarea
            label={reviewAction === 'APPROVE' ? 'Review Notes (Optional)' : 'Rejection Reason / Notes *'}
            rows={2}
            value={reviewNotes}
            onChange={(e) => setReviewNotes(e.target.value)}
            placeholder={
              reviewAction === 'APPROVE'
                ? 'Optional notes on the investigation report...'
                : 'Why is this hypothesis rejected? (e.g. Misidentified root cause, logs indicate different DB pool)'
            }
          />

          <div className="flex justify-end gap-3 pt-3 border-t border-surface-200 dark:border-surface-800">
            <Button variant="ghost" onClick={() => setReviewModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant={reviewAction === 'APPROVE' ? 'primary' : 'danger'}
              onClick={handleSubmitReview}
              loading={submittingReview}
            >
              {reviewAction === 'APPROVE' ? 'Confirm & Resolve' : 'Submit Rejection'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
