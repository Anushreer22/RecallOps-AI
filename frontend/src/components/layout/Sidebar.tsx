import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  AlertTriangle,
  BrainCircuit,
  Network,
  Server,
  Webhook,
  FolderKanban,
  ShieldCheck,
  Settings,
  ChevronLeft,
  ChevronRight,
  Radio,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Badge } from '../ui/Badge';

interface SidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isCollapsed, onToggleCollapse }) => {
  const { activeOrg, role } = useAuth();

  const navItems = [
    { label: 'Overview', path: '/', icon: LayoutDashboard },
    { label: 'Incidents', path: '/incidents', icon: AlertTriangle },
    { label: 'AI Investigations', path: '/investigations', icon: BrainCircuit },
    { label: 'Service Topology', path: '/topology', icon: Network },
    { label: 'Services', path: '/services', icon: Server },
    { label: 'Webhooks', path: '/webhooks', icon: Webhook },
    { label: 'Projects', path: '/projects', icon: FolderKanban },
    { label: 'Audit Logs', path: '/audit-logs', icon: ShieldCheck },
    { label: 'Settings', path: '/settings', icon: Settings },
  ];

  return (
    <aside
      className={`relative flex flex-col h-screen border-r border-slate-800 bg-[#090d16] text-slate-300 transition-all duration-200 select-none ${
        isCollapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-slate-800">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/40 text-indigo-400 shrink-0">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          {!isCollapsed && (
            <div className="truncate">
              <span className="text-sm font-bold tracking-tight text-slate-100 flex items-center gap-1.5">
                RecallOps<span className="text-indigo-400 font-mono text-xs font-semibold px-1 py-0.5 rounded bg-indigo-950/60 border border-indigo-800">AI</span>
              </span>
              <p className="text-[10px] text-slate-500 font-mono tracking-wider truncate">
                {activeOrg?.organization_name || 'Autonomous SRE'}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Nav List */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600/15 text-indigo-300 border border-indigo-500/30'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 border border-transparent'
                } ${isCollapsed ? 'justify-center px-0' : ''}`
              }
              title={isCollapsed ? item.label : undefined}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {!isCollapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Bottom Info & Collapse Button */}
      <div className="p-3 border-t border-slate-800 space-y-2">
        {!isCollapsed && role && (
          <div className="px-3 py-2 rounded-md bg-slate-900/60 border border-slate-800/80 flex items-center justify-between">
            <span className="text-[11px] text-slate-400">Current Scope</span>
            <Badge variant="role" value={role} />
          </div>
        )}
        <button
          onClick={onToggleCollapse}
          className="flex items-center justify-center w-full py-1.5 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 rounded transition border border-transparent"
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>
    </aside>
  );
};
