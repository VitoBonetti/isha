import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import ConfirmModal from '../../components/Modals/ConfirmModal';
import { KeySquare, Trash2, ChevronsUpDown, ChevronUp, ChevronDown} from 'lucide-react';

export default function ApiKeysSettings() {
  const [globalApiKeys, setGlobalApiKeys] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [actionModal, setActionModal] = useState<{isOpen: boolean, title: string, message: string, confirmText: string, variant: 'danger'|'warning', onConfirm: () => void} | null>(null);

  // Pagination & Sorting
  const [apiKeyPage, setApiKeyPage] = useState(1);
  const ITEMS_PER_PAGE = 15;
  const [sortBy, setSortBy] = useState<string>('owner_name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const fetchGlobalKeys = async () => {
    setIsLoading(true);
    try {
      const res = await axios.get('/api/auth/keys?global_view=true');
      setGlobalApiKeys(res.data);
    } catch (err) {
      toast.error("Failed to load global API keys.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchGlobalKeys();
    const handleRefresh = () => fetchGlobalKeys();
    window.addEventListener('refresh_api_keys', handleRefresh);
    return () => window.removeEventListener('refresh_api_keys', handleRefresh);
  }, []);

  const handleSort = (column: string) => {
    if (sortBy === column) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortBy(column); setSortDir('asc'); }
  };

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return <ChevronsUpDown size={14} className="opacity-30 inline-block" />;
    return sortDir === 'asc' ? <ChevronUp size={14} className="text-emerald-500 inline-block" /> : <ChevronDown size={14} className="text-emerald-500 inline-block" />;
  };

  const handleRevokeGlobalKey = async (id: string) => {
    try {
      await axios.delete(`/api/auth/keys/${id}`);
      setGlobalApiKeys(prev => prev.filter(k => k.id !== id));
      toast.success("API Key permanently revoked.");
    } catch (err) { toast.error("Failed to revoke key."); }
  };

  const sortedApiKeys = [...globalApiKeys].sort((a, b) => {
    let res = 0;
    if (sortBy === 'owner_name') res = (a.owner_name || '').localeCompare(b.owner_name || '');
    else if (sortBy === 'key_name') res = (a.key_name || '').localeCompare(b.key_name || '');
    else if (sortBy === 'prefix') res = (a.prefix || '').localeCompare(b.prefix || '');
    return sortDir === 'asc' ? res : -res;
  });

  const paginatedApiKeys = sortedApiKeys.slice((apiKeyPage - 1) * ITEMS_PER_PAGE, apiKeyPage * ITEMS_PER_PAGE);

  if (isLoading) return <div className="p-8 text-center text-slate-500">Loading API keys...</div>;

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">
      <ConfirmModal
        isOpen={actionModal?.isOpen || false}
        title={actionModal?.title || ""}
        message={actionModal?.message || ""}
        confirmText={actionModal?.confirmText}
        variant={actionModal?.variant}
        onConfirm={() => { if(actionModal) actionModal.onConfirm(); setActionModal(null); }}
        onCancel={() => setActionModal(null)}
      />

      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <KeySquare size={22} className="text-blue-500" /> Global API Keys
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-0.5">
            Monitor and revoke active API keys across the entire platform.
          </p>
        </div>
      </div>

      <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col bg-white dark:bg-zinc-900">
        {/* DESKTOP TABLE */}
        <table className="hidden md:table w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-slate-50 dark:bg-zinc-950/50 border-b border-slate-200 dark:border-zinc-800 select-none">
            <tr>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('owner_name')}>
                Key Owner <SortIcon column="owner_name" />
              </th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('key_name')}>
                Key Name <SortIcon column="key_name" />
              </th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('prefix')}>
                Prefix <SortIcon column="prefix" />
              </th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
            {paginatedApiKeys.map(k => (
              <tr key={k.id} className="hover:bg-slate-50/50 dark:hover:bg-zinc-800/30 transition-colors">
                <td className="p-4">
                  <div className="font-bold text-slate-900 dark:text-zinc-100">{k.owner_name}</div>
                  <div className="text-xs text-slate-500">{k.owner_email}</div>
                </td>
                <td className="p-4 font-medium text-slate-700 dark:text-zinc-300">{k.key_name}</td>
                <td className="p-4 text-slate-500 dark:text-zinc-400 font-mono text-xs">{k.prefix}••••••••</td>
                <td className="p-4 text-right">
                  <button onClick={() => {
                     setActionModal({
                       isOpen: true, variant: 'danger', confirmText: "Revoke Key", title: "Revoke API Key",
                       message: `Are you sure you want to revoke the key "${k.key_name}" owned by ${k.owner_name}? Any scripts using this key will immediately fail.`,
                       onConfirm: () => handleRevokeGlobalKey(k.id)
                     });
                  }} className="text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 p-2 rounded-xl transition-colors" title="Revoke Key">
                    <Trash2 size={18} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* MOBILE CARDS */}
        <div className="flex md:hidden flex-col divide-y divide-slate-100 dark:divide-zinc-800">
          {paginatedApiKeys.map(k => (
            <div key={k.id} className="p-4 flex flex-col gap-3">
              <div className="flex justify-between items-start gap-4">
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-base text-slate-900 dark:text-zinc-100 truncate">{k.owner_name}</div>
                  <div className="text-xs text-slate-500 dark:text-zinc-400 truncate">{k.owner_email}</div>
                </div>
                <button onClick={() => {
                    setActionModal({
                      isOpen: true, variant: 'danger', confirmText: "Revoke Key", title: "Revoke API Key",
                      message: `Are you sure you want to revoke the key "${k.key_name}" owned by ${k.owner_name}? Any scripts using this key will immediately fail.`,
                      onConfirm: () => handleRevokeGlobalKey(k.id)
                    });
                }} className="text-red-500 bg-red-50 dark:bg-red-900/20 p-2.5 rounded-lg shrink-0">
                  <Trash2 size={16} />
                </button>
              </div>
              <div className="flex justify-between items-center bg-slate-50 dark:bg-zinc-950/50 p-2.5 rounded-xl border border-slate-100 dark:border-zinc-800 mt-1">
                <span className="font-medium text-slate-700 dark:text-zinc-300 text-sm truncate pr-2">{k.key_name}</span>
                <span className="font-mono text-[10px] text-slate-500 dark:text-zinc-400 bg-white dark:bg-zinc-900 px-1.5 py-0.5 rounded border border-slate-200 dark:border-zinc-700 shrink-0">{k.prefix}••••</span>
              </div>
            </div>
          ))}
        </div>

        {globalApiKeys.length === 0 && <div className="p-12 text-center text-sm text-slate-500 dark:text-zinc-500">No API keys are currently active.</div>}

        {/* PAGINATION FOOTER */}
        {globalApiKeys.length > 0 && (
          <div className="px-4 py-3.5 border-t border-slate-200 dark:border-zinc-800 flex flex-col sm:flex-row justify-between items-center gap-3 bg-slate-50/50 dark:bg-zinc-950/50 text-xs font-medium">
            <span className="text-slate-500">
              Page <strong className="text-slate-800 dark:text-zinc-200">{apiKeyPage}</strong> of <strong className="text-slate-800 dark:text-zinc-200">{Math.ceil(globalApiKeys.length / ITEMS_PER_PAGE) || 1}</strong>
            </span>
            <div className="flex gap-2 w-full sm:w-auto">
              <button onClick={() => setApiKeyPage(p => Math.max(1, p - 1))} disabled={apiKeyPage === 1} className="flex-1 sm:flex-none px-4 py-1.5 border border-slate-200 dark:border-zinc-800 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors bg-white dark:bg-zinc-900">Prev</button>
              <button onClick={() => setApiKeyPage(p => p + 1)} disabled={apiKeyPage >= Math.ceil(globalApiKeys.length / ITEMS_PER_PAGE)} className="flex-1 sm:flex-none px-4 py-1.5 border border-slate-200 dark:border-zinc-800 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors bg-white dark:bg-zinc-900">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}