import React, { useState, useEffect } from 'react';
import { X, KeyRound, ShieldAlert, Copy, CheckCircle2, Loader2, AlertTriangle, Info, XCircle } from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { generateRSAKeyPair } from '../../utils/cryptoUtils';
import { useAppContext } from '../../context/AppContext';

interface E2EEKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function E2EEKeyModal({ isOpen, onClose }: E2EEKeyModalProps) {
  const { currentUser } = useAppContext();
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedPrivateKey, setGeneratedPrivateKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // --- NEW: Status Tracking ---
  const [hasExistingKey, setHasExistingKey] = useState<boolean | null>(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState(false);

  // Fetch the user's current key status when the modal opens
  useEffect(() => {
    if (isOpen && currentUser) {
      setIsLoadingStatus(true);
      axios.get('/api/users/public-keys').then(res => {
        // Find the current user in the list we just updated!
        const me = res.data.find((u: any) => String(u.id) === String(currentUser.id));
        setHasExistingKey(me?.has_key || !!me?.public_key);
        setIsLoadingStatus(false);
      }).catch(() => {
        setIsLoadingStatus(false);
      });
    } else {
      // Reset state on close
      setGeneratedPrivateKey(null);
      setCopied(false);
      setHasExistingKey(null);
    }
  }, [isOpen, currentUser]);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      // 1. Browser generates the keys natively
      const { publicKey, privateKey } = await generateRSAKeyPair();

      // 2. Send ONLY the Public Key to the server
      await axios.post('/api/users/me/public-key', { public_key: publicKey });

      // 3. Display the Private Key to the user
      setGeneratedPrivateKey(privateKey);
      setHasExistingKey(true); // Update local status immediately
      toast.success("Key pair generated! Public key saved to your profile.");
    } catch (e) {
      toast.error("Failed to generate or save keys.");
    } finally {
      setIsGenerating(false);
    }
  };

  const copyToClipboard = () => {
    if (generatedPrivateKey) {
      navigator.clipboard.writeText(generatedPrivateKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast.success("Copied to clipboard!");
    }
  };

  return (
    <div className="fixed inset-0 z-[200] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>

        <div className="px-6 py-4 border-b border-slate-100 dark:border-zinc-800 flex justify-between items-center bg-slate-50/50 dark:bg-zinc-900/30">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded-lg">
              <KeyRound size={18} />
            </div>
            <h2 className="font-bold text-slate-900 dark:text-zinc-100">Zero-Knowledge Key Generator</h2>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 rounded-full transition-colors">
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-6">

          {/* --- NEW: Dynamic Status Banner --- */}
          {isLoadingStatus ? (
            <div className="bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-3 rounded-xl flex items-center gap-3 text-slate-500 text-sm animate-pulse">
              <Loader2 size={18} className="animate-spin" /> Checking key status...
            </div>
          ) : hasExistingKey === true && !generatedPrivateKey ? (
            <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-900/50 p-3 rounded-xl flex items-center gap-3 text-emerald-800 dark:text-emerald-300 text-sm font-bold shadow-sm">
              <CheckCircle2 size={18} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
              Status: Active Key Configured
            </div>
          ) : hasExistingKey === false && !generatedPrivateKey ? (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900/50 p-3 rounded-xl flex items-center gap-3 text-red-800 dark:text-red-300 text-sm font-bold shadow-sm">
              <XCircle size={18} className="text-red-600 dark:text-red-400 shrink-0" />
              Status: No Key Configured
            </div>
          ) : null}

          {!generatedPrivateKey ? (
            <>
              <div className="bg-indigo-50 dark:bg-indigo-900/10 border border-indigo-200 dark:border-indigo-900/30 p-4 rounded-xl flex items-start gap-3 text-indigo-800 dark:text-indigo-300 text-sm">
                <ShieldAlert size={24} className="shrink-0 mt-0.5" />
                <p>Generate your personal RSA-4096 cryptographic key pair. The <strong>Public Key</strong> will be saved to your profile so teammates can encrypt notes for you. The <strong>Private Key</strong> never leaves your browser.</p>
              </div>

              {/* Only show the warning if they already have a key they are about to overwrite! */}
              {hasExistingKey && (
                <div className="p-4 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-900/30 rounded-xl flex items-start gap-3 text-amber-800 dark:text-amber-300 text-xs">
                  <AlertTriangle size={18} className="shrink-0" />
                  <p><strong>Warning:</strong> Generating a new key pair overrides your existing public key. You will lose access to old notes encrypted with your previous key unless someone re-shares them with you.</p>
                </div>
              )}

              <button
                onClick={handleGenerate}
                disabled={isGenerating || isLoadingStatus}
                className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-bold text-sm rounded-xl shadow-md transition-colors flex items-center justify-center gap-2"
              >
                {isGenerating ? <Loader2 size={18} className="animate-spin" /> : <KeyRound size={18} />}
                {isGenerating ? "Computing Math (This takes a second)..." : hasExistingKey ? "Regenerate Keys (Overwrite)" : "Generate E2EE Key Pair"}
              </button>
            </>
          ) : (
            <div className="animate-in slide-in-from-bottom-4">
              <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-900/50 p-4 rounded-xl flex items-start gap-3 text-emerald-800 dark:text-emerald-300 text-sm mb-4 shadow-sm">
                <CheckCircle2 size={24} className="shrink-0 mt-0.5" />
                <div>
                  <strong className="block mb-1">Success! Your Keys are Ready.</strong>
                  Your Public Key is saved. <strong>You must save the Private Key below to your Password Manager right now.</strong> Once you close this window, it is gone forever.
                </div>
              </div>

              <div className="relative group">
                <textarea
                  readOnly
                  value={generatedPrivateKey}
                  className="w-full h-48 p-4 border border-slate-300 dark:border-zinc-700 rounded-xl bg-slate-50 dark:bg-zinc-950 font-mono text-[10px] sm:text-xs outline-none resize-none custom-scrollbar text-slate-800 dark:text-zinc-200 shadow-inner"
                />
                <button
                  onClick={copyToClipboard}
                  className="absolute top-3 right-3 p-2 bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 rounded-lg shadow-sm hover:bg-slate-50 dark:hover:bg-zinc-700 transition-colors text-slate-600 dark:text-zinc-300 flex items-center gap-2"
                >
                  {copied ? <CheckCircle2 size={16} className="text-emerald-500" /> : <Copy size={16} />}
                  <span className="text-xs font-bold">{copied ? "Copied!" : "Copy Key"}</span>
                </button>
              </div>

              <button
                onClick={onClose}
                className="mt-6 w-full py-3 bg-slate-800 hover:bg-slate-900 dark:bg-zinc-100 dark:hover:bg-white dark:text-slate-900 text-white font-bold text-sm rounded-xl transition-colors shadow-md"
              >
                I have saved my Private Key in my Password Manager
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}