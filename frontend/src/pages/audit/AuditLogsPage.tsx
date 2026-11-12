import React, { useState, useEffect } from 'react';
import { ShieldCheck, RefreshCw, Filter, Code } from 'lucide-react';
import { auditApi } from '../../api/audit';
import { AuditLogItem } from '../../types';
import { Card, CardBody } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';

export const AuditLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [actionFilter, setActionFilter] = useState('ALL');
  const [resourceFilter, setResourceFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);
  const [selectedLog, setSelectedLog] = useState<AuditLogItem | null>(null);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await auditApi.list(actionFilter, resourceFilter, 100);
      setLogs(data);
    } catch (err: any) {
      console.error('Failed to load audit logs', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [actionFilter, resourceFilter]);

  const getActionBadge = (action: string) => {
    if (action.includes('RESOLVE') || action.includes('APPROVE')) {
      return <Badge variant="success">{action}</Badge>;
    }
    if (action.includes('INVESTIGATION')) {
      return <Badge variant="purple">{action}</Badge>;
    }
    if (action.includes('DELETE') || action.includes('REJECT')) {
      return <Badge variant="danger">{action}</Badge>;
    }
    if (action.includes('CREATE') || action.includes('ADD')) {
      return <Badge variant="blue">{action}</Badge>;
    }
    return <Badge variant="neutral">{action}</Badge>;
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-200 dark:border-surface-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-white">
              Security Audit Log
            </h1>
            <Badge variant="blue" size="sm">
              <ShieldCheck className="w-3 h-3 mr-1" />
              SOC 2 Compliant
            </Badge>
          </div>
          <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
            Immutable, cryptographically correlated audit trail of all administrative and incident response actions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={fetchLogs} loading={loading}>
            <RefreshCw className="w-4 h-4 mr-1.5" />
            Refresh Trail
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 p-4 rounded-xl bg-surface-50 dark:bg-surface-800/60 border border-surface-200 dark:border-surface-800">
        <Filter className="w-4 h-4 text-surface-400" />
        <span className="text-xs font-semibold text-surface-700 dark:text-surface-300">
          Filters:
        </span>

        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="bg-white dark:bg-surface-900 border border-surface-300 dark:border-surface-700 text-surface-900 dark:text-surface-100 text-xs rounded-lg px-3 py-1.5"
        >
          <option value="ALL">All Actions</option>
          <option value="INCIDENT_CREATE">INCIDENT_CREATE</option>
          <option value="INCIDENT_RESOLVE">INCIDENT_RESOLVE</option>
          <option value="INVESTIGATION_RUN">INVESTIGATION_RUN</option>
          <option value="INVESTIGATION_FEEDBACK">INVESTIGATION_FEEDBACK</option>
          <option value="MEMBER_ADD">MEMBER_ADD</option>
          <option value="MEMBER_ROLE_UPDATE">MEMBER_ROLE_UPDATE</option>
          <option value="SERVICE_CREATE">SERVICE_CREATE</option>
          <option value="DEPENDENCY_CREATE">DEPENDENCY_CREATE</option>
        </select>

        <select
          value={resourceFilter}
          onChange={(e) => setResourceFilter(e.target.value)}
          className="bg-white dark:bg-surface-900 border border-surface-300 dark:border-surface-700 text-surface-900 dark:text-surface-100 text-xs rounded-lg px-3 py-1.5"
        >
          <option value="ALL">All Resource Types</option>
          <option value="incident">incident</option>
          <option value="investigation">investigation</option>
          <option value="service">service</option>
          <option value="dependency">dependency</option>
          <option value="organization">organization</option>
          <option value="user">user</option>
        </select>
      </div>

      {/* Table */}
      <Card>
        <CardBody className="p-0">
          {loading ? (
            <div className="py-16 flex justify-center">
              <LoadingSpinner size="lg" />
            </div>
          ) : logs.length === 0 ? (
            <EmptyState
              title="No audit entries match filter"
              message="Audit entries are generated automatically as operations execute."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-50 dark:bg-surface-800/50 text-surface-500 dark:text-surface-400 border-b border-surface-200 dark:border-surface-800 uppercase tracking-wider font-semibold">
                  <tr>
                    <th className="px-6 py-3.5">Timestamp</th>
                    <th className="px-6 py-3.5">Action</th>
                    <th className="px-6 py-3.5">Resource</th>
                    <th className="px-6 py-3.5">Actor User</th>
                    <th className="px-6 py-3.5">Request ID</th>
                    <th className="px-6 py-3.5 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-200 dark:divide-surface-800">
                  {logs.map((log) => (
                    <tr
                      key={log.id}
                      className="hover:bg-surface-50/50 dark:hover:bg-surface-800/30 transition-colors"
                    >
                      <td className="px-6 py-3.5 text-surface-500 dark:text-surface-400 font-mono whitespace-nowrap">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-3.5">{getActionBadge(log.action)}</td>
                      <td className="px-6 py-3.5">
                        <span className="font-semibold text-surface-900 dark:text-white capitalize">
                          {log.resource_type}
                        </span>
                        {log.resource_id && (
                          <div className="font-mono text-[10px] text-surface-400 truncate max-w-[140px]">
                            {log.resource_id}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-3.5 font-mono text-surface-600 dark:text-surface-300">
                        {log.actor_user_id ? log.actor_user_id.slice(0, 12) : 'System / Service'}
                      </td>
                      <td className="px-6 py-3.5 font-mono text-[11px] text-surface-400 truncate max-w-[120px]">
                        {log.request_id || '—'}
                      </td>
                      <td className="px-6 py-3.5 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedLog(log)}
                          title="View metadata payload"
                        >
                          <Code className="w-3.5 h-3.5 mr-1" />
                          Metadata
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

      {/* Metadata Detail Modal */}
      <Modal
        isOpen={!!selectedLog}
        onClose={() => setSelectedLog(null)}
        title={`Audit Event: ${selectedLog?.action || ''}`}
        size="md"
      >
        <div className="space-y-4 text-xs">
          <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-surface-100 dark:bg-surface-800">
            <div>
              <span className="text-[10px] uppercase font-bold text-surface-500">Resource</span>
              <div className="font-semibold text-surface-900 dark:text-white capitalize">
                {selectedLog?.resource_type} ({selectedLog?.resource_id || 'Global'})
              </div>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-surface-500">Timestamp</span>
              <div className="text-surface-900 dark:text-white">
                {selectedLog?.created_at ? new Date(selectedLog.created_at).toLocaleString() : '—'}
              </div>
            </div>
          </div>

          <div>
            <span className="text-[10px] uppercase font-bold text-surface-500 block mb-1">
              Structured Event Metadata
            </span>
            <pre className="p-3 rounded-lg bg-surface-900 text-surface-200 font-mono text-[11px] overflow-x-auto max-h-72 border border-surface-800 whitespace-pre-wrap">
              {selectedLog?.metadata_json
                ? JSON.stringify(JSON.parse(selectedLog.metadata_json), null, 2)
                : 'No structured metadata recorded.'}
            </pre>
          </div>

          <div className="flex justify-end pt-2 border-t border-surface-200 dark:border-surface-800">
            <Button variant="primary" size="sm" onClick={() => setSelectedLog(null)}>
              Close
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
