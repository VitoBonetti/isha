import React, { useState, useEffect } from 'react';
import { X, Key, Trash2, Plus, AlertCircle, Copy, BookOpen, Clock } from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';

export default function ApiKeysModal({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
  const [keys, setKeys] = useState<any[]>([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) fetchKeys();
  }, [isOpen]);

  const fetchKeys = async () => {
    try {
      const res = await axios.get('/api/auth/keys');
      setKeys(res.data);
    } catch (err) { toast.error("Failed to load API keys."); }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await axios.post('/api/auth/keys', { name: newKeyName });
      setGeneratedKey(res.data.raw_key);
      setNewKeyName("");
      fetchKeys();
      toast.success("API Key generated!");
      window.dispatchEvent(new CustomEvent('refresh_api_keys'));
    } catch (err) { toast.error("Failed to generate key."); }
  };

  const handleRevoke = async (id: string) => {
    try {
      await axios.delete(`/api/auth/keys/${id}`);
      toast.success("Key revoked.");
      fetchKeys();
      window.dispatchEvent(new CustomEvent('refresh_api_keys'));
    } catch (err) { toast.error("Failed to revoke key."); }
  };

  const copyToClipboard = () => {
    if (generatedKey) navigator.clipboard.writeText(generatedKey);
    toast.success("Copied to clipboard!");
  };

  // Helper functions for expiration logic
  const isExpired = (dateStr: string) => dateStr && new Date(dateStr) < new Date();
  const formatDate = (dateStr: string) => dateStr ? new Date(dateStr).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : 'Never';

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-[1000] flex items-start sm:items-center justify-center p-2 sm:p-4 animate-in fade-in overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 sm:p-6 w-[95%] sm:w-full max-w-2xl shadow-2xl flex flex-col my-4 sm:my-8 flex-shrink-0"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-4 sm:mb-6 border-b border-slate-100 dark:border-zinc-800 pb-4 shrink-0">
          <h2 className="text-lg sm:text-xl font-bold flex items-center gap-2 text-slate-900 dark:text-zinc-100">
            <Key size={20} className="text-blue-500" /> Developer API Keys
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors p-1">
            <X size={20} />
          </button>
        </div>

        {/* API Docs Callout */}
        <div className="mb-6 flex flex-col sm:flex-row items-start sm:items-center justify-between bg-slate-50 dark:bg-zinc-950/50 border border-slate-200 dark:border-zinc-800 p-4 rounded-xl gap-4 sm:gap-0 shrink-0">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-zinc-100 text-sm sm:text-base">API Documentation</h3>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-zinc-400 mt-1">View endpoints, schemas, and test queries directly from the browser.</p>
          </div>
          <a
            href="/api/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="flex w-full sm:w-auto justify-center items-center gap-2 px-4 py-2.5 sm:py-2 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/30 font-bold text-sm rounded-lg hover:bg-indigo-100 transition-colors"
          >
            <BookOpen size={16} /> Open Docs
          </a>
        </div>

        {generatedKey && (
          <div className="mb-6 p-4 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 rounded-xl shrink-0">
            <div className="flex items-start sm:items-center gap-2 text-emerald-800 dark:text-emerald-400 font-bold mb-3 text-sm">
              <AlertCircle size={16} className="shrink-0 mt-0.5 sm:mt-0" />
              Store this key safely! It will not be shown again.
            </div>
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
              <input type="text" readOnly value={generatedKey} className="w-full p-2.5 sm:p-2 bg-white dark:bg-zinc-950 border border-emerald-200 dark:border-emerald-500/30 rounded-lg font-mono text-xs sm:text-sm text-slate-700 dark:text-zinc-300 outline-none break-all" />
              <button onClick={copyToClipboard} className="p-2.5 sm:p-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors flex justify-center items-center gap-2 text-sm font-bold">
                <Copy size={16} /> <span className="sm:hidden">Copy Key</span>
              </button>
            </div>
            <button onClick={() => setGeneratedKey(null)} className="mt-3 text-xs sm:text-sm text-emerald-700 dark:text-emerald-500 font-bold hover:underline w-full sm:w-auto text-center sm:text-left">
              I have saved it, close this.
            </button>
          </div>
        )}

        <form onSubmit={handleCreate} className="flex flex-col sm:flex-row gap-3 mb-6 shrink-0">
          <input required type="text" placeholder="New Key Name (e.g. CI/CD Pipeline)" value={newKeyName} onChange={e => setNewKeyName(e.target.value)} className="flex-1 p-2.5 border border-slate-300 dark:border-zinc-700 rounded-lg bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
          <button type="submit" className="w-full sm:w-auto px-4 py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors flex justify-center items-center gap-2 text-sm"><Plus size={16}/> Generate Key</button>
        </form>

        <div className="flex-1 overflow-y-auto border border-slate-200 dark:border-zinc-800 rounded-xl bg-white dark:bg-zinc-900 custom-scrollbar">

          {/* DESKTOP TABLE */}
          <table className="hidden sm:table w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-zinc-800/50 border-b border-slate-200 dark:border-zinc-700">
              <tr>
                <th className="p-3 font-semibold text-slate-500">Name</th>
                <th className="p-3 font-semibold text-slate-500">Prefix</th>
                <th className="p-3 font-semibold text-slate-500">Expires</th>
                <th className="p-3 font-semibold text-slate-500 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
              {keys.map(k => {
                const expired = isExpired(k.expires_at);
                return (
                  <tr key={k.id} className={`transition-colors ${expired ? 'bg-slate-50 dark:bg-zinc-950/50 opacity-60' : 'hover:bg-slate-50 dark:hover:bg-zinc-800/30'}`}>
                    <td className={`p-3 font-bold ${expired ? 'text-slate-500 line-through decoration-slate-400' : 'text-slate-900 dark:text-zinc-100'}`}>
                      {k.key_name}
                    </td>
                    <td className="p-3 font-mono text-slate-500 dark:text-zinc-400 text-xs">{k.prefix}••••••••</td>
                    <td className="p-3">
                      {expired ? (
                        <span className="text-[10px] font-bold bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400 px-2 py-0.5 rounded uppercase tracking-wider">Expired</span>
                      ) : (
                        <span className="text-xs text-slate-500 dark:text-zinc-400 flex items-center gap-1">
                          <Clock size={12}/> {formatDate(k.expires_at)}
                        </span>
                      )}
                    </td>
                    <td className="p-3 text-right">
                      <button onClick={() => handleRevoke(k.id)} className="text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 p-1.5 rounded transition-colors" title="Revoke Key">
                        <Trash2 size={16}/>
                      </button>
                    </td>
                  </tr>
                );
              })}
              {keys.length === 0 && <tr><td colSpan={4} className="p-8 text-center text-slate-500">No API keys generated yet.</td></tr>}
            </tbody>
          </table>

          {/* MOBILE CARDS */}
          <div className="flex sm:hidden flex-col divide-y divide-slate-100 dark:divide-zinc-800">
             {keys.map(k => {
               const expired = isExpired(k.expires_at);
               return (
                  <div key={k.id} className={`p-4 flex flex-col gap-3 ${expired ? 'opacity-60 bg-slate-50 dark:bg-zinc-950/50' : ''}`}>
                     <div className="flex justify-between items-start gap-4">
                        <div className={`font-bold truncate text-sm ${expired ? 'text-slate-500 line-through' : 'text-slate-900 dark:text-zinc-100'}`}>
                          {k.key_name}
                        </div>
                        <button onClick={() => handleRevoke(k.id)} className="text-red-500 bg-red-50 dark:bg-red-900/30 p-2 rounded-lg shrink-0"><Trash2 size={16}/></button>
                     </div>
                     <div className="flex justify-between items-center">
                        <div className="font-mono text-slate-500 dark:text-zinc-400 text-xs bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded-lg w-fit">{k.prefix}••••••••</div>
                        {expired ? (
                          <span className="text-[10px] font-bold bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400 px-2 py-0.5 rounded uppercase tracking-wider">Expired</span>
                        ) : (
                          <span className="text-xs text-slate-500 dark:text-zinc-400">{formatDate(k.expires_at)}</span>
                        )}
                     </div>
                  </div>
               );
             })}
             {keys.length === 0 && <div className="p-8 text-center text-sm text-slate-500">No API keys generated yet.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}