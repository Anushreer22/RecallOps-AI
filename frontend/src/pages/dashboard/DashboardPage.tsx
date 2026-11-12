import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  Activity,
  CheckCircle2,
  Clock,
  Flame,
  BrainCircuit,
  Server,
  ArrowRight,
  TrendingUp,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import { incidentsApi } from '../../api/incidents';
import { healthApi } from '../../api/health';
import { servicesApi } from '../../api/services';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';

export const DashboardPage: React.FC = () => {
  const { data: incidents = [], isLoading: incidentsLoading } = useQuery({
    queryKey: ['incidents'],
    queryFn: () => incidentsApi.list(undefined, 0, 100),
  });

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: () => healthApi.check(),
  });

  const { data: services = [], isLoading: servicesLoading } = useQuery({
    queryKey: ['services'],
    queryFn: () => servicesApi.list(),
  });

  if (incidentsLoading || healthLoading || servicesLoading) {
    return <LoadingSpinner message="Aggregating operational intelligence..." />;
  }

  // Calculate real metrics directly from backend data
  const totalIncidents = incidents.length;
  const activeIncidents = incidents.filter(
    (i) => i.status === 'OPEN' || i.status === 'INVESTIGATING'
  ).length;
  const criticalIncidents = incidents.filter((i) => i.severity === 'CRITICAL').length;
  const resolvedIncidents = incidents.filter((i) => i.status === 'RESOLVED').length;

  // MTTR calculation from resolved incidents with resolution timestamps
  const resolvedWithTimestamps = incidents.filter(
    (i) => i.status === 'RESOLVED' && i.resolution?.resolved_at && i.created_at
  );

  let mttrString = 'Unavailable';
  if (resolvedWithTimestamps.length > 0) {
    const totalMinutes = resolvedWithTimestamps.reduce((acc, curr) => {
      const created = new Date(curr.created_at).getTime();
      const resolved = new Date(curr.resolution!.resolved_at).getTime();
      const diffMinutes = Math.max(0, (resolved - created) / (1000 * 60));
      return acc + diffMinutes;
    }, 0);
    const avgMinutes = Math.round(totalMinutes / resolvedWithTimestamps.length);
    mttrString = avgMinutes < 60 ? `${avgMinutes}m` : `${(avgMinutes / 60).toFixed(1)}h`;
  }

  // Severity Distribution Data
  const severityCounts: Record<string, number> = {
    CRITICAL: 0,
    HIGH: 0,
    MEDIUM: 0,
    LOW: 0,
  };
  incidents.forEach((i) => {
    if (severityCounts[i.severity] !== undefined) {
      severityCounts[i.severity]++;
    }
  });

  const severityChartData = [
    { name: 'Critical', value: severityCounts.CRITICAL, color: '#f43f5e' },
    { name: 'High', value: severityCounts.HIGH, color: '#f59e0b' },
    { name: 'Medium', value: severityCounts.MEDIUM, color: '#38bdf8' },
    { name: 'Low', value: severityCounts.LOW, color: '#94a3b8' },
  ];

  // Service Breakdown Data (Top impacted services)
  const serviceCounts: Record<string, number> = {};
  incidents.forEach((i) => {
    serviceCounts[i.service_name] = (serviceCounts[i.service_name] || 0) + 1;
  });
  const serviceChartData = Object.entries(serviceCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name, count]) => ({ name, count }));

  return (
    <div className="space-y-6">
      {/* Page Title & Slogan */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            Operations Command Center
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time incident response telemetry, priority triage & service health
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/incidents"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 rounded-md border border-slate-700 transition"
          >
            Manage Incidents
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <Card className="!p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Total Incidents</span>
            <Activity className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100 font-mono">{totalIncidents}</span>
            <span className="text-[10px] text-slate-500">recorded</span>
          </div>
        </Card>

        <Card className="!p-4 border-rose-500/30 bg-rose-950/10">
          <div className="flex items-center justify-between">
            <span className="text-xs text-rose-300 font-medium">Active / Triage</span>
            <Flame className="w-4 h-4 text-rose-400 animate-pulse" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-rose-300 font-mono">{activeIncidents}</span>
            <span className="text-[10px] text-rose-400/70">unmitigated</span>
          </div>
        </Card>

        <Card className="!p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Critical (P0)</span>
            <AlertTriangle className="w-4 h-4 text-rose-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100 font-mono">{criticalIncidents}</span>
            <span className="text-[10px] text-slate-500">sev-critical</span>
          </div>
        </Card>

        <Card className="!p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Resolved</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-emerald-400 font-mono">
              {resolvedIncidents}
            </span>
            <span className="text-[10px] text-slate-500">verified</span>
          </div>
        </Card>

        <Card className="!p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Mean Time to Resolve</span>
            <Clock className="w-4 h-4 text-sky-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-100 font-mono">{mttrString}</span>
            <span className="text-[10px] text-slate-500">avg MTTR</span>
          </div>
        </Card>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Severity Distribution */}
        <Card title="Incident Severity Breakdown" subtitle="Distribution of outages by business criticality">
          <div className="h-64 w-full flex items-center justify-center">
            {totalIncidents === 0 ? (
              <span className="text-xs text-slate-500">No incident telemetry recorded</span>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={severityChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {severityChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      borderRadius: '0.375rem',
                      fontSize: '0.75rem',
                      color: '#f8fafc',
                    }}
                  />
                  <Legend
                    verticalAlign="bottom"
                    iconSize={8}
                    formatter={(val) => <span className="text-xs text-slate-300">{val}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        {/* Top Impacted Services */}
        <Card
          title="Top Impacted Services"
          subtitle="Microservices with highest frequency of incident alerts"
        >
          <div className="h-64 w-full">
            {serviceChartData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-slate-500">
                No service correlations recorded yet
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={serviceChartData} layout="vertical" margin={{ left: 20, right: 20 }}>
                  <XAxis type="number" stroke="#64748b" fontSize={11} allowDecimals={false} />
                  <YAxis dataKey="name" type="category" stroke="#64748b" fontSize={11} width={100} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      borderRadius: '0.375rem',
                      fontSize: '0.75rem',
                    }}
                  />
                  <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </div>

      {/* Operational Modules: Recent Incidents & System Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Incidents (2 cols) */}
        <div className="lg:col-span-2">
          <Card
            title="Recent Critical Activity"
            subtitle="Most recently created or updated incident alerts"
            headerAction={
              <Link to="/incidents" className="text-xs text-indigo-400 hover:text-indigo-300 font-medium">
                View all ({totalIncidents})
              </Link>
            }
          >
            {incidents.length === 0 ? (
              <p className="text-xs text-slate-500 py-4 text-center">No active incidents</p>
            ) : (
              <div className="divide-y divide-slate-800/80">
                {incidents.slice(0, 5).map((inc) => (
                  <Link
                    key={inc.id}
                    to={`/incidents/${inc.id}`}
                    className="flex items-center justify-between py-3 px-2 rounded-md hover:bg-slate-800/40 transition group"
                  >
                    <div className="space-y-1 min-w-0 pr-4">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-slate-400 font-medium">{inc.id}</span>
                        <h4 className="text-xs font-medium text-slate-200 truncate group-hover:text-indigo-400 transition">
                          {inc.title}
                        </h4>
                      </div>
                      <div className="flex items-center gap-3 text-[11px] text-slate-500">
                        <span>{inc.service_name}</span>
                        <span>•</span>
                        <span>{inc.impacted_users.toLocaleString()} users affected</span>
                        <span>•</span>
                        <span>{new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Badge variant="severity" value={inc.severity} />
                      <Badge variant="status" value={inc.status} />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* System & Architecture Health (1 col) */}
        <div>
          <Card title="System Topology & Knowledge" subtitle="Persistent episodic memory & graph status">
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                <div className="flex items-center gap-3">
                  <Server className="w-4 h-4 text-indigo-400" />
                  <div>
                    <p className="text-xs font-medium text-slate-200">Cataloged Services</p>
                    <p className="text-[10px] text-slate-500">Total persistent microservices</p>
                  </div>
                </div>
                <span className="text-sm font-bold font-mono text-slate-100">
                  {services.length}
                </span>
              </div>

              <div className="flex items-center justify-between p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                <div className="flex items-center gap-3">
                  <BrainCircuit className="w-4 h-4 text-purple-400" />
                  <div>
                    <p className="text-xs font-medium text-slate-200">Episodic Memories</p>
                    <p className="text-[10px] text-slate-500">Verified historical outage runbooks</p>
                  </div>
                </div>
                <span className="text-sm font-bold font-mono text-purple-400">
                  {health?.indexed_memories ?? 0}
                </span>
              </div>

              <div className="flex items-center justify-between p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                <div className="flex items-center gap-3">
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                  <div>
                    <p className="text-xs font-medium text-slate-200">Engine Health</p>
                    <p className="text-[10px] text-slate-500">Backend API operational status</p>
                  </div>
                </div>
                <span className="text-xs font-semibold uppercase text-emerald-400">
                  {health?.status || 'HEALTHY'}
                </span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
