import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import ConfirmModal from '../../components/Modals/ConfirmModal';
import { Terminal, Download, Trash2 } from 'lucide-react';
import { useSettings } from '../../hooks/useSettings';

export default function SystemLogsSettings() {
  const { handleDelete } = useSettings();
  const [bqLogs, setBqLogs] = useState<any[]>([]);
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; endpoint: string; id: string; name: string } | null>(null);

  const fetchLogs = () => {
    axios.get('/api/system/logs/')
      .then(res => setBqLogs(res.data))
      .catch(console.error);
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const confirmDelete = (endpoint: string, id: string, name: string) => setDeleteModal({ isOpen: true, endpoint, id, name });

  const executeDelete = async () => {
    if (deleteModal) {
      await handleDelete(deleteModal.endpoint, deleteModal.id);
      setDeleteModal(null);
      fetchLogs();
    }
  };

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200 flex flex-col h-full">
      <ConfirmModal
        isOpen={!!deleteModal}
        title="Confirm Deletion"
        message={`Are you sure you want to delete ${deleteModal?.name}? This action cannot be undone.`}
        onConfirm={executeDelete}
        onCancel={() => setDeleteModal(null)}
      />

      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Terminal size={22} className="text-slate-500 dark:text-zinc-400" /> Audit Logs
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-0.5">
            Monitor background workers, webhooks, and administrative actions.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
          <a href="/api/system/logs/download/csv" target="_blank" rel="noopener noreferrer" className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 hover:bg-slate-50 dark:hover:bg-zinc-800 text-slate-700 dark:text-zinc-300 px-4 py-2.5 sm:py-2 rounded-xl flex justify-center items-center gap-2 text-sm font-bold shadow-sm transition-colors">
            <Download size={16} /> Download Logs
          </a>
          <button onClick={() => confirmDelete('/api/system/logs/clear', '', 'All Audit Logs')} className="text-red-600 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/40 px-4 py-2.5 sm:py-2 rounded-xl flex justify-center items-center gap-2 text-sm font-bold shadow-sm transition-colors">
            <Trash2 size={16} /> Delete all Logs
          </button>
        </div>
      </div>

      {/* Fully Scrollable Terminal Container (Expanded Height) */}
      <div className="bg-[#0c0c0e] rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden flex flex-col min-h-[600px] w-full max-w-full">
        {/* Terminal Header */}
        <div className="bg-slate-800 px-3 md:px-4 py-3 flex items-center gap-2 shrink-0">
          <div className="w-3 h-3 rounded-full bg-red-500 shrink-0"></div>
          <div className="w-3 h-3 rounded-full bg-amber-500 shrink-0"></div>
          <div className="w-3 h-3 rounded-full bg-emerald-500 shrink-0"></div>
          <span className="ml-2 text-[11px] font-mono text-slate-400 font-medium tracking-wider">mario_platform.audit_logs</span>
        </div>

        {/* Terminal Body */}
        <div className="p-4 overflow-auto custom-scrollbar font-mono text-[11px] text-slate-300 flex-1 w-full relative">
          <div className="w-max min-w-full space-y-2">
            {(!bqLogs || bqLogs.length === 0) ? (
                <div className="text-slate-600 italic font-sans p-4 text-center">No logs found in the database.</div>
            ) : (
              bqLogs.map((log: any, idx: number) => (
                <div key={idx} className="flex gap-3 hover:bg-white/5 p-1 rounded transition-colors whitespace-nowrap">
                  <span className="text-emerald-400 shrink-0">[{new Date(log.timestamp).toLocaleString()}]</span>
                  <span className="text-blue-400 shrink-0 font-bold">[{log.action}]</span>
                  <span className="text-slate-300 pr-4">{log.details}</span>
                  <span className="text-slate-500 ml-auto shrink-0 pl-4 border-l border-slate-800">User: {log.user_id?.split('-')[0]}... ({log.role})</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}