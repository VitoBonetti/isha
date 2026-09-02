import React, { useState } from 'react';
import { useSettings } from '../../hooks/useSettings';
import ConfirmModal from '../../components/Modals/ConfirmModal';
import {
  Flag, Plus, Edit2, Trash2, X, ChevronsUpDown, ChevronUp, ChevronDown
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

const defaultCountryForm = { code: '', name: '', region_id: '', is_active: true, kiss24_uuid: '', is_team: false };

export default function CountriesSettings() {
  const { countries, regions, handleSave, handleDelete, isLoading } = useSettings();

  // Panel & Edit State
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [editCountryId, setEditCountryId] = useState<string | null>(null);
  const [countryForm, setCountryForm] = useState(defaultCountryForm);

  // Modals & Pagination
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; id: string; name: string } | null>(null);
  const [countryTab, setCountryTab] = useState<'active' | 'disabled'>('active');
  const [countryPage, setCountryPage] = useState(1);
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
    setEditCountryId(null);
    setCountryForm(defaultCountryForm);
    setIsPanelOpen(true);
  };

  const openEditPanel = (c: any) => {
    setEditCountryId(c.id);
    setCountryForm({
      code: c.code,
      name: c.name,
      region_id: c.region_id || '',
      is_active: c.is_active,
      kiss24_uuid: c.kiss24_uuid || '',
      is_team: c.is_team
    });
    setIsPanelOpen(true);
  };

  const closePanel = () => {
    setIsPanelOpen(false);
    setEditCountryId(null);
    setCountryForm(defaultCountryForm);
  };

  const submitCountry = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      ...countryForm,
      region_id: countryForm.region_id === '' ? null : countryForm.region_id
    };
    const success = await handleSave('/api/countries/', payload, !!editCountryId, editCountryId);
    if (success) closePanel();
  };

  const executeDelete = async () => {
    if (deleteModal) {
      await handleDelete('/api/countries/', deleteModal.id);
      setDeleteModal(null);
    }
  };

  // Filter & Sort
  const displayCountries = countries?.filter(c => countryTab === 'active' ? c.is_active : !c.is_active) || [];
  const sortedCountries = [...displayCountries].sort((a, b) => {
    let res = 0;
    if (sortBy === 'code') res = (a.code || '').localeCompare(b.code || '');
    else if (sortBy === 'name') res = (a.name || '').localeCompare(b.name || '');
    else if (sortBy === 'region_name') res = (a.region_name || '').localeCompare(b.region_name || '');
    return sortDir === 'asc' ? res : -res;
  });

  const paginatedCountries = sortedCountries.slice((countryPage - 1) * ITEMS_PER_PAGE, countryPage * ITEMS_PER_PAGE);

  const inputClasses = "w-full mt-1.5 p-2.5 border border-slate-200 dark:border-zinc-800 rounded-xl bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none text-sm transition-colors";

  if (isLoading) return <div className="p-8 text-center text-slate-500">Loading countries...</div>;

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
            <Flag size={22} className="text-blue-500" /> Countries
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-0.5">
            Manage operating countries and analytics mappings.
          </p>
        </div>
        <button
          onClick={openCreatePanel}
          className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 shadow-sm transition-colors cursor-pointer"
        >
          <Plus size={16} /> Add Country
        </button>
      </div>

      {/* SUB-TABS */}
      <div className="flex gap-6 mb-4 border-b border-slate-200 dark:border-zinc-800 overflow-x-auto whitespace-nowrap">
        <button
          onClick={() => { setCountryTab('active'); setCountryPage(1); }}
          className={`pb-2.5 font-bold text-sm border-b-2 transition-colors ${countryTab === 'active' ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-zinc-300'}`}
        >
          Active Countries ({countries?.filter(c => c.is_active).length || 0})
        </button>
        <button
          onClick={() => { setCountryTab('disabled'); setCountryPage(1); }}
          className={`pb-2.5 font-bold text-sm border-b-2 transition-colors ${countryTab === 'disabled' ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-zinc-300'}`}
        >
          Disabled Countries ({countries?.filter(c => !c.is_active).length || 0})
        </button>
      </div>

      {/* TABLE CONTAINER */}
      <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col bg-white dark:bg-zinc-900">

        {/* DESKTOP TABLE */}
        <table className="hidden md:table w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-slate-50 dark:bg-zinc-950/50 border-b border-slate-200 dark:border-zinc-800 select-none">
            <tr>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('code')}>
                Code <SortIcon column="code" />
              </th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('name')}>
                Country Name <SortIcon column="name" />
              </th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('region_name')}>
                Region <SortIcon column="region_name" />
              </th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
            {paginatedCountries.map(c => (
              <tr key={c.id} className="hover:bg-slate-50/50 dark:hover:bg-zinc-800/30 transition-colors">
                <td className="p-4 text-slate-500 dark:text-zinc-400 font-mono font-bold">{c.code}</td>
                <td className="p-4 font-bold text-slate-900 dark:text-zinc-100">{c.name}</td>
                <td className="p-4">
                  <span className="px-2.5 py-1 rounded-full bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 text-indigo-700 dark:text-indigo-400 text-xs font-bold shadow-sm">
                    {c.region_name || 'Unmapped'}
                  </span>
                </td>
                <td className="p-4 text-right">
                  <div className="flex justify-end gap-2">
                    <button onClick={() => openEditPanel(c)} className="text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 p-2 rounded-xl transition-colors cursor-pointer">
                      <Edit2 size={16} />
                    </button>
                    <button onClick={() => setDeleteModal({ isOpen: true, id: c.id, name: c.name })} className="text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 p-2 rounded-xl transition-colors cursor-pointer">
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
          {paginatedCountries.map(c => (
            <div key={c.id} className="p-4 flex flex-col gap-3">
              <div className="flex justify-between items-start gap-4 w-full">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <span className="font-mono text-slate-500 dark:text-zinc-400 text-xs bg-slate-100 dark:bg-zinc-800 px-2 py-0.5 rounded border border-slate-200 dark:border-zinc-700 shrink-0">{c.code}</span>
                  <span className="font-bold text-base text-slate-900 dark:text-zinc-100 truncate">{c.name}</span>
                </div>
                <span className="px-2.5 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 text-indigo-700 dark:text-indigo-400 text-[10px] font-bold shadow-sm shrink-0 whitespace-nowrap">
                  {c.region_name || 'Unmapped'}
                </span>
              </div>
              <div className="flex justify-end gap-2 mt-1">
                <button onClick={() => openEditPanel(c)} className="text-slate-600 dark:text-zinc-300 bg-slate-100 dark:bg-zinc-800 p-2.5 rounded-xl flex-1 flex justify-center items-center"><Edit2 size={14} /></button>
                <button onClick={() => setDeleteModal({ isOpen: true, id: c.id, name: c.name })} className="text-red-600 bg-red-50 dark:bg-red-900/20 p-2.5 rounded-xl flex-1 flex justify-center items-center"><Trash2 size={14} /></button>
              </div>
            </div>
          ))}
        </div>

        {displayCountries.length === 0 && (
          <div className="p-12 text-center text-sm text-slate-500 dark:text-zinc-500">
            No {countryTab} countries found.
          </div>
        )}

        {/* PAGINATION FOOTER */}
        {displayCountries.length > 0 && (
          <div className="px-4 py-3.5 border-t border-slate-200 dark:border-zinc-800 flex flex-col sm:flex-row justify-between items-center gap-3 bg-slate-50/50 dark:bg-zinc-950/50 text-xs font-medium">
            <span className="text-slate-500">
              Page <strong className="text-slate-800 dark:text-zinc-200">{countryPage}</strong> of <strong className="text-slate-800 dark:text-zinc-200">{Math.ceil(displayCountries.length / ITEMS_PER_PAGE) || 1}</strong>
            </span>
            <div className="flex gap-2 w-full sm:w-auto">
              <button onClick={() => setCountryPage(p => Math.max(1, p - 1))} disabled={countryPage === 1} className="flex-1 sm:flex-none px-4 py-1.5 border border-slate-200 dark:border-zinc-800 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors bg-white dark:bg-zinc-900">
                Previous
              </button>
              <button onClick={() => setCountryPage(p => p + 1)} disabled={countryPage >= Math.ceil(displayCountries.length / ITEMS_PER_PAGE)} className="flex-1 sm:flex-none px-4 py-1.5 border border-slate-200 dark:border-zinc-800 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors bg-white dark:bg-zinc-900">
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
                  {editCountryId ? 'Edit Country' : 'Add Country'}
                </h3>
                <button onClick={closePanel} className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer">
                  <X size={18} />
                </button>
              </div>

              <form onSubmit={submitCountry} className="flex-1 p-6 overflow-y-auto space-y-6">

                <div className="grid grid-cols-2 gap-4">
                  <div className="col-span-2">
                    <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                      Country Name
                    </label>
                    <input type="text" className={inputClasses} value={countryForm.name} onChange={e => setCountryForm({ ...countryForm, name: e.target.value })} required />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                      Code
                    </label>
                    <input type="text" className={inputClasses} value={countryForm.code} onChange={e => setCountryForm({ ...countryForm, code: e.target.value.toUpperCase() })} required placeholder="e.g. US" />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                    Region Mapping
                  </label>
                  <select className={inputClasses} value={countryForm.region_id} onChange={e => setCountryForm({ ...countryForm, region_id: e.target.value })}>
                    <option value="">-- None --</option>
                    {regions?.map(r => <option key={r.id} value={r.id}>{r.name || r.regions}</option>)}
                  </select>
                </div>

                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                    Kiss24 Organization UUID
                  </label>
                  <input type="text" className={inputClasses} value={countryForm.kiss24_uuid} onChange={e => setCountryForm({ ...countryForm, kiss24_uuid: e.target.value })} placeholder="Optional UUID" />
                </div>

                <div className="pt-4 border-t border-slate-100 dark:border-zinc-800">
                  <Toggle checked={countryForm.is_active} onChange={(c) => setCountryForm({ ...countryForm, is_active: c })} label="Country is Active" />
                </div>

                <div className="pt-4 border-t border-slate-100 dark:border-zinc-800">
                  <Toggle checked={countryForm.is_team} onChange={(c) => setCountryForm({ ...countryForm, is_team: c })} label="Team Use Country" />
                </div>

                <div className="fixed bottom-0 right-0 w-full max-w-md p-6 bg-white dark:bg-zinc-900 border-t border-slate-100 dark:border-zinc-800 flex justify-end gap-3 z-10">
                  <button type="button" onClick={closePanel} className="px-5 py-2.5 text-sm font-bold bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-zinc-700 rounded-xl transition-colors cursor-pointer">
                    Cancel
                  </button>
                  <button type="submit" className="px-5 py-2.5 text-sm font-bold bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-sm transition-colors cursor-pointer">
                    {editCountryId ? 'Update Country' : 'Save Country'}
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