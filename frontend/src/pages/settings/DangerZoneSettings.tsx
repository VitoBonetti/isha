import React, { useState } from 'react';
import axios from 'axios';
import toast, { Toaster } from 'react-hot-toast';
import { AlertTriangle } from 'lucide-react';
import { useSettings } from '../../hooks/useSettings';
import ConfirmModal from '../../components/Modals/ConfirmModal';

export default function DangerZoneSettings() {
  const { handleWipeSystem } = useSettings();

  const [nukeModalOpen, setNukeModalOpen] = useState(false);
  const [nukeText, setNukeText] = useState("");
  const [actionModal, setActionModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    confirmText: string;
    variant: 'danger' | 'warning';
    onConfirm: () => void;
  } | null>(null);

  const inputClasses = "w-full mt-1.5 p-2.5 border border-slate-200 dark:border-zinc-800 rounded-xl bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none text-sm transition-colors";

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">
      <Toaster position="bottom-right" />
      <ConfirmModal
        isOpen={actionModal?.isOpen || false}
        title={actionModal?.title || ""}
        message={actionModal?.message || ""}
        confirmText={actionModal?.confirmText}
        variant={actionModal?.variant}
        onConfirm={() => { if (actionModal) actionModal.onConfirm(); setActionModal(null); }}
        onCancel={() => setActionModal(null)}
      />

      {/* Nuke Modal */}
      {nukeModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-50 flex items-start sm:items-center justify-center p-4 animate-in fade-in overflow-y-auto">
          <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-3xl p-6 md:p-8 w-[95%] sm:w-full max-w-md shadow-2xl animate-in zoom-in-95 my-8 sm:my-0 flex-shrink-0">
            <div className="flex flex-col sm:flex-row items-center sm:items-start gap-4 text-center sm:text-left">
              <div className="bg-red-100 dark:bg-red-500/10 text-red-600 dark:text-red-500 p-4 rounded-full shrink-0 border border-red-200 dark:border-red-500/20">
                <AlertTriangle size={32} />
              </div>
              <div>
                <h3 className="text-xl font-bold text-slate-900 dark:text-zinc-100">Factory Reset</h3>
                <p className="text-sm text-slate-500 dark:text-zinc-400 mt-2">
                  This will permanently delete all tests, assets, events, and assignments. Configurations and users will be kept.
                </p>
              </div>
            </div>
            <div className="mt-8">
              <label className="block text-sm font-bold text-slate-700 dark:text-zinc-300 mb-2 text-center sm:text-left">
                Type <strong className="text-red-500 select-all">NUKE</strong> to confirm:
              </label>
              <input
                type="text"
                className={inputClasses}
                value={nukeText}
                onChange={(e) => setNukeText(e.target.value)}
                placeholder="NUKE"
              />
            </div>
            <div className="flex flex-col sm:flex-row justify-end gap-3 mt-8">
              <button
                onClick={() => { setNukeModalOpen(false); setNukeText(""); }}
                className="w-full sm:w-auto px-5 py-3 sm:py-2.5 text-sm font-bold bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-xl transition-colors order-2 sm:order-1 flex justify-center items-center"
              >
                Cancel
              </button>
              <button
                onClick={() => { if (nukeText === 'NUKE') { handleWipeSystem(); setNukeModalOpen(false); setNukeText(""); } }}
                disabled={nukeText !== 'NUKE'}
                className="w-full sm:w-auto px-5 py-3 sm:py-2.5 text-sm font-bold bg-red-600 hover:bg-red-700 disabled:bg-slate-200 dark:disabled:bg-zinc-800 disabled:text-slate-400 text-white rounded-xl shadow-sm transition-colors order-1 sm:order-2 flex justify-center items-center"
              >
                Execute Reset
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="mb-8">
        <h1 className="text-xl font-bold text-red-600 dark:text-red-500 flex items-center gap-2">
          <AlertTriangle size={22} /> Danger Zone
        </h1>
        <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1 max-w-3xl">
          Destructive actions that cannot be undone. Proceed with absolute caution.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 w-full">

        {/* Card 1: Unlink Drive Folders */}
        <div className="bg-white dark:bg-zinc-900 border border-red-200 dark:border-red-900/50 p-6 rounded-3xl shadow-sm flex flex-col justify-between h-full">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-zinc-100 text-base">Unlink Drive Folders</h3>
            <p className="text-sm text-slate-500 dark:text-zinc-400 mt-2">
              Removes the Google Drive folder links from all tests and wipes their synchronized document metadata including LLM Vulnerabilities Analysis. Physical files in Google Drive are NOT deleted.
            </p>
          </div>
          <button
            onClick={() => {
              setActionModal({
                isOpen: true, variant: 'danger', confirmText: "Unlink Folders", title: "Unlink All Drive Folders",
                message: "Are you sure you want to unlink all Google Drive folders and wipe the document cache? Links will have to be manually re-established for each test.",
                onConfirm: async () => {
                  try {
                    await axios.delete('/api/danger/tests/wipe-google-drive-workspace');
                    toast.success("Drive folders unlinked and documents wiped.");
                  } catch (err) { toast.error("Failed to wipe drive folders."); }
                }
              });
            }}
            className="w-full mt-6 bg-red-500 hover:bg-red-600 text-white font-bold py-2.5 px-4 rounded-xl shadow-sm transition-colors text-sm"
          >
            Unlink Folders
          </button>
        </div>

        {/* Card 2: Wipe Synced Documents */}
        <div className="bg-white dark:bg-zinc-900 border border-red-200 dark:border-red-900/50 p-6 rounded-3xl shadow-sm flex flex-col justify-between h-full">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-zinc-100 text-base">Wipe Synced Documents</h3>
            <p className="text-sm text-slate-500 dark:text-zinc-400 mt-2">
              Wipes the cached Google Drive file records from the database. Parent folder links are preserved. You will need to click "Resync Files" on active tests to rebuild the cache.
            </p>
          </div>
          <button
            onClick={() => {
              setActionModal({
                isOpen: true, variant: 'warning', confirmText: "Wipe Documents", title: "Wipe Synced Documents",
                message: "Are you sure you want to empty the synchronized document cache? This action is safe, but requires manual resyncs on active tests.",
                onConfirm: async () => {
                  try {
                    await axios.delete('/api/danger/tests/wipe-documents');
                    toast.success("Document cache wiped.");
                  } catch (err) { toast.error("Failed to wipe document cache."); }
                }
              });
            }}
            className="w-full mt-6 bg-orange-500 hover:bg-orange-600 text-white font-bold py-2.5 px-4 rounded-xl shadow-sm transition-colors text-sm"
          >
            Wipe Documents
          </button>
        </div>

        {/* Card 3: Wipe Rag Chat Logs */}
        <div className="bg-white dark:bg-zinc-900 border border-red-200 dark:border-red-900/50 p-6 rounded-3xl shadow-sm flex flex-col justify-between h-full">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-zinc-100 text-base">Wipe Rag Chat Logs</h3>
            <p className="text-sm text-slate-500 dark:text-zinc-400 mt-2">
              Wipes the Rag Chat Logs records from the database. All the logs will be permanently deleted. It will be impossible recover any session.
            </p>
          </div>
          <button
            onClick={() => {
              setActionModal({
                isOpen: true, variant: 'warning', confirmText: "Wipe Rag Chat Logs", title: "Wipe Rag Chat Logs",
                message: "Are you sure you want to delete the Rag Chat Logs? This action cannot be reversed.",
                onConfirm: async () => {
                  try {
                    await axios.delete('/api/danger/tests/wipe-rag-chat-logs');
                    toast.success("Rag Chat Logs wiped.");
                  } catch (err) { toast.error("Failed to wipe Rag Chat Logs."); }
                }
              });
            }}
            className="w-full mt-6 bg-orange-500 hover:bg-orange-600 text-white font-bold py-2.5 px-4 rounded-xl shadow-sm transition-colors text-sm"
          >
            Wipe Rag Chat Logs
          </button>
        </div>

        {/* Card 4: Wipe All Vulnerability Analysis */}
        <div className="bg-white dark:bg-zinc-900 border border-red-200 dark:border-red-900/50 p-6 rounded-3xl shadow-sm flex flex-col justify-between h-full">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-zinc-100 text-base">Wipe Vulnerability Analysis</h3>
            <p className="text-sm text-slate-500 dark:text-zinc-400 mt-2">
              Wipes permanently the Vulnerability Analysis records from the database.
            </p>
          </div>
          <button
            onClick={() => {
              setActionModal({
                isOpen: true, variant: 'warning', confirmText: "Wipe Vulnerability Analysis", title: "Wipe Vulnerability Analysis",
                message: "Are you sure you want to delete the Vulnerability Analysis? This action cannot be reversed.",
                onConfirm: async () => {
                  try {
                    await axios.delete('/api/danger/tests/wipe-test-analyses');
                    toast.success("Vulnerability Analysis wiped.");
                  } catch (err) { toast.error("Failed to wipe Vulnerability Analysis."); }
                }
              });
            }}
            className="w-full mt-6 bg-orange-500 hover:bg-orange-600 text-white font-bold py-2.5 px-4 rounded-xl shadow-sm transition-colors text-sm"
          >
            Wipe  Vulnerability Analysis
          </button>
        </div>

        {/* Card 5: Wipe Secure Notes */}
        <div className="bg-white dark:bg-zinc-900 border border-red-200 dark:border-red-900/50 p-6 rounded-3xl shadow-sm flex flex-col justify-between h-full">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-zinc-100 text-base">Wipe All Secure Notes</h3>
            <p className="text-sm text-slate-500 dark:text-zinc-400 mt-2">
              Permanently destroys all E2EE encrypted pentester notes from the vault. Keys cannot be recovered.
            </p>
          </div>
          <button
            onClick={() => {
              setActionModal({
                isOpen: true, variant: 'danger', confirmText: "Wipe Secrets", title: "Wipe All Secure Notes",
                message: "Are you sure you want to permanently wipe ALL encrypted notes from the vault? This action cannot be reversed.",
                onConfirm: async () => {
                  try {
                    await axios.delete('/api/danger/secrets-note/wipe-secrets');
                    toast.success("Notes wiped.");
                  } catch (err) { toast.error("Failed to wipe notes."); }
                }
              });
            }}
            className="w-full mt-6 bg-red-600 hover:bg-red-700 text-white font-bold py-2.5 px-4 rounded-xl shadow-sm transition-colors text-sm"
          >
            Wipe Secure Notes
          </button>
        </div>

        {/* Card 6: Factory Reset Database */}
        <div className="bg-white dark:bg-zinc-900 border border-red-200 dark:border-red-900/50 p-6 rounded-3xl shadow-sm flex flex-col justify-between h-full">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-zinc-100 text-base">Factory Reset Database</h3>
            <p className="text-sm text-slate-500 dark:text-zinc-400 mt-2">
              Purges all tests, assets, and assignments. Keeps configuration settings (Services, Countries, Users).
            </p>
          </div>
          <button
            onClick={() => setNukeModalOpen(true)}
            className="w-full mt-6 bg-red-600 hover:bg-red-700 text-white font-bold py-2.5 px-4 rounded-xl shadow-sm transition-colors text-sm"
          >
            Execute Factory Reset
          </button>
        </div>

      </div>
    </div>
  );
}