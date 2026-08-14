import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { X, History } from 'lucide-react';
import type { Test } from '../../types/board';

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
    <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-[1000] flex items-start sm:items-center justify-center p-2 sm:p-4 animate-in fade-in overflow-y-auto">
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 sm:p-6 w-[95%] sm:w-full max-w-lg shadow-2xl animate-in zoom-in-95 my-4 sm:my-8 max-h-[85vh] flex flex-col flex-shrink-0">

        <div className="flex justify-between items-start mb-4 sm:mb-6 border-b border-slate-100 dark:border-zinc-800 pb-4 shrink-0 gap-2">
          <div>
            <h2 className="text-base sm:text-lg font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
              <History size={18} className="text-blue-500 sm:w-5 sm:h-5" /> Lifecycle Timeline
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-zinc-400 mt-1 max-w-[250px] sm:max-w-[350px] truncate">
              {test.name}
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors p-1">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
          {loading ? (
            <div className="py-12 text-center text-sm text-slate-500 dark:text-zinc-500">Loading history...</div>
          ) : history.length === 0 ? (
            <div className="py-12 text-center text-sm text-slate-400 dark:text-zinc-600 font-medium">No history recorded for this test.</div>
          ) : (
            <div className="relative border-l-2 border-slate-200 dark:border-zinc-800 ml-3 sm:ml-4 space-y-6 sm:space-y-8 pb-4">
              {history.map((entry) => {
                const isError = entry.action.includes('UNABLE') || entry.action.includes('DELETED');
                const isSuccess = entry.action.includes('COMPLETED') || entry.action.includes('SCHEDULED');

                return (
                  <div key={entry.id} className="relative pl-5 sm:pl-6">
                    {/* Timeline Dot */}
                    <div className={`absolute -left-[9px] mt-1.5 w-4 h-4 rounded-full ring-4 ring-white dark:ring-zinc-900 ${isError ? 'bg-red-500' : isSuccess ? 'bg-emerald-500' : 'bg-blue-500'}`}></div>

                    <div className="bg-slate-50 dark:bg-zinc-950/50 border border-slate-200 dark:border-zinc-800 rounded-xl p-3 sm:p-4 shadow-sm">
                      <div className="flex justify-between items-start mb-1 sm:mb-2">
                        <span className="text-[10px] sm:text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider">
                          {formatDate(entry.timestamp)}
                        </span>
                      </div>

                      <div className="text-sm sm:text-base font-bold text-slate-900 dark:text-zinc-100 mb-1">
                        {entry.action.replace(/_/g, ' ')}
                      </div>

                      <div className="text-xs sm:text-sm text-slate-600 dark:text-zinc-400 leading-relaxed mb-3 break-words">
                        {entry.details || "Status changed."}
                      </div>

                      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between border-t border-slate-200 dark:border-zinc-800/50 pt-3 gap-2 sm:gap-0">
                        <div className="text-[11px] sm:text-xs font-medium text-slate-500 dark:text-zinc-500">
                          By: <span className="text-slate-700 dark:text-zinc-300">{entry.user_name || 'System'}</span>
                        </div>

                        {entry.week_number && entry.year && (
                          <div className="text-[9px] sm:text-[10px] font-bold text-indigo-700 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 px-2 py-1 rounded-md uppercase tracking-wider w-fit">
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