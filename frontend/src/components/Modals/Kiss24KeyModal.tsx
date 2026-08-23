import { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { X, Key, ShieldCheck, Loader2, CheckCircle, AlertTriangle, Info } from 'lucide-react';
import { useAppContext } from '../../context/AppContext';

interface Kiss24KeyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type KeyStatus = 'checking' | 'valid' | 'invalid' | 'none';

export default function Kiss24KeyModal({ isOpen, onClose }: Kiss24KeyModalProps) {
  const { currentUser, refreshUser } = useAppContext();
  const [apiKey, setApiKey] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // --- NEW: Live validation states ---
  const [keyStatus, setKeyStatus] = useState<KeyStatus>('none');
  const [statusMessage, setStatusMessage] = useState('');

  // --- NEW: Trigger validation when modal opens ---
  useEffect(() => {
    if (isOpen) {
      if (!currentUser?.has_kiss24_key) {
        setKeyStatus('none');
        setStatusMessage('No API Key configured.');
        return;
      }

      setKeyStatus('checking');
      axios.get('/api/users/me/kiss24-key/validate')
        .then(res => {
          if (res.data.is_valid) {
            setKeyStatus('valid');
            setStatusMessage('Your API Key is valid and active.');
          } else {
            setKeyStatus('invalid');
            setStatusMessage(res.data.message || 'Your API Key is invalid or expired.');
          }
        })
        .catch(err => {
          setKeyStatus('invalid');
          setStatusMessage('Failed to validate API Key.');
        });
    } else {
      // Reset state when closed
      setApiKey('');
      setKeyStatus('none');
      setStatusMessage('');
    }
  }, [isOpen, currentUser?.has_kiss24_key]);

  if (!isOpen) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return toast.error("API Key cannot be empty");

    setIsSaving(true);
    try {
      await axios.post('/api/users/me/kiss24-key', { api_key: apiKey.trim() });
      toast.success("API Key securely saved!");
      await refreshUser(); // Update the AppContext instantly

      // We don't close the modal immediately so the user sees the status flip to Valid!
      setApiKey('');

      // Re-trigger the validation check to confirm the new key works
      setKeyStatus('checking');
      const res = await axios.get('/api/users/me/kiss24-key/validate');
      if (res.data.is_valid) {
        setKeyStatus('valid');
        setStatusMessage('Your new API Key is valid and active.');
        setTimeout(() => onClose(), 1500); // Close automatically after 1.5s of seeing the green success
      } else {
        setKeyStatus('invalid');
        setStatusMessage(res.data.message || 'Keep Secure 24 rejected the new key.');
      }
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

          {/* --- NEW: Dynamic Status Banner --- */}
          {keyStatus === 'checking' && (
            <div className="bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-3 rounded-lg flex items-center gap-3 text-slate-700 dark:text-zinc-300 text-sm font-medium animate-pulse">
              <Loader2 size={18} className="animate-spin text-blue-500 shrink-0" />
              <p>Validating key with Keep Secure 24...</p>
            </div>
          )}

          {keyStatus === 'valid' && (
            <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-900/50 p-3 rounded-lg flex items-center gap-3 text-emerald-800 dark:text-emerald-300 text-sm font-medium">
              <CheckCircle size={18} className="text-emerald-500 shrink-0" />
              <p>{statusMessage}</p>
            </div>
          )}

          {keyStatus === 'invalid' && (
            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-900/50 p-3 rounded-lg flex items-start gap-3 text-amber-800 dark:text-amber-300 text-sm font-medium">
              <AlertTriangle size={18} className="text-amber-500 shrink-0 mt-0.5" />
              <p>{statusMessage}</p>
            </div>
          )}

          {keyStatus === 'none' && (
            <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-900/50 p-3 rounded-lg flex items-center gap-3 text-purple-800 dark:text-purple-300 text-sm font-medium">
              <Info size={18} className="text-purple-500 shrink-0" />
              <p>{statusMessage}</p>
            </div>
          )}

          <div className="bg-slate-50 dark:bg-zinc-900/50 border border-slate-200 dark:border-zinc-800 p-3 rounded-lg flex gap-3 text-slate-600 dark:text-zinc-400 text-sm">
            <ShieldCheck size={20} className="shrink-0 text-slate-400" />
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