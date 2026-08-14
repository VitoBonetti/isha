import React from 'react';
import { AlertTriangle, Info, Key } from 'lucide-react';

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'info' | 'secure';
}

export default function ConfirmModal({ isOpen, title, message, onConfirm, onCancel, confirmText = "Delete", cancelText = "Cancel", variant = 'danger' }: ConfirmModalProps) {
  if (!isOpen) return null;

  const styles = {
    danger: { bg: 'bg-red-600 hover:bg-red-700', text: 'text-red-600 dark:text-red-400', iconBg: 'bg-red-100 dark:bg-red-500/10 border-red-200 dark:border-red-500/20', Icon: AlertTriangle },
    warning: { bg: 'bg-amber-600 hover:bg-amber-700', text: 'text-amber-600 dark:text-amber-400', iconBg: 'bg-amber-100 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20', Icon: AlertTriangle },
    info: { bg: 'bg-blue-600 hover:bg-blue-700', text: 'text-blue-600 dark:text-blue-400', iconBg: 'bg-blue-100 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20', Icon: Info },
    secure: { bg: 'bg-indigo-600 hover:bg-indigo-700', text: 'text-indigo-600 dark:text-indigo-400', iconBg: 'bg-indigo-100 dark:bg-indigo-500/10 border-indigo-200 dark:border-indigo-500/20', Icon: Key }
  };

  const { bg, text, iconBg, Icon } = styles[variant];

  return (
    <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-[2000] flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 sm:p-6 w-[95%] sm:w-full max-w-sm shadow-2xl animate-in zoom-in-95">
        <div className="flex flex-col sm:flex-row items-center sm:items-start text-center sm:text-left gap-4">
          <div className={`${iconBg} ${text} p-3 rounded-full shrink-0 border`}>
            <Icon size={24} />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100">{title}</h3>
            <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1">{message}</p>
          </div>
        </div>
        <div className="flex flex-col sm:flex-row justify-end gap-3 mt-6">
          <button onClick={onConfirm} className={`w-full sm:w-auto px-4 py-2.5 sm:py-2 text-sm font-medium text-white rounded-lg shadow-sm transition-colors order-1 sm:order-2 flex justify-center items-center ${bg}`}>
            {confirmText}
          </button>
          <button onClick={onCancel} className="w-full sm:w-auto px-4 py-2.5 sm:py-2 text-sm font-medium bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors order-2 sm:order-1 flex justify-center items-center">
            {cancelText}
          </button>
        </div>
      </div>
    </div>
  );
}