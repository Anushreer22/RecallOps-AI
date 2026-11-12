import React from 'react';
import { IncidentSeverity, IncidentStatus, ServiceTier, UserRole } from '../../types';

interface BadgeProps {
  children?: React.ReactNode;
  variant?: 'severity' | 'status' | 'tier' | 'role' | 'neutral' | 'success' | 'warning' | 'danger' | 'purple' | 'blue';
  value?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ children, variant = 'neutral', value, size = 'md', className = '' }) => {
  const text = (children || value || '') as string;
  const upper = typeof text === 'string' ? text.toUpperCase() : '';

  let colorClasses = 'bg-surface-200 dark:bg-slate-800 text-surface-700 dark:text-slate-300 border-surface-300 dark:border-slate-700';

  if (variant === 'purple') {
    colorClasses = 'bg-purple-500/10 text-purple-600 dark:text-purple-300 border-purple-500/30';
  } else if (variant === 'blue') {
    colorClasses = 'bg-blue-500/10 text-blue-600 dark:text-blue-300 border-blue-500/30';
  } else if (variant === 'success') {
    colorClasses = 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-300 border-emerald-500/30';
  } else if (variant === 'warning') {
    colorClasses = 'bg-amber-500/10 text-amber-600 dark:text-amber-300 border-amber-500/30';
  } else if (variant === 'danger') {
    colorClasses = 'bg-rose-500/10 text-rose-600 dark:text-rose-300 border-rose-500/30';
  } else if (variant === 'severity' || upper in { CRITICAL: 1, HIGH: 1, MEDIUM: 1, LOW: 1 }) {
    switch (upper as IncidentSeverity) {
      case 'CRITICAL':
        colorClasses = 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/30';
        break;
      case 'HIGH':
        colorClasses = 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30';
        break;
      case 'MEDIUM':
        colorClasses = 'bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/30';
        break;
      case 'LOW':
        colorClasses = 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/30';
        break;
    }
  } else if (variant === 'status' || upper in { OPEN: 1, INVESTIGATING: 1, MITIGATED: 1, RESOLVED: 1 }) {
    switch (upper as IncidentStatus) {
      case 'OPEN':
        colorClasses = 'bg-rose-500/15 text-rose-600 dark:text-rose-300 border-rose-500/40 animate-pulse';
        break;
      case 'INVESTIGATING':
        colorClasses = 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-300 border-indigo-500/40';
        break;
      case 'MITIGATED':
        colorClasses = 'bg-cyan-500/15 text-cyan-600 dark:text-cyan-300 border-cyan-500/40';
        break;
      case 'RESOLVED':
        colorClasses = 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border-emerald-500/40';
        break;
    }
  } else if (variant === 'tier' || upper.startsWith('TIER_')) {
    switch (upper as ServiceTier) {
      case 'TIER_0':
        colorClasses = 'bg-purple-500/15 text-purple-600 dark:text-purple-300 border-purple-500/40 font-semibold';
        break;
      case 'TIER_1':
        colorClasses = 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-300 border-indigo-500/30';
        break;
      case 'TIER_2':
        colorClasses = 'bg-slate-500/10 text-slate-600 dark:text-slate-300 border-slate-500/30';
        break;
      case 'TIER_3':
        colorClasses = 'bg-zinc-200 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-400 border-zinc-300 dark:border-zinc-700';
        break;
    }
  } else if (variant === 'role' || upper in { ADMIN: 1, ENGINEER: 1, VIEWER: 1 }) {
    switch (upper as UserRole) {
      case 'ADMIN':
        colorClasses = 'bg-purple-500/15 text-purple-600 dark:text-purple-300 border-purple-500/40 font-semibold';
        break;
      case 'ENGINEER':
        colorClasses = 'bg-blue-500/15 text-blue-600 dark:text-blue-300 border-blue-500/40';
        break;
      case 'VIEWER':
        colorClasses = 'bg-slate-500/15 text-slate-600 dark:text-slate-300 border-slate-500/40';
        break;
    }
  }

  const sizeClasses = {
    sm: 'text-[10px] px-1.5 py-0.5 gap-1',
    md: 'text-xs px-2.5 py-1 gap-1.5',
    lg: 'text-sm px-3 py-1.5 gap-2',
  }[size];

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full border tracking-wide uppercase transition-colors ${sizeClasses} ${colorClasses} ${className}`}
    >
      {children || value}
    </span>
  );
};

export const SeverityBadge: React.FC<{ severity: IncidentSeverity }> = ({ severity }) => (
  <Badge variant="severity" value={severity} />
);

export const StatusBadge: React.FC<{ status: IncidentStatus }> = ({ status }) => (
  <Badge variant="status" value={status} />
);

export const TierBadge: React.FC<{ tier: ServiceTier }> = ({ tier }) => (
  <Badge variant="tier" value={tier} />
);

export const RoleBadge: React.FC<{ role: UserRole }> = ({ role }) => (
  <Badge variant="role" value={role} />
);
