import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { X, History } from 'lucide-react';
import type { Test } from '../../types/board';;

interface TestHistoryModalProps {
  test: Test;
  onClose: () => void;
}

interface HistoryEntry {
  id: string;
  action: string;
  details: string;
  timestamp: string;
  user_name: string;
  week_number?: number;
  year?: number;
}

export default function TestHistoryModal({ test, onClose }: TestHistoryModalProps) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`/api/tests/${test.id}/history`)
      .then(res => setHistory(res.data))
      .catch(err => console.error("Failed to load history", err))
      .finally(() => setLoading(false));
  }, [test.id]);

  const formatDate = (dateString: string) => {
    if (!dateString) return "N/A";
    // Ensure the timestamp is treated as valid ISO by appending Z if no timezone is specified
    const safeDateStr = dateString.endsWith('Z') || dateString.includes('+') ? dateString : dateString + 'Z';
    const d = new Date(safeDateStr);
    if (isNaN(d.getTime())) return "Invalid Date";
    return d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-[1000] flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 w-full max-w-lg shadow-2xl animate-in zoom-in-95 max-h-[85vh] flex flex-col">

        <div className="flex justify-between items-start mb-6 border-b border-slate-100 dark:border-zinc-800 pb-4 shrink-0">
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
              <History size={20} className="text-blue-500" /> Lifecycle Timeline
            </h2>
            <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1 max-w-[350px] truncate">
              {test.name}
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto pr-2">
          {loading ? (
            <div className="py-12 text-center text-slate-500 dark:text-zinc-500">Loading history...</div>
          ) : history.length === 0 ? (
            <div className="py-12 text-center text-slate-400 dark:text-zinc-600 font-medium">No history recorded for this test.</div>
          ) : (
            <div className="relative border-l-2 border-slate-200 dark:border-zinc-800 ml-4 space-y-8 pb-4">
              {history.map((entry) => {
                const isError = entry.action.includes('UNABLE') || entry.action.includes('DELETED');
                const isSuccess = entry.action.includes('COMPLETED') || entry.action.includes('SCHEDULED');

                return (
                  <div key={entry.id} className="relative pl-6">
                    {/* Timeline Dot */}
                    <div className={`absolute -left-[9px] mt-1.5 w-4 h-4 rounded-full ring-4 ring-white dark:ring-zinc-900 ${isError ? 'bg-red-500' : isSuccess ? 'bg-emerald-500' : 'bg-blue-500'}`}></div>

                    <div className="bg-slate-50 dark:bg-zinc-950/50 border border-slate-200 dark:border-zinc-800 rounded-xl p-4 shadow-sm">
                      <div className="flex justify-between items-start mb-2">
                        <span className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider">
                          {formatDate(entry.timestamp)}
                        </span>
                      </div>

                      <div className="text-base font-bold text-slate-900 dark:text-zinc-100 mb-1">
                        {entry.action.replace(/_/g, ' ')}
                      </div>

                      <div className="text-sm text-slate-600 dark:text-zinc-400 leading-relaxed mb-3">
                        {entry.details || "Status changed."}
                      </div>

                      <div className="flex items-center justify-between border-t border-slate-200 dark:border-zinc-800/50 pt-3">
                        <div className="text-xs font-medium text-slate-500 dark:text-zinc-500">
                          By: <span className="text-slate-700 dark:text-zinc-300">{entry.user_name || 'System'}</span>
                        </div>

                        {entry.week_number && entry.year && (
                          <div className="text-[10px] font-bold text-indigo-700 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 px-2 py-1 rounded-md uppercase tracking-wider">
                            Target: Wk {entry.week_number} ({entry.year})
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}