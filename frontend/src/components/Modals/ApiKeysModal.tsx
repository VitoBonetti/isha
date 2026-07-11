import React, { useState, useEffect } from 'react';
import { X, Key, Trash2, Plus, AlertCircle, Copy, BookOpen } from 'lucide-react';
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
      window.dispatchEvent(new CustomEvent('refresh_api_keys')); // <-- ADD THIS
    } catch (err) { toast.error("Failed to generate key."); }
  };

  const handleRevoke = async (id: string) => {
    try {
      await axios.delete(`/api/auth/keys/${id}`);
      toast.success("Key revoked.");
      fetchKeys();
      window.dispatchEvent(new CustomEvent('refresh_api_keys')); // <-- ADD THIS
    } catch (err) { toast.error("Failed to revoke key."); }
  };

  const copyToClipboard = () => {
    if (generatedKey) navigator.clipboard.writeText(generatedKey);
    toast.success("Copied to clipboard!");
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-[1000] flex items-center justify-center p-4 animate-in fade-in"
      onClick={onClose} // <-- Click backdrop to close
    >
      <div
        className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 w-full max-w-2xl shadow-2xl flex flex-col max-h-[85vh]"
        onClick={e => e.stopPropagation()} // <-- Prevent backdrop click from closing when clicking inside modal
      >
        <div className="flex justify-between items-center mb-6 border-b border-slate-100 dark:border-zinc-800 pb-4">
          <h2 className="text-xl font-bold flex items-center gap-2 text-slate-900 dark:text-zinc-100">
            <Key size={20} className="text-blue-500" /> Developer API Keys
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* API Docs Callout */}
        <div className="mb-6 flex items-center justify-between bg-slate-50 dark:bg-zinc-950/50 border border-slate-200 dark:border-zinc-800 p-4 rounded-xl">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-zinc-100">API Documentation</h3>
            <p className="text-sm text-slate-500 dark:text-zinc-400">View endpoints, schemas, and test queries directly from the browser.</p>
          </div>
          <a
            href="/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/30 font-bold text-sm rounded-lg hover:bg-indigo-100 transition-colors"
          >
            <BookOpen size={16} /> Open Docs
          </a>
        </div>

        {generatedKey && (
          <div className="mb-6 p-4 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 rounded-xl">
            <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-400 font-bold mb-2"><AlertCircle size={16} /> Store this key safely! It will not be shown again.</div>
            <div className="flex items-center gap-2">
              <input type="text" readOnly value={generatedKey} className="w-full p-2 bg-white dark:bg-zinc-950 border border-emerald-200 dark:border-emerald-500/30 rounded-lg font-mono text-sm text-slate-700 dark:text-zinc-300 outline-none" />
              <button onClick={copyToClipboard} className="p-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"><Copy size={16} /></button>
            </div>
            <button onClick={() => setGeneratedKey(null)} className="mt-3 text-sm text-emerald-700 dark:text-emerald-500 font-bold hover:underline">I have saved it, close this.</button>
          </div>
        )}

        <form onSubmit={handleCreate} className="flex gap-3 mb-6">
          <input required type="text" placeholder="New Key Name (e.g. CI/CD Pipeline)" value={newKeyName} onChange={e => setNewKeyName(e.target.value)} className="flex-1 p-2.5 border border-slate-300 dark:border-zinc-700 rounded-lg bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
          <button type="submit" className="px-4 py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 text-sm"><Plus size={16}/> Generate Key</button>
        </form>

        <div className="flex-1 overflow-y-auto border border-slate-200 dark:border-zinc-800 rounded-xl">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-zinc-800/50 border-b border-slate-200 dark:border-zinc-700">
              <tr>
                <th className="p-3 font-semibold text-slate-500">Name</th>
                <th className="p-3 font-semibold text-slate-500">Prefix</th>
                <th className="p-3 font-semibold text-slate-500 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
              {keys.map(k => (
                <tr key={k.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors">
                  <td className="p-3 font-bold text-slate-900 dark:text-zinc-100">{k.key_name}</td>
                  <td className="p-3 font-mono text-slate-500 dark:text-zinc-400 text-xs">{k.prefix}••••••••</td>
                  <td className="p-3 text-right"><button onClick={() => handleRevoke(k.id)} className="text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 p-1.5 rounded transition-colors"><Trash2 size={16}/></button></td>
                </tr>
              ))}
              {keys.length === 0 && <tr><td colSpan={3} className="p-8 text-center text-slate-500">No API keys generated yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}