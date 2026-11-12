import React from 'react';
export { Select } from './Select';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  helperText,
  className = '',
  id,
  ...props
}) => {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className="w-full space-y-1.5">
      {label && (
        <label htmlFor={inputId} className="block text-xs font-medium text-surface-700 dark:text-slate-300">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`w-full px-3 py-2 text-sm bg-surface-50 dark:bg-slate-950/80 border rounded-md text-surface-900 dark:text-slate-100 placeholder-surface-400 dark:placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500 transition disabled:opacity-50 disabled:cursor-not-allowed ${
          error
            ? 'border-rose-500 focus:border-rose-500'
            : 'border-surface-300 dark:border-slate-800 focus:border-brand-500 hover:border-surface-400 dark:hover:border-slate-700'
        } ${className}`}
        {...props}
      />
      {error && <p className="text-xs text-rose-500 dark:text-rose-400 font-medium">{error}</p>}
      {!error && helperText && <p className="text-xs text-surface-500 dark:text-slate-500">{helperText}</p>}
    </div>
  );
};

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Textarea: React.FC<TextareaProps> = ({
  label,
  error,
  helperText,
  className = '',
  id,
  ...props
}) => {
  const areaId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className="w-full space-y-1.5">
      {label && (
        <label htmlFor={areaId} className="block text-xs font-medium text-surface-700 dark:text-slate-300">
          {label}
        </label>
      )}
      <textarea
        id={areaId}
        className={`w-full px-3 py-2 text-sm bg-surface-50 dark:bg-slate-950/80 border rounded-md text-surface-900 dark:text-slate-100 placeholder-surface-400 dark:placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500 transition disabled:opacity-50 disabled:cursor-not-allowed ${
          error
            ? 'border-rose-500 focus:border-rose-500'
            : 'border-surface-300 dark:border-slate-800 focus:border-brand-500 hover:border-surface-400 dark:hover:border-slate-700'
        } ${className}`}
        {...props}
      />
      {error && <p className="text-xs text-rose-500 dark:text-rose-400 font-medium">{error}</p>}
      {!error && helperText && <p className="text-xs text-surface-500 dark:text-slate-500">{helperText}</p>}
    </div>
  );
};
