import React, { useState, useEffect } from 'react';
import { X, Lock, Save, Trash2 } from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { useAppContext } from '../../context/AppContext';
import ConfirmModal from './ConfirmModal';

export default function SecureNoteModal({ test, onClose }: { test: any, onClose: () => void }) {
  const { currentUser } = useAppContext();
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  useEffect(() => {
    axios.get(`/api/tests/${test.id}/secret`).then(res => {
      setNote(res.data.note || "");
      setLoading(false);
    }).catch(() => {
      toast.error("Failed to decrypt secure note.");
      onClose();
    });
  }, [test.id]);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (!note.trim()) {
        await axios.delete(`/api/tests/${test.id}/secret`);
      } else {
        await axios.put(`/api/tests/${test.id}/secret`, { note });
      }
      toast.success("Secure note saved!");
      onClose();
    } catch (e) { toast.error("Failed to save secure note."); }
    setSaving(false);
  };

  const handleDelete = async () => {
    try {
      await axios.delete(`/api/tests/${test.id}/secret`);
      toast.success("Secure note deleted!");
      setDeleteModalOpen(false);
      onClose();
    } catch (e) { toast.error("Failed to delete note."); }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-[1500] flex items-start sm:items-center justify-center p-2 sm:p-4 animate-in fade-in overflow-y-auto">
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 sm:p-6 w-[95%] sm:w-full max-w-2xl shadow-2xl flex flex-col my-4 sm:my-8 flex-shrink-0">
        <div className="flex justify-between items-center mb-4 border-b border-slate-100 dark:border-zinc-800 pb-4">
          <h2 className="text-base sm:text-lg font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Lock size={18} className="text-indigo-500 flex-shrink-0" />
            <span className="truncate">Secure Vault: {test.name}</span>
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors p-1"><X size={20} /></button>
        </div>

        {loading ? <div className="py-12 text-center text-sm text-slate-500">Decrypting...</div> : (
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Store credentials, backup codes, or temporary access URLs here..."
            className="w-full h-48 sm:h-64 p-3 sm:p-4 border border-slate-300 dark:border-zinc-700 rounded-lg bg-slate-50 dark:bg-zinc-950 font-mono text-xs sm:text-sm focus:ring-2 focus:ring-indigo-500 outline-none resize-none text-slate-900 dark:text-zinc-100 custom-scrollbar"
          />
        )}

        <div className="flex flex-col sm:flex-row justify-between items-stretch sm:items-center mt-4 sm:mt-6 pt-4 border-t border-slate-100 dark:border-zinc-800 gap-3 sm:gap-0">

          <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto order-1 sm:order-2">
            <button onClick={handleSave} disabled={saving || loading} className="w-full sm:w-auto flex justify-center items-center gap-2 px-5 py-2.5 sm:py-2 text-sm font-medium bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors order-1 sm:order-2"><Save size={16}/> {saving ? 'Encrypting...' : 'Save & Encrypt'}</button>
            <button onClick={onClose} className="w-full sm:w-auto flex justify-center px-4 py-2.5 sm:py-2 text-sm font-medium bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors order-2 sm:order-1">Cancel</button>
          </div>

          {currentUser?.role === 'admin' && test.has_secret ? (
            <button onClick={() => setDeleteModalOpen(true)} className="w-full sm:w-auto flex justify-center items-center gap-2 px-4 py-2.5 sm:py-2 text-sm font-bold text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-lg transition-colors order-3 sm:order-1 border border-red-100 dark:border-red-900/30 sm:border-transparent"><Trash2 size={16}/> Delete</button>
          ) : <div className="hidden sm:block" />}
        </div>
      </div>
      <ConfirmModal isOpen={deleteModalOpen} title="Delete Secure Note" message="Are you sure you want to permanently delete this encrypted note?" onConfirm={handleDelete} onCancel={() => setDeleteModalOpen(false)} />
    </div>
  );
}