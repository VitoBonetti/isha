import React, { useState, useEffect } from 'react';
import { X, Lock, Save, Trash2, KeyRound, Users } from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { useAppContext } from '../../context/AppContext';
import ConfirmModal from './ConfirmModal';
import {
  importPrivateKey, importPublicKey, generateAesKey,
  encryptNote, decryptNote, wrapKeyWithRSA, unwrapKeyWithRSA
} from '../../utils/cryptoUtils';

export default function SecureNoteModal({ test, onClose }: { test: any, onClose: () => void }) {
  const { currentUser } = useAppContext();

  // Note States
  const [note, setNote] = useState("");
  const [privateKeyInput, setPrivateKeyInput] = useState("");
  const [isLocked, setIsLocked] = useState(false);

  // Data States
  const [serverData, setServerData] = useState<any>(null);
  const [teamMembers, setTeamMembers] = useState<any[]>([]);
  const [selectedUsers, setSelectedUsers] = useState<string[]>([]);

  // UI States
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  useEffect(() => {
    // 1. Fetch the note from the server
    axios.get(`/api/tests/${test.id}/secret`).then(res => {
      if (res.data.exists) {
        setServerData(res.data);
        setSelectedUsers(res.data.shared_with || []);
        setIsLocked(true); // Must provide private key to unlock
      } else {
        // New note - select current user by default
        setSelectedUsers([currentUser?.id as string]);
      }
      setLoading(false);
    }).catch(() => {
      toast.error("Failed to fetch secure note details.");
      onClose();
    });

    // 2. Fetch team members who have public keys configured
    axios.get('/api/users/public-keys').then(res => {
      setTeamMembers(res.data);
    });
  }, [test.id, currentUser?.id, onClose]);

  const handleUnlock = async () => {
    if (!privateKeyInput.trim()) return toast.error("Please paste your RSA Private Key.");
    if (!serverData?.encrypted_key) return toast.error("You do not have cryptographic access to this note.");

    setLoading(true);
    try {
      // 1. Import the Private Key
      const rsaPrivKey = await importPrivateKey(privateKeyInput);

      // 2. Unwrap the AES DEK
      const aesKey = await unwrapKeyWithRSA(serverData.encrypted_key, rsaPrivKey);

      // 3. Decrypt the actual note
      const decryptedText = await decryptNote(serverData.encrypted_data, aesKey);

      setNote(decryptedText);
      setIsLocked(false);
      setPrivateKeyInput(""); // Clear private key from memory!
    } catch (e) {
      toast.error("Decryption failed. Ensure your Private Key is correct and in PKCS#8 format.");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (selectedUsers.length === 0) return toast.error("You must select at least one user to share this note with.");
    setSaving(true);

    try {
      if (!note.trim()) {
        await axios.delete(`/api/tests/${test.id}/secret`);
        toast.success("Secure note deleted!");
        onClose();
        return;
      }

      // 1. Generate a brand new AES-GCM Key (DEK)
      const aesKey = await generateAesKey();

      // 2. Encrypt the Note
      const encryptedData = await encryptNote(note, aesKey);

      // 3. Wrap the AES Key for each selected user
      const accessList = [];
      for (const userId of selectedUsers) {
        const user = teamMembers.find(u => String(u.id) === String(userId));
        if (user && user.public_key) {
          const rsaPubKey = await importPublicKey(user.public_key);
          const wrappedKey = await wrapKeyWithRSA(aesKey, rsaPubKey);
          accessList.push({ user_id: user.id, encrypted_key: wrappedKey });
        }
      }

      // 4. Send Ciphertext + Wrapped Keys to the blind backend
      await axios.put(`/api/tests/${test.id}/secret`, {
        encrypted_data: encryptedData,
        access_list: accessList
      });

      toast.success("Zero-Knowledge secure note encrypted and saved!");
      onClose();
    } catch (e) {
      toast.error("Failed to encrypt and save note.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      await axios.delete(`/api/tests/${test.id}/secret`);
      toast.success("Secure note permanently deleted!");
      setDeleteModalOpen(false);
      onClose();
    } catch (e) { toast.error("Failed to delete note."); }
  };

  const toggleUser = (userId: string) => {
    setSelectedUsers(prev => prev.includes(userId) ? prev.filter(id => id !== userId) : [...prev, userId]);
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-[1500] flex items-start sm:items-center justify-center p-2 sm:p-4 animate-in fade-in overflow-y-auto">
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 sm:p-6 w-[95%] sm:w-full max-w-4xl shadow-2xl flex flex-col sm:flex-row gap-6 my-4 sm:my-8 flex-shrink-0">

        {/* LEFT PANEL: The Note Content */}
        <div className="flex-1 flex flex-col">
          <div className="flex justify-between items-center mb-4 border-b border-slate-100 dark:border-zinc-800 pb-4">
            <h2 className="text-base sm:text-lg font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
              <Lock size={18} className="text-indigo-500 flex-shrink-0" />
              <span className="truncate">E2EE Vault: {test.name}</span>
            </h2>
            <button onClick={onClose} className="sm:hidden text-slate-400 hover:text-slate-900 transition-colors p-1"><X size={20} /></button>
          </div>

          {loading ? (
            <div className="py-12 flex justify-center items-center h-64"><div className="animate-spin h-6 w-6 border-2 border-indigo-500 border-t-transparent rounded-full"></div></div>
          ) : isLocked ? (
            <div className="flex flex-col h-64 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl p-4">
              <div className="flex items-center gap-2 text-amber-600 dark:text-amber-500 font-bold text-sm mb-3">
                <KeyRound size={16} /> Note is Encrypted
              </div>
              <p className="text-xs text-slate-500 mb-3">Paste your personal RSA Private Key to decrypt this note. The key never leaves your browser.</p>
              <textarea
                value={privateKeyInput}
                onChange={(e) => setPrivateKeyInput(e.target.value)}
                placeholder="-----BEGIN PRIVATE KEY-----&#10;..."
                className="flex-1 w-full p-3 border border-slate-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 font-mono text-[10px] sm:text-xs focus:ring-2 focus:ring-amber-500 outline-none resize-none custom-scrollbar"
              />
              <button onClick={handleUnlock} className="mt-3 w-full py-2.5 bg-amber-500 hover:bg-amber-600 text-white font-bold rounded-lg text-sm transition-colors">
                Decrypt Note locally
              </button>
            </div>
          ) : (
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Store credentials, backup codes, or temporary access URLs here..."
              className="w-full h-48 sm:h-64 p-3 sm:p-4 border border-slate-300 dark:border-zinc-700 rounded-lg bg-slate-50 dark:bg-zinc-950 font-mono text-xs sm:text-sm focus:ring-2 focus:ring-indigo-500 outline-none resize-none text-slate-900 dark:text-zinc-100 custom-scrollbar"
            />
          )}

          <div className="flex justify-between items-center mt-6 pt-4 border-t border-slate-100 dark:border-zinc-800">
            <button onClick={onClose} className="px-4 py-2 text-sm font-medium bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors">Close</button>
            {!isLocked && (
              <button onClick={handleSave} disabled={saving || loading} className="flex items-center gap-2 px-5 py-2 text-sm font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors shadow-sm">
                <Lock size={16}/> {saving ? 'Encrypting...' : 'Encrypt & Save'}
              </button>
            )}
          </div>
        </div>

        {/* RIGHT PANEL: Cryptographic Access Control */}
        {!isLocked && (
          <div className="w-full sm:w-64 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl p-4 flex flex-col">
            <h3 className="text-sm font-bold text-slate-800 dark:text-zinc-200 flex items-center gap-2 mb-3">
              <Users size={16} className="text-blue-500"/> Authorized Access
            </h3>
            <p className="text-[10px] text-slate-500 mb-3 leading-relaxed">
              Select who can decrypt this note. The AES key will be encrypted uniquely using each selected user's public key.
            </p>

            <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 max-h-64">
              {teamMembers.map(user => {
                const hasKey = !!user.public_key;

                return (
                  <label
                    key={user.id}
                    className={`flex items-center gap-2 p-2 rounded-lg transition-colors border ${hasKey ? 'hover:bg-slate-100 dark:hover:bg-zinc-900 cursor-pointer border-transparent hover:border-slate-200 dark:hover:border-zinc-800' : 'opacity-60 cursor-not-allowed border-transparent'}`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedUsers.includes(user.id)}
                      onChange={() => hasKey && toggleUser(user.id)}
                      disabled={!hasKey}
                      className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 disabled:bg-slate-200 dark:disabled:bg-zinc-800"
                    />
                    <div className="flex flex-col flex-1">
                      <div className="flex justify-between items-center w-full">
                        <span className="text-xs font-bold text-slate-700 dark:text-zinc-300">{user.name}</span>
                        {!hasKey && (
                          <span className="text-[9px] font-bold bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 px-1.5 py-0.5 rounded whitespace-nowrap">
                            Missing Key
                          </span>
                        )}
                      </div>
                      {String(user.id) === String(currentUser?.id) && (
                        <span className="text-[9px] text-indigo-500 font-bold mt-0.5">(You)</span>
                      )}
                    </div>
                  </label>
                );
              })}
            </div>

            {currentUser?.role === 'admin' && test.has_secret && (
              <button onClick={() => setDeleteModalOpen(true)} className="mt-4 w-full flex justify-center items-center gap-2 px-4 py-2 text-sm font-bold text-red-600 bg-white dark:bg-zinc-900 border border-red-200 dark:border-red-900/30 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-lg transition-colors">
                <Trash2 size={16}/> Wipe Vault
              </button>
            )}
          </div>
        )}

      </div>
      <ConfirmModal isOpen={deleteModalOpen} title="Wipe Secure Note" message="Are you sure you want to permanently delete this encrypted note? This cannot be undone." onConfirm={handleDelete} onCancel={() => setDeleteModalOpen(false)} />
    </div>
  );
}