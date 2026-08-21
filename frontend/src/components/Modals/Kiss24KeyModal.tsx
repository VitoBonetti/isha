import { useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { X, Key, ShieldCheck, Loader2 } from 'lucide-react';
import { useAppContext } from '../../context/AppContext';

interface Kiss24KeyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function Kiss24KeyModal({ isOpen, onClose }: Kiss24KeyModalProps) {
  const { currentUser, refreshUser } = useAppContext();
  const [apiKey, setApiKey] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  if (!isOpen) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return toast.error("API Key cannot be empty");

    setIsSaving(true);
    try {
      await axios.post('/api/users/me/kiss24-key', { api_key: apiKey.trim() });
      toast.success("API Key securely saved!");
      await refreshUser(); // Update the AppContext instantly
      setApiKey(''); // Clear the input
      onClose();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to save API Key");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[200] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>

        <div className="px-6 py-4 border-b border-slate-100 dark:border-zinc-800 flex justify-between items-center bg-slate-50/50 dark:bg-zinc-900/30">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-lg">
              <Key size={18} />
            </div>
            <h2 className="font-bold text-slate-900 dark:text-zinc-100">Keep Secure 24 API Key</h2>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 rounded-full transition-colors">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSave} className="p-6 space-y-6">
          <div className="bg-emerald-50 dark:bg-emerald-900/10 border border-emerald-200 dark:border-emerald-900/30 p-3 rounded-lg flex gap-3 text-emerald-800 dark:text-emerald-300 text-sm">
            <ShieldCheck size={20} className="shrink-0" />
            <p>Your API key is encrypted at rest using a Fernet cipher before being stored in the database. It is never exposed to the frontend.</p>
          </div>

          <div>
            <label className="block text-sm font-bold text-slate-700 dark:text-zinc-300 mb-1.5">
              {currentUser?.has_kiss24_key ? "Update API Key" : "Enter API Key"}
            </label>
            <input
              type="password"
              required
              placeholder="Paste your personal KISS24 token here..."
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              className="w-full p-3 border border-slate-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-900 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none transition-all font-mono text-sm"
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2.5 bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 font-bold text-sm rounded-xl transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={isSaving} className="flex-1 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-bold text-sm rounded-xl shadow-md transition-colors flex items-center justify-center gap-2">
              {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Key size={16} />}
              Save Key
            </button>
          </div>
        </form>

      </div>
    </div>
  );
}