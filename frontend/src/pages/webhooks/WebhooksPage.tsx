import React, { useState, useEffect } from 'react';
import {
  Webhook,
  Copy,
  Check,
  RefreshCw,
  FileJson,
} from 'lucide-react';
import { webhooksApi } from '../../api/webhooks';
import { WebhookEventItem } from '../../types';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';

export const WebhooksPage: React.FC = () => {
  const [events, setEvents] = useState<WebhookEventItem[]>([]);
  const [providerFilter, setProviderFilter] = useState<string>('ALL');
  const [loading, setLoading] = useState(true);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Selected payload modal
  const [selectedEvent, setSelectedEvent] = useState<WebhookEventItem | null>(null);

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const data = await webhooksApi.listEvents(providerFilter);
      setEvents(data);
    } catch (err: any) {
      console.error('Failed to load webhook events', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, [providerFilter]);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case 'PROCESSED':
        return <Badge variant="success">PROCESSED</Badge>;
      case 'DUPLICATE':
        return <Badge variant="warning">DUPLICATE</Badge>;
      case 'FAILED':
        return <Badge variant="danger">FAILED</Badge>;
      default:
        return <Badge variant="neutral">{status}</Badge>;
    }
  };

  const getProviderBadge = (provider: string) => {
    switch (provider.toLowerCase()) {
      case 'pagerduty':
        return <Badge variant="success">PagerDuty</Badge>;
      case 'datadog':
        return <Badge variant="purple">Datadog</Badge>;
      case 'alertmanager':
        return <Badge variant="blue">Alertmanager</Badge>;
      default:
        return <Badge variant="neutral">{provider}</Badge>;
    }
  };

  const currentOrigin = window.location.origin;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-200 dark:border-surface-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-white">
              Webhook Ingestion & Adapters
            </h1>
            <Badge variant="purple" size="sm">
              <Webhook className="w-3 h-3 mr-1" />
              Idempotent Ingestion
            </Badge>
          </div>
          <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
            Enterprise integrations with HMAC signature verification, atomic database idempotency, and normalized telemetry.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={fetchEvents} loading={loading}>
            <RefreshCw className="w-4 h-4 mr-1.5" />
            Refresh Log
          </Button>
        </div>
      </div>

      {/* Provider Integration Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* PagerDuty */}
        <Card className="hover:border-surface-400 dark:hover:border-surface-600 transition-colors">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-emerald-500/10 text-emerald-500 flex items-center justify-center font-bold text-xs">
                  PD
                </div>
                <h3 className="font-semibold text-surface-900 dark:text-white text-sm">
                  PagerDuty Webhooks
                </h3>
              </div>
              <Badge variant="success" size="sm">HMAC SHA-256</Badge>
            </div>
          </CardHeader>
          <CardBody className="space-y-3 text-xs">
            <p className="text-surface-600 dark:text-surface-400">
              Validates <code className="text-brand-500 font-mono">X-PagerDuty-Signature</code> headers with dual secret rotation support.
            </p>
            <div className="space-y-1">
              <span className="text-[10px] uppercase font-bold text-surface-500">Ingest URL</span>
              <div className="flex items-center gap-1.5 p-2 rounded bg-surface-100 dark:bg-surface-800 font-mono text-[11px] text-surface-800 dark:text-surface-200 overflow-hidden">
                <span className="truncate flex-1">/api/v1/webhooks/pagerduty</span>
                <button
                  onClick={() => copyToClipboard(`${currentOrigin}/api/v1/webhooks/pagerduty`, 'pd')}
                  className="text-surface-400 hover:text-white"
                  title="Copy URL"
                >
                  {copiedKey === 'pd' ? <Check className="w-3.5 h-3.5 text-success-500" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Datadog */}
        <Card className="hover:border-surface-400 dark:hover:border-surface-600 transition-colors">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-purple-500/10 text-purple-500 flex items-center justify-center font-bold text-xs">
                  DD
                </div>
                <h3 className="font-semibold text-surface-900 dark:text-white text-sm">
                  Datadog Webhooks
                </h3>
              </div>
              <Badge variant="purple" size="sm">Header Auth</Badge>
            </div>
          </CardHeader>
          <CardBody className="space-y-3 text-xs">
            <p className="text-surface-600 dark:text-surface-400">
              Parses monitor alerts with automatic snapshot rendering, transition triggers, and metric tags.
            </p>
            <div className="space-y-1">
              <span className="text-[10px] uppercase font-bold text-surface-500">Ingest URL</span>
              <div className="flex items-center gap-1.5 p-2 rounded bg-surface-100 dark:bg-surface-800 font-mono text-[11px] text-surface-800 dark:text-surface-200 overflow-hidden">
                <span className="truncate flex-1">/api/v1/webhooks/datadog</span>
                <button
                  onClick={() => copyToClipboard(`${currentOrigin}/api/v1/webhooks/datadog`, 'dd')}
                  className="text-surface-400 hover:text-white"
                  title="Copy URL"
                >
                  {copiedKey === 'dd' ? <Check className="w-3.5 h-3.5 text-success-500" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Prometheus Alertmanager */}
        <Card className="hover:border-surface-400 dark:hover:border-surface-600 transition-colors">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-blue-500/10 text-blue-500 flex items-center justify-center font-bold text-xs">
                  AM
                </div>
                <h3 className="font-semibold text-surface-900 dark:text-white text-sm">
                  Prometheus Alertmanager
                </h3>
              </div>
              <Badge variant="blue" size="sm">Bearer Token</Badge>
            </div>
          </CardHeader>
          <CardBody className="space-y-3 text-xs">
            <p className="text-surface-600 dark:text-surface-400">
              Normalizes Alertmanager v4 JSON payloads with firing/resolved transitions and fingerprint deduplication.
            </p>
            <div className="space-y-1">
              <span className="text-[10px] uppercase font-bold text-surface-500">Ingest URL</span>
              <div className="flex items-center gap-1.5 p-2 rounded bg-surface-100 dark:bg-surface-800 font-mono text-[11px] text-surface-800 dark:text-surface-200 overflow-hidden">
                <span className="truncate flex-1">/api/v1/webhooks/alertmanager</span>
                <button
                  onClick={() => copyToClipboard(`${currentOrigin}/api/v1/webhooks/alertmanager`, 'am')}
                  className="text-surface-400 hover:text-white"
                  title="Copy URL"
                >
                  {copiedKey === 'am' ? <Check className="w-3.5 h-3.5 text-success-500" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Filter and Events Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-surface-900 dark:text-white">
                Ingested Webhook Deliveries
              </h2>
              <p className="text-xs text-surface-500 dark:text-surface-400">
                Audited stream of provider deliveries, idempotency locks, and incident transitions
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-surface-500">Provider:</span>
              <select
                value={providerFilter}
                onChange={(e) => setProviderFilter(e.target.value)}
                className="bg-surface-50 dark:bg-surface-900 border border-surface-300 dark:border-surface-700 text-surface-900 dark:text-surface-100 text-xs rounded-lg px-3 py-1.5"
              >
                <option value="ALL">All Providers</option>
                <option value="pagerduty">PagerDuty</option>
                <option value="datadog">Datadog</option>
                <option value="alertmanager">Alertmanager</option>
              </select>
            </div>
          </div>
        </CardHeader>

        <CardBody className="p-0">
          {loading ? (
            <div className="py-16 flex justify-center">
              <LoadingSpinner size="lg" />
            </div>
          ) : events.length === 0 ? (
            <EmptyState
              title="No webhook events recorded"
              message="Deliveries from PagerDuty, Datadog, or Alertmanager will appear here in real-time."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-50 dark:bg-surface-800/50 text-surface-500 dark:text-surface-400 border-b border-surface-200 dark:border-surface-800 uppercase tracking-wider font-semibold">
                  <tr>
                    <th className="px-6 py-3.5">Provider</th>
                    <th className="px-6 py-3.5">Event ID & Key</th>
                    <th className="px-6 py-3.5">Type & Service</th>
                    <th className="px-6 py-3.5">Status</th>
                    <th className="px-6 py-3.5">Received At</th>
                    <th className="px-6 py-3.5 text-right">Payload</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-200 dark:divide-surface-800">
                  {events.map((ev) => (
                    <tr
                      key={ev.id}
                      className="hover:bg-surface-50/50 dark:hover:bg-surface-800/30 transition-colors"
                    >
                      <td className="px-6 py-4">{getProviderBadge(ev.provider)}</td>
                      <td className="px-6 py-4">
                        <div className="font-mono font-medium text-surface-900 dark:text-white truncate max-w-[180px]">
                          {ev.provider_event_id}
                        </div>
                        {ev.incident_key && (
                          <div className="text-[10px] text-surface-400 font-mono truncate max-w-[180px]">
                            Key: {ev.incident_key}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="font-semibold text-surface-900 dark:text-white">
                          {ev.event_type}
                        </div>
                        <div className="text-surface-500 font-mono text-[11px]">
                          {ev.service_name || '—'}
                        </div>
                      </td>
                      <td className="px-6 py-4">{getStatusBadge(ev.status)}</td>
                      <td className="px-6 py-4 text-surface-500 dark:text-surface-400">
                        {new Date(ev.received_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedEvent(ev)}
                          title="Inspect raw payload"
                        >
                          <FileJson className="w-3.5 h-3.5 mr-1" />
                          View
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Payload Modal */}
      <Modal
        isOpen={!!selectedEvent}
        onClose={() => setSelectedEvent(null)}
        title={`Webhook Event: ${selectedEvent?.provider_event_id || ''}`}
        size="lg"
      >
        <div className="space-y-4 text-xs">
          <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-surface-100 dark:bg-surface-800">
            <div>
              <span className="text-[10px] uppercase font-bold text-surface-500">Provider</span>
              <div className="font-semibold text-surface-900 dark:text-white capitalize">
                {selectedEvent?.provider}
              </div>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-surface-500">Status</span>
              <div>{selectedEvent && getStatusBadge(selectedEvent.status)}</div>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-surface-500">Internal Incident</span>
              <div className="font-mono text-surface-900 dark:text-white">
                {selectedEvent?.internal_incident_id || 'None'}
              </div>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-surface-500">Processed At</span>
              <div className="text-surface-900 dark:text-white">
                {selectedEvent?.processed_at ? new Date(selectedEvent.processed_at).toLocaleString() : '—'}
              </div>
            </div>
          </div>

          <div>
            <span className="text-[10px] uppercase font-bold text-surface-500 block mb-1">
              Sanitized Raw Payload Summary
            </span>
            <pre className="p-3 rounded-lg bg-surface-900 text-surface-200 font-mono text-[11px] overflow-x-auto max-h-72 border border-surface-800 whitespace-pre-wrap">
              {selectedEvent?.raw_payload_summary || 'No payload recorded.'}
            </pre>
          </div>

          <div className="flex justify-end pt-2 border-t border-surface-200 dark:border-surface-800">
            <Button variant="primary" size="sm" onClick={() => setSelectedEvent(null)}>
              Close
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
