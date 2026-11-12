import React from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ message, size = 'md', className = '' }) => {
  const sizeClass = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-10 h-10',
  }[size];

  return (
    <div className={`flex flex-col items-center justify-center p-6 text-center ${className}`}>
      <Loader2 className={`${sizeClass} animate-spin text-brand-500 mb-2`} />
      {message && <p className="text-xs text-surface-500 dark:text-surface-400 font-medium tracking-wide">{message}</p>}
    </div>
  );
};
