import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Server, ShieldAlert } from 'lucide-react';
import { ServiceTier } from '../../types';

interface ServiceNodeData {
  label: string;
  tier?: ServiceTier | string;
  owner?: string;
  isOrigin?: boolean;
  isImpacted?: boolean;
  impactDepth?: number;
}

export const ServiceNode: React.FC<{ data: ServiceNodeData }> = memo(({ data }) => {
  const { label, tier, owner, isOrigin, isImpacted, impactDepth } = data;

  const getTierColor = (t?: string) => {
    switch (t?.toUpperCase()) {
      case 'TIER_1':
        return 'text-danger-500 bg-danger-500/10 border-danger-500/30';
      case 'TIER_2':
        return 'text-warning-500 bg-warning-500/10 border-warning-500/30';
      case 'TIER_3':
        return 'text-blue-500 bg-blue-500/10 border-blue-500/30';
      default:
        return 'text-surface-500 bg-surface-500/10 border-surface-500/30';
    }
  };

  let borderClass = 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-800';
  if (isOrigin) {
    borderClass = 'border-danger-500 dark:border-danger-500 ring-4 ring-danger-500/20 bg-danger-500/5 dark:bg-danger-950/20';
  } else if (isImpacted) {
    borderClass = 'border-warning-500 dark:border-warning-500 ring-2 ring-warning-500/20 bg-warning-500/5 dark:bg-warning-950/20';
  }

  return (
    <div
      className={`relative px-4 py-3 rounded-xl shadow-lg border transition-all min-w-[190px] ${borderClass}`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-surface-400 dark:!bg-surface-600 !w-2.5 !h-2.5 !border-2 !border-white dark:!border-surface-900"
      />

      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div
            className={`w-7 h-7 rounded-lg flex items-center justify-center ${
              isOrigin
                ? 'bg-danger-500 text-white'
                : isImpacted
                ? 'bg-warning-500 text-white'
                : 'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-300'
            }`}
          >
            {isOrigin || isImpacted ? (
              <ShieldAlert className="w-4 h-4" />
            ) : (
              <Server className="w-4 h-4" />
            )}
          </div>
          <div>
            <div className="font-semibold text-xs text-surface-900 dark:text-white truncate max-w-[120px]">
              {label}
            </div>
            {owner && (
              <div className="text-[10px] text-surface-500 dark:text-surface-400 truncate max-w-[120px]">
                {owner}
              </div>
            )}
          </div>
        </div>

        {tier && (
          <span
            className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold uppercase border ${getTierColor(
              tier
            )}`}
          >
            {tier.replace('TIER_', 'T')}
          </span>
        )}
      </div>

      {isOrigin && (
        <div className="mt-2 text-[10px] font-bold text-danger-500 uppercase tracking-wider flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-danger-500 animate-ping" />
          Root Origin
        </div>
      )}

      {isImpacted && !isOrigin && (
        <div className="mt-2 text-[10px] font-medium text-warning-500 flex items-center justify-between">
          <span>Downstream Blast</span>
          <span className="font-mono text-[9px] px-1 rounded bg-warning-500/20">
            Hop +{impactDepth || 1}
          </span>
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-surface-400 dark:!bg-surface-600 !w-2.5 !h-2.5 !border-2 !border-white dark:!border-surface-900"
      />
    </div>
  );
});

ServiceNode.displayName = 'ServiceNode';
