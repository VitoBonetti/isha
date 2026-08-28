import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { useSettings } from '../../hooks/useSettings';
import ConfirmModal from '../../components/Modals/ConfirmModal';
import {
  Tags, Plus, Edit2, Trash2, X, ChevronsUpDown, ChevronUp, ChevronDown
} from 'lucide-react';

const currentYear = new Date().getFullYear();
const availableYears = Array.from({ length: 7 }, (_, i) => currentYear - 1 + i);

const defaultCatForm = {
  name: '',
  target_goal: 0,
  service_lane_id: '',
  year: currentYear
};

export default function CategoriesSettings() {
  const { services, handleDelete } = useSettings(); // Use global services for dropdowns

  const [categories, setCategories] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Filters
  const [filterCatYear, setFilterCatYear] = useState<string>(currentYear.toString());
  const [filterCatLane, setFilterCatLane] = useState<string>("All");

  // Panel & Edit State
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [editCatId, setEditCatId] = useState<string | null>(null);
  const [catForm, setCatForm] = useState(defaultCatForm);

  // Modals & Pagination
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; id: string; name: string } | null>(null);
  const [catPage, setCatPage] = useState(1);
  const ITEMS_PER_PAGE = 15;

  // Sorting
  const [sortBy, setSortBy] = useState<string>('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const fetchCategories = async () => {
    setIsLoading(true);
    try {
      // If "All" years is selected, you might need a different endpoint, but based on your code:
      const yearQuery = filterCatYear === "All" ? currentYear : filterCatYear;
      const res = await axios.get(`/api/board/categories/?year=${yearQuery}`);
      setCategories(res.data);
    } catch (err) {
      toast.error("Failed to load categories.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCategories();
    setCatPage(1); // Reset page on filter change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterCatYear]);

  const handleSort = (column: string) => {
    if (sortBy === column) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortBy(column); setSortDir('asc'); }
  };

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return <ChevronsUpDown size={14} className="opacity-30 inline-block" />;
    return sortDir === 'asc' ? <ChevronUp size={14} className="text-emerald-500 inline-block" /> : <ChevronDown size={14} className="text-emerald-500 inline-block" />;
  };

  const openCreatePanel = () => {
    setEditCatId(null);
    setCatForm({ ...defaultCatForm, year: filterCatYear === "All" ? currentYear : parseInt(filterCatYear) });
    setIsPanelOpen(true);
  };

  const openEditPanel = (c: any) => {
    setEditCatId(c.id);
    setCatForm({
      name: c.name,
      target_goal: c.target_goal,
      service_lane_id: c.service_lane_id || '',
      year: c.goal_year || currentYear
    });
    setIsPanelOpen(true);
  };

  const closePanel = () => {
    setIsPanelOpen(false);
    setEditCatId(null);
    setCatForm(defaultCatForm);
  };

  const submitCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      name: catForm.name,
      target_goal: catForm.target_goal,
      service_lane_id: catForm.service_lane_id === '' ? null : catForm.service_lane_id
    };
    const toastId = toast.loading("Saving category...");

    try {
      if (editCatId) {
        await axios.put(`/api/board/categories/${editCatId}?year=${catForm.year}`, payload);
        toast.success("Category updated", { id: toastId });
      } else {
        await axios.post(`/api/board/categories/?year=${catForm.year}`, payload);
        toast.success("Category created", { id: toastId });
      }
      closePanel();
      fetchCategories();
    } catch (err) {
      toast.error("Failed to save category", { id: toastId });
    }
  };

  const executeDelete = async () => {
    if (!deleteModal) return;
    try {
      await axios.delete(`/api/board/categories/${deleteModal.id}`);
      toast.success("Category deleted");
      setDeleteModal(null);
      fetchCategories();
    } catch (err) {
      toast.error("Failed to delete category. It may be in use.");
    }
  };

  // Filter & Sort
  const processedCategories = useMemo(() => {
    let result = [...categories];

    // Lane Filter
    if (filterCatLane !== "All") {
      result = result.filter(c => c.service_lane_id === filterCatLane);
    }

    // Sort
    result.sort((a, b) => {
      let res = 0;
      if (sortBy === 'name') res = (a.name || '').localeCompare(b.name || '');
      else if (sortBy === 'target_goal') res = (a.target_goal || 0) - (b.target_goal || 0);
      else if (sortBy === 'goal_year') res = (a.goal_year || 0) - (b.goal_year || 0);
      else if (sortBy === 'service_lane') res = (a.service_lane_name || '').localeCompare(b.service_lane_name || '');
      return sortDir === 'asc' ? res : -res;
    });

    return result;
  }, [categories, filterCatLane, sortBy, sortDir]);

  const paginatedCategories = processedCategories.slice((catPage - 1) * ITEMS_PER_PAGE, catPage * ITEMS_PER_PAGE);

  const inputClasses = "w-full mt-1.5 p-2.5 border border-slate-200 dark:border-zinc-800 rounded-xl bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none text-sm transition-colors";

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">

      <ConfirmModal
        isOpen={!!deleteModal}
        title="Confirm Deletion"
        message={`Are you sure you want to delete ${deleteModal?.name}? This action cannot be undone.`}
        onConfirm={executeDelete}
        onCancel={() => setDeleteModal(null)}
      />

      {/* HEADER BAR & FILTERS */}
      <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Tags size={22} className="text-blue-500" /> Service Forecast Categories
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-0.5">
            Manage specific target goals and map them to parent service lanes.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full xl:w-auto">
          <select
            className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-sm px-3 py-2.5 rounded-xl outline-none cursor-pointer text-slate-700 dark:text-zinc-300 shadow-sm flex-1 xl:flex-none"
            value={filterCatLane}
            onChange={e => setFilterCatLane(e.target.value)}
          >
            <option value="All">All Service Lanes</option>
            {services?.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>

          <select
            className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 font-black text-blue-600 dark:text-blue-400 text-sm px-3 py-2.5 rounded-xl outline-none cursor-pointer shadow-sm flex-1 xl:flex-none"
            value={filterCatYear}
            onChange={e => setFilterCatYear(e.target.value)}
          >
            <option value="All">All Years</option>
            {availableYears.map(y => <option key={y} value={y}>{y}</option>)}
          </select>

          <button
            onClick={openCreatePanel}
            className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 shadow-sm transition-colors cursor-pointer"
          >
            <Plus size={16} /> Add Category
          </button>
        </div>
      </div>

      {/* TABLE CONTAINER */}
      <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col bg-white dark:bg-zinc-900">

        {isLoading ? (
           <div className="p-12 text-center text-slate-500">Loading categories...</div>
        ) : (
          <>
            {/* DESKTOP TABLE */}
            <table className="hidden md:table w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-slate-50 dark:bg-zinc-950/50 border-b border-slate-200 dark:border-zinc-800 select-none">
                <tr>
                  <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('name')}>
                    Category Name <SortIcon column="name" />
                  </th>
                  <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('target_goal')}>
                    Target Goal <SortIcon column="target_goal" />
                  </th>
                  <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('goal_year')}>
                    Target Year <SortIcon column="goal_year" />
                  </th>
                  <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('service_lane')}>
                    Service Lane <SortIcon column="service_lane" />
                  </th>
                  <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                {paginatedCategories.map(c => (
                  <tr key={c.id} className="hover:bg-slate-50/50 dark:hover:bg-zinc-800/30 transition-colors">
                    <td className="p-4 font-bold text-slate-900 dark:text-zinc-100">{c.name}</td>
                    <td className="p-4 text-slate-700 dark:text-zinc-300 font-medium">{c.target_goal}</td>
                    <td className="p-4 font-bold text-slate-500">{c.goal_year || 'Not Set'}</td>
                    <td className="p-4">
                      <span className="px-2.5 py-1 rounded-full bg-slate-100 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 text-slate-700 dark:text-zinc-300 text-xs font-bold shadow-sm">
                        {c.service_lane_name || 'Unlinked'}
                      </span>
                    </td>
                    <td className="p-4 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => openEditPanel(c)}
                          className="text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 p-2 rounded-xl transition-colors cursor-pointer"
                        >
                          <Edit2 size={16} />
                        </button>
                        <button
                          onClick={() => setDeleteModal({ isOpen: true, id: c.id, name: c.name })}
                          className="text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 p-2 rounded-xl transition-colors cursor-pointer"
                        >
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
              {paginatedCategories.map(c => (
                <div key={c.id} className="p-4 flex flex-col gap-3">
                  <div className="flex justify-between items-start gap-4">
                    <span className="font-bold text-base text-slate-900 dark:text-zinc-100 leading-tight">{c.name}</span>
                    <div className="flex flex-col items-end shrink-0 gap-1">
                      <span className="text-xs font-bold text-slate-500 dark:text-zinc-400 bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded border border-slate-200 dark:border-zinc-700">Goal: {c.target_goal}</span>
                      <span className="text-[10px] font-bold text-slate-400 px-1">Year: {c.goal_year || 'Not Set'}</span>
                    </div>
                  </div>
                  <div className="flex justify-between items-center mt-1">
                    <span className="px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 text-slate-700 dark:text-zinc-300 text-[10px] font-bold shadow-sm max-w-[60%] truncate">
                      {c.service_lane_name || 'Unlinked'}
                    </span>
                    <div className="flex gap-2 shrink-0">
                      <button
                        onClick={() => openEditPanel(c)}
                        className="text-slate-500 bg-slate-100 dark:bg-zinc-800 p-2.5 rounded-lg flex-1 flex justify-center items-center"
                      >
                        <Edit2 size={14} />
                      </button>
                      <button
                        onClick={() => setDeleteModal({ isOpen: true, id: c.id, name: c.name })}
                        className="text-red-500 bg-red-50 dark:bg-red-900/20 p-2.5 rounded-lg flex-1 flex justify-center items-center"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {processedCategories.length === 0 && (
              <div className="p-12 text-center text-sm text-slate-500 dark:text-zinc-500">
                No categories match your filters.
              </div>
            )}

            {/* PAGINATION FOOTER */}
            {processedCategories.length > 0 && (
              <div className="px-4 py-3.5 border-t border-slate-200 dark:border-zinc-800 flex flex-col sm:flex-row justify-between items-center gap-3 bg-slate-50/50 dark:bg-zinc-950/50 text-xs font-medium">
                <span className="text-slate-500">
                  Page <strong className="text-slate-800 dark:text-zinc-200">{catPage}</strong> of <strong className="text-slate-800 dark:text-zinc-200">{Math.ceil(processedCategories.length / ITEMS_PER_PAGE) || 1}</strong>
                </span>
                <div className="flex gap-2 w-full sm:w-auto">
                  <button
                    onClick={() => setCatPage(p => Math.max(1, p - 1))}
                    disabled={catPage === 1}
                    className="flex-1 sm:flex-none px-4 py-1.5 border border-slate-200 dark:border-zinc-800 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors bg-white dark:bg-zinc-900"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setCatPage(p => p + 1)}
                    disabled={catPage >= Math.ceil(processedCategories.length / ITEMS_PER_PAGE)}
                    className="flex-1 sm:flex-none px-4 py-1.5 border border-slate-200 dark:border-zinc-800 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors bg-white dark:bg-zinc-900"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* RIGHT SLIDE-OVER FORM PANEL */}
      {isPanelOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-slate-900/40 dark:bg-zinc-950/70 backdrop-blur-sm transition-opacity animate-in fade-in" onClick={closePanel} />

          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-md bg-white dark:bg-zinc-900 border-l border-slate-200 dark:border-zinc-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">

              {/* PANEL HEADER */}
              <div className="p-6 border-b border-slate-100 dark:border-zinc-800 flex justify-between items-center bg-slate-50/50 dark:bg-zinc-950/50">
                <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100">
                  {editCatId ? 'Edit Category' : 'Add Category'}
                </h3>
                <button
                  onClick={closePanel}
                  className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                >
                  <X size={18} />
                </button>
              </div>

              {/* PANEL BODY (FORM) */}
              <form onSubmit={submitCategory} className="flex-1 p-6 overflow-y-auto space-y-6">
                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                    Category Name
                  </label>
                  <input
                    type="text"
                    className={inputClasses}
                    value={catForm.name}
                    onChange={e => setCatForm({ ...catForm, name: e.target.value })}
                    required
                    placeholder="e.g. Q1 Target"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                      Target Year
                    </label>
                    <input
                      type="number"
                      className={inputClasses}
                      value={catForm.year}
                      onChange={e => setCatForm({ ...catForm, year: parseInt(e.target.value) })}
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                      Target Goal
                    </label>
                    <input
                      type="number"
                      className={inputClasses}
                      value={catForm.target_goal}
                      onChange={e => setCatForm({ ...catForm, target_goal: parseInt(e.target.value) })}
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                    Link to Service Lane
                  </label>
                  <select
                    className={inputClasses}
                    value={catForm.service_lane_id}
                    onChange={e => setCatForm({ ...catForm, service_lane_id: e.target.value })}
                  >
                    <option value="">-- None --</option>
                    {services?.map((s: any) => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
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
                    {editCatId ? 'Update Category' : 'Save Category'}
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