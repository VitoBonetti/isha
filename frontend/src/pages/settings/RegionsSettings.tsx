import React, { useState } from 'react';
import { useSettings } from '../../hooks/useSettings';
import ConfirmModal from '../../components/Modals/ConfirmModal';
import {
  Globe, Plus, Edit2, Trash2, X, ChevronsUpDown, ChevronUp, ChevronDown
} from 'lucide-react';

const Toggle = ({ checked, onChange, label, disabled = false }: { checked: boolean, onChange: (c: boolean) => void, label: string, disabled?: boolean }) => (
  <label className={`flex items-center gap-3 select-none ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>
    <div className="relative flex items-center shrink-0">
      <input type="checkbox" className="sr-only" checked={checked} disabled={disabled} onChange={e => onChange(e.target.checked)} />
      <div className={`block w-10 h-6 rounded-full transition-colors duration-300 ${checked ? 'bg-blue-500' : 'bg-slate-300 dark:bg-zinc-700'}`}></div>
      <div className={`absolute left-1 bg-white w-4 h-4 rounded-full transition-transform duration-300 shadow-sm ${checked ? 'transform translate-x-4' : ''}`}></div>
    </div>
    <span className="text-sm font-bold text-slate-700 dark:text-zinc-300 leading-tight">{label}</span>
  </label>
);

const defaultRegionForm = { name: '', is_active: true };

export default function RegionsSettings() {
  const { regions, handleSave, handleDelete, isLoading } = useSettings();

  // Panel & Edit State
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [editRegionId, setEditRegionId] = useState<string | null>(null);
  const [regionForm, setRegionForm] = useState(defaultRegionForm);

  // Modals & Pagination
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; id: string; name: string } | null>(null);
  const [regionTab, setRegionTab] = useState<'active' | 'disabled'>('active');
  const [regionPage, setRegionPage] = useState(1);
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
    setEditRegionId(null);
    setRegionForm(defaultRegionForm);
    setIsPanelOpen(true);
  };

  const openEditPanel = (r: any) => {
    setEditRegionId(r.id);
    setRegionForm({ name: r.name, is_active: r.is_active });
    setIsPanelOpen(true);
  };

  const closePanel = () => {
    setIsPanelOpen(false);
    setEditRegionId(null);
    setRegionForm(defaultRegionForm);
  };

  const submitRegion = async (e: React.FormEvent) => {
    e.preventDefault();
    const success = await handleSave('/api/regions/', regionForm, !!editRegionId, editRegionId);
    if (success) closePanel();
  };

  const executeDelete = async () => {
    if (deleteModal) {
      await handleDelete('/api/regions/', deleteModal.id);
      setDeleteModal(null);
    }
  };

  // Filter & Sort
  const displayRegions = regions?.filter(r => regionTab === 'active' ? r.is_active : !r.is_active) || [];
  const sortedRegions = [...displayRegions].sort((a, b) => {
    let res = (a.name || '').localeCompare(b.name || '');
    return sortDir === 'asc' ? res : -res;
  });

  const paginatedRegions = sortedRegions.slice((regionPage - 1) * ITEMS_PER_PAGE, regionPage * ITEMS_PER_PAGE);

  const inputClasses = "w-full mt-1.5 p-2.5 border border-slate-200 dark:border-zinc-800 rounded-xl bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none text-sm transition-colors";

  if (isLoading) return <div className="p-8 text-center text-slate-500">Loading regions...</div>;

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">
      <ConfirmModal
        isOpen={!!deleteModal}
        title="Confirm Deletion"
        message={`Are you sure you want to delete ${deleteModal?.name}? This action cannot be undone.`}
        onConfirm={executeDelete}
        onCancel={() => setDeleteModal(null)}
      />

      {/* HEADER BAR */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Globe size={22} className="text-blue-500" /> Regions
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-0.5">
            Manage broad operational boundaries.
          </p>
        </div>
        <button
          onClick={openCreatePanel}
          className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 shadow-sm transition-colors cursor-pointer"
        >
          <Plus size={16} /> Add Region
        </button>
      </div>

      {/* SUB-TABS */}
      <div className="flex gap-6 mb-4 border-b border-slate-200 dark:border-zinc-800 overflow-x-auto whitespace-nowrap">
        <button
          onClick={() => { setRegionTab('active'); setRegionPage(1); }}
          className={`pb-2.5 font-bold text-sm border-b-2 transition-colors ${regionTab === 'active' ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-zinc-300'}`}
        >
          Active Regions ({regions?.filter(r => r.is_active).length || 0})
        </button>
        <button
          onClick={() => { setRegionTab('disabled'); setRegionPage(1); }}
          className={`pb-2.5 font-bold text-sm border-b-2 transition-colors ${regionTab === 'disabled' ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-zinc-300'}`}
        >
          Disabled Regions ({regions?.filter(r => !r.is_active).length || 0})
        </button>
      </div>

      {/* TABLE CONTAINER */}
      <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col bg-white dark:bg-zinc-900">

        {/* DESKTOP TABLE */}
        <table className="hidden md:table w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-slate-50 dark:bg-zinc-950/50 border-b border-slate-200 dark:border-zinc-800 select-none">
            <tr>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('name')}>
                Region Name <SortIcon column="name" />
              </th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
            {paginatedRegions.map(r => (
              <tr key={r.id} className="hover:bg-slate-50/50 dark:hover:bg-zinc-800/30 transition-colors">
                <td className="p-4 font-bold text-slate-900 dark:text-zinc-100">{r.name}</td>
                <td className="p-4 text-right">
                  <div className="flex justify-end gap-2">
                    <button onClick={() => openEditPanel(r)} className="text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 p-2 rounded-xl transition-colors cursor-pointer">
                      <Edit2 size={16} />
                    </button>
                    <button onClick={() => setDeleteModal({ isOpen: true, id: r.id, name: r.name })} className="text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 p-2 rounded-xl transition-colors cursor-pointer">
                      <Trash2 size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* MOBILE CARDS */}
        <div className="flex md:hidden flex-col divide-y divide-slate-100 dark:divide-zinc-800">
          {paginatedRegions.map(r => (
            <div key={r.id} className="p-4 flex justify-between items-center gap-4">
              <span className="font-bold text-base text-slate-900 dark:text-zinc-100 truncate flex-1">{r.name}</span>
              <div className="flex gap-2 shrink-0">
                <button onClick={() => openEditPanel(r)} className="text-slate-600 dark:text-zinc-300 bg-slate-100 dark:bg-zinc-800 p-2.5 rounded-xl"><Edit2 size={14} /></button>
                <button onClick={() => setDeleteModal({ isOpen: true, id: r.id, name: r.name })} className="text-red-600 bg-red-50 dark:bg-red-900/20 p-2.5 rounded-xl"><Trash2 size={14} /></button>
              </div>
            </div>
          ))}
        </div>

        {displayRegions.length === 0 && (
          <div className="p-12 text-center text-sm text-slate-500 dark:text-zinc-500">
            No {regionTab} regions found.
          </div>
        )}

        {/* PAGINATION FOOTER */}
        {displayRegions.length > 0 && (
          <div className="px-4 py-3.5 border-t border-slate-200 dark:border-zinc-800 flex flex-col sm:flex-row justify-between items-center gap-3 bg-slate-50/50 dark:bg-zinc-950/50 text-xs font-medium">
            <span className="text-slate-500">
              Page <strong className="text-slate-800 dark:text-zinc-200">{regionPage}</strong> of <strong className="text-slate-800 dark:text-zinc-200">{Math.ceil(displayRegions.length / ITEMS_PER_PAGE) || 1}</strong>
            </span>
            <div className="flex gap-2 w-full sm:w-auto">
              <button onClick={() => setRegionPage(p => Math.max(1, p - 1))} disabled={regionPage === 1} className="flex-1 sm:flex-none px-4 py-1.5 border border-slate-200 dark:border-zinc-800 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors bg-white dark:bg-zinc-900">
                Previous
              </button>
              <button onClick={() => setRegionPage(p => p + 1)} disabled={regionPage >= Math.ceil(displayRegions.length / ITEMS_PER_PAGE)} className="flex-1 sm:flex-none px-4 py-1.5 border border-slate-200 dark:border-zinc-800 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors bg-white dark:bg-zinc-900">
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* RIGHT SLIDE-OVER FORM PANEL */}
      {isPanelOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-slate-900/40 dark:bg-zinc-950/70 backdrop-blur-sm transition-opacity animate-in fade-in" onClick={closePanel} />
          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-md bg-white dark:bg-zinc-900 border-l border-slate-200 dark:border-zinc-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
              <div className="p-6 border-b border-slate-100 dark:border-zinc-800 flex justify-between items-center bg-slate-50/50 dark:bg-zinc-950/50">
                <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100">
                  {editRegionId ? 'Edit Region' : 'Add Region'}
                </h3>
                <button onClick={closePanel} className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer">
                  <X size={18} />
                </button>
              </div>

              <form onSubmit={submitRegion} className="flex-1 p-6 overflow-y-auto space-y-6">
                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                    Region Name
                  </label>
                  <input
                    type="text"
                    className={inputClasses}
                    value={regionForm.name}
                    onChange={e => setRegionForm({ ...regionForm, name: e.target.value })}
                    required
                  />
                </div>

                <div className="pt-2 border-t border-slate-100 dark:border-zinc-800">
                  <Toggle
                    checked={regionForm.is_active}
                    onChange={(c) => setRegionForm({ ...regionForm, is_active: c })}
                    label="Region is Active"
                  />
                </div>

                <div className="fixed bottom-0 right-0 w-full max-w-md p-6 bg-white dark:bg-zinc-900 border-t border-slate-100 dark:border-zinc-800 flex justify-end gap-3 z-10">
                  <button type="button" onClick={closePanel} className="px-5 py-2.5 text-sm font-bold bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-zinc-700 rounded-xl transition-colors cursor-pointer">
                    Cancel
                  </button>
                  <button type="submit" className="px-5 py-2.5 text-sm font-bold bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-sm transition-colors cursor-pointer">
                    {editRegionId ? 'Update Region' : 'Save Region'}
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