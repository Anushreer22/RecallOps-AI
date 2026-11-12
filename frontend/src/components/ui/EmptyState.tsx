import React from 'react';
import { LucideIcon, Inbox } from 'lucide-react';
import { Button } from './Button';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon = Inbox,
  title,
  description,
  message,
  actionLabel,
  onAction,
  action,
  className = '',
}) => {
  const text = description || message;
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 text-center rounded-xl border border-dashed border-surface-200 dark:border-surface-800 bg-surface-50/50 dark:bg-surface-900/30 ${className}`}
    >
      <div className="p-3 mb-3 rounded-full bg-surface-100 dark:bg-surface-800/80 text-surface-400">
        <Icon className="w-6 h-6" />
      </div>
      <h3 className="text-sm font-semibold text-surface-800 dark:text-surface-200">{title}</h3>
      {text && <p className="max-w-sm mt-1 text-xs text-surface-500 dark:text-surface-400">{text}</p>}
      {action ? (
        <div className="mt-4">{action}</div>
      ) : actionLabel && onAction ? (
        <div className="mt-4">
          <Button size="sm" onClick={onAction}>
            {actionLabel}
          </Button>
        </div>
      ) : null}
    </div>
  );
};
