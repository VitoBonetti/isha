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
    <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-[1500] flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 w-full max-w-2xl shadow-2xl flex flex-col">
        <div className="flex justify-between items-center mb-4 border-b border-slate-100 dark:border-zinc-800 pb-4">
          <h2 className="text-lg font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Lock size={20} className="text-indigo-500" /> Secure Vault: {test.name}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 transition-colors"><X size={20} /></button>
        </div>

        {loading ? <div className="py-12 text-center text-slate-500">Decrypting...</div> : (
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Store credentials, backup codes, or temporary access URLs here..."
            className="w-full h-64 p-4 border border-slate-300 dark:border-zinc-700 rounded-lg bg-slate-50 dark:bg-zinc-950 font-mono text-sm focus:ring-2 focus:ring-indigo-500 outline-none resize-none text-slate-900 dark:text-zinc-100"
          />
        )}

        <div className="flex justify-between items-center mt-6 pt-4 border-t border-slate-100 dark:border-zinc-800">
          {currentUser?.role === 'admin' && test.has_secret ? (
            <button onClick={() => setDeleteModalOpen(true)} className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 rounded-lg transition-colors"><Trash2 size={16}/> Delete</button>
          ) : <div/>}
          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 text-sm font-medium bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors">Cancel</button>
            <button onClick={handleSave} disabled={saving || loading} className="flex items-center gap-2 px-5 py-2 text-sm font-medium bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors"><Save size={16}/> {saving ? 'Encrypting...' : 'Save & Encrypt'}</button>
          </div>
        </div>
      </div>
      <ConfirmModal isOpen={deleteModalOpen} title="Delete Secure Note" message="Are you sure you want to permanently delete this encrypted note?" onConfirm={handleDelete} onCancel={() => setDeleteModalOpen(false)} />
    </div>
  );
}