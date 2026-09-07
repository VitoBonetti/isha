import React, { useState } from 'react';
import { useSettings } from '../../hooks/useSettings';
import ConfirmModal from '../../components/Modals/ConfirmModal';
import { useAppContext } from "../../context/AppContext";
import {
  LayoutTemplate, Plus, Edit2, Trash2, X, ChevronsUpDown, ChevronUp, ChevronDown
} from 'lucide-react';

const defaultTypeForm = { name: '' };

export default function AssetTypesSettings() {
  const { currentUser } = useAppContext();
  const { assetTypes, handleSave, handleDelete, isLoading } = useSettings();

  // Panel & Edit State
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [editTypeId, setEditTypeId] = useState<string | null>(null);
  const [typeForm, setTypeForm] = useState(defaultTypeForm);

  const isReadOnly = currentUser?.role === 'read_only';

  // Modals & Pagination
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; id: string; name: string } | null>(null);
  const [page, setPage] = useState(1);
  const ITEMS_PER_PAGE = 15;

  // Sorting
  const [sortBy, setSortBy] = useState<string>('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const handleSort = (column: string) => {
    if (sortBy === column) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortBy(column); setSortDir('asc'); }
  };

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return <ChevronsUpDown size={14} className="opacity-30 inline-block" />;
    return sortDir === 'asc' ? <ChevronUp size={14} className="text-emerald-500 inline-block" /> : <ChevronDown size={14} className="text-emerald-500 inline-block" />;
  };

  const openCreatePanel = () => {
    setEditTypeId(null);
    setTypeForm(defaultTypeForm);
    setIsPanelOpen(true);
  };

  const openEditPanel = (at: any) => {
    setEditTypeId(at.id);
    setTypeForm({ name: at.name });
    setIsPanelOpen(true);
  };

  const closePanel = () => {
    setIsPanelOpen(false);
    setEditTypeId(null);
    setTypeForm(defaultTypeForm);
  };

  const submitType = async (e: React.FormEvent) => {
    e.preventDefault();
    const success = await handleSave('/api/assets/types/', { name: typeForm.name }, !!editTypeId, editTypeId);
    if (success) {
      closePanel();
    }
  };

  const executeDelete = async () => {
    if (deleteModal) {
      await handleDelete('/api/assets/types/', deleteModal.id);
      setDeleteModal(null);
    }
  };

  // Sort & Paginate
  const sortedTypes = [...(assetTypes || [])].sort((a, b) => {
    let res = (a.name || '').localeCompare(b.name || '');
    return sortDir === 'asc' ? res : -res;
  });

  const paginatedTypes = sortedTypes.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

  const inputClasses = "w-full mt-1.5 p-2.5 border border-slate-200 dark:border-zinc-800 rounded-xl bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none text-sm transition-colors";

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Loading asset types...</div>;
  }

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">
      <ConfirmModal
        isOpen={!!deleteModal}
        title="Confirm Deletion"
        message={`Are you sure you want to delete the asset type "${deleteModal?.name}"? WARNING: Deleting this will also delete all associated raw assets! This action cannot be undone.`}
        onConfirm={executeDelete}
        onCancel={() => setDeleteModal(null)}
      />

      {/* HEADER BAR */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <LayoutTemplate size={22} className="text-blue-500" /> Asset Types
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-0.5">
            Manage categories of applications (e.g., APIs, Web, Mobile, Infrastructure).
          </p>
        </div>
        {!isReadOnly && (
          <button
            onClick={openCreatePanel}
            className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 shadow-sm transition-colors cursor-pointer"
          >
            <Plus size={16} /> Add Asset Type
          </button>
         )}
      </div>

      {/* TABLE CONTAINER */}
      <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col bg-white dark:bg-zinc-900">

        {/* DESKTOP TABLE */}
        <table className="hidden md:table w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-slate-50 dark:bg-zinc-950/50 border-b border-slate-200 dark:border-zinc-800 select-none">
            <tr>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('name')}>
                Type Name <SortIcon column="name" />
              </th>
              {!isReadOnly && (
                <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
            {paginatedTypes.map((at: any) => (
              <tr key={at.id} className="hover:bg-slate-50/50 dark:hover:bg-zinc-800/30 transition-colors">
                <td className="p-4 font-bold text-slate-900 dark:text-zinc-100">
                  {at.name}
                </td>
                {!isReadOnly && (
                  <td className="p-4 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => openEditPanel(at)}
                        className="text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 p-2 rounded-xl transition-colors cursor-pointer"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        onClick={() => setDeleteModal({ isOpen: true, id: at.id, name: at.name })}
                        className="text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 p-2 rounded-xl transition-colors cursor-pointer"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>

        {/* MOBILE CARDS */}
        <div className="flex md:hidden flex-col divide-y divide-slate-100 dark:divide-zinc-800">
          {paginatedTypes.map((at: any) => (
            <div key={at.id} className="p-4 flex flex-col gap-3">
              <div className="flex items-center min-w-0">
                <span className="font-bold text-base text-slate-900 dark:text-zinc-100 truncate">{at.name}</span>
              </div>
              {!isReadOnly && (
                <div className="flex justify-end gap-2 mt-1">
                  <button
                    onClick={() => openEditPanel(at)}
                    className="text-slate-600 dark:text-zinc-300 bg-slate-100 dark:bg-zinc-800 p-2 rounded-xl flex-1 flex justify-center items-center font-bold text-xs gap-1"
                  >
                    <Edit2 size={14} /> Edit
                  </button>
                  <button
                    onClick={() => setDeleteModal({ isOpen: true, id: at.id, name: at.name })}
                    className="text-red-600 bg-red-50 dark:bg-red-900/20 p-2 rounded-xl flex-1 flex justify-center items-center font-bold text-xs gap-1"
                  >
                    <Trash2 size={14} /> Delete
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        {sortedTypes.length === 0 && (
          <div className="p-12 text-center text-sm text-slate-500 dark:text-zinc-500">
            No asset types found.
          </div>
        )}

        {/* PAGINATION FOOTER */}
        {sortedTypes.length > 0 && (
          <div className="px-4 py-3.5 border-t border-slate-200 dark:border-zinc-800 flex flex-col sm:flex-row justify-between items-center gap-3 bg-slate-50/50 dark:bg-zinc-950/50 text-xs font-medium">
            <span className="text-slate-500">
              Page <strong className="text-slate-800 dark:text-zinc-200">{page}</strong> of <strong className="text-slate-800 dark:text-zinc-200">{Math.ceil(sortedTypes.length / ITEMS_PER_PAGE) || 1}</strong>
            </span>
            <div className="flex gap-2 w-full sm:w-auto">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="flex-1 sm:flex-none px-4 py-1.5 border border-slate-200 dark:border-zinc-800 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors bg-white dark:bg-zinc-900"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={page >= Math.ceil(sortedTypes.length / ITEMS_PER_PAGE)}
                className="flex-1 sm:flex-none px-4 py-1.5 border border-slate-200 dark:border-zinc-800 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors bg-white dark:bg-zinc-900"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* RIGHT SLIDE-OVER FORM PANEL */}
      {isPanelOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-slate-900/40 dark:bg-zinc-950/70 backdrop-blur-sm transition-opacity animate-in fade-in"
            onClick={closePanel}
          />

          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-md bg-white dark:bg-zinc-900 border-l border-slate-200 dark:border-zinc-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">

              {/* PANEL HEADER */}
              <div className="p-6 border-b border-slate-100 dark:border-zinc-800 flex justify-between items-center bg-slate-50/50 dark:bg-zinc-950/50">
                <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100">
                  {editTypeId ? 'Edit Asset Type' : 'Add Asset Type'}
                </h3>
                <button
                  onClick={closePanel}
                  className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                >
                  <X size={18} />
                </button>
              </div>

              {/* PANEL BODY (FORM) */}
              <form onSubmit={submitType} className="flex-1 p-6 overflow-y-auto space-y-6">
                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                    Asset Type Name
                  </label>
                  <input
                    type="text"
                    className={inputClasses}
                    value={typeForm.name}
                    onChange={e => setTypeForm({ ...typeForm, name: e.target.value })}
                    required
                    placeholder="e.g. Mobile Application"
                  />
                </div>

                {/* PANEL FOOTER ACTIONS */}
                <div className="pt-6 mt-auto border-t border-slate-100 dark:border-zinc-800 flex justify-end gap-3 absolute bottom-0 left-0 right-0 p-6 bg-white dark:bg-zinc-900">
                  <button
                    type="button"
                    onClick={closePanel}
                    className="px-5 py-2.5 text-sm font-bold bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-zinc-700 rounded-xl transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-5 py-2.5 text-sm font-bold bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-sm transition-colors cursor-pointer"
                  >
                    {editTypeId ? 'Update Asset Type' : 'Save Asset Type'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}