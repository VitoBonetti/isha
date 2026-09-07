import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { useSettings } from '../../hooks/useSettings';
import type { UserFormState} from "../../types/board";
import ConfirmModal from '../../components/Modals/ConfirmModal';
import { useAppContext } from "../../context/AppContext";
import {
  Users, Plus, Edit2, Trash2, X, ChevronsUpDown, ChevronUp, ChevronDown
} from 'lucide-react';


const defaultUserForm: UserFormState = {
  email: '',
  name: '',
  role: 'read_only',
  service_lane_id: '',
  base_capacity: 1.0,
  location_id: '',
  start_week: 1,
  start_year: new Date().getFullYear(),
  end_week: '',
  end_year: '',
  kiss24_uuid: '',
  kiss24_api_key: ''
};

export default function UsersSettings() {
  const { currentUser } = useAppContext();
  const { users, locations, handleSave, handleDelete, isLoading } = useSettings();
  const [services, setServices] = useState<any[]>([]);

  const isReadOnly = currentUser?.role === 'read_only';

  // Panel & Edit State
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [editUserId, setEditUserId] = useState<string | null>(null);
  const [userForm, setUserForm] = useState<UserFormState>(defaultUserForm);

  // Modals & Sub-tabs
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; id: string; name: string } | null>(null);
  const [userTab, setUserTab] = useState<'active' | 'offboarded'>('active');
  const [userPage, setUserPage] = useState(1);
  const ITEMS_PER_PAGE = 15;

  // Sorting
  const [sortBy, setSortBy] = useState<string>('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  // Server Time for Offboard Calculations
  const [serverTime, setServerTime] = useState({ year: new Date().getFullYear(), week: 1 });

  useEffect(() => {
    axios.get('/api/users/system/time')
      .then(res => setServerTime(res.data))
      .catch(console.error);

    axios.get('/api/services/')
      .then(res => setServices(res.data))
      .catch(console.error);
  }, []);

  const handleSort = (column: string) => {
    if (sortBy === column) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortBy(column); setSortDir('asc'); }
  };

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return <ChevronsUpDown size={14} className="opacity-30 inline-block" />;
    return sortDir === 'asc' ? <ChevronUp size={14} className="text-emerald-500 inline-block" /> : <ChevronDown size={14} className="text-emerald-500 inline-block" />;
  };

  const isOffboarded = (u: any) => {
    if (!u.end_year || !u.end_week) return false;
    if (serverTime.year > u.end_year) return true;
    if (serverTime.year === u.end_year && serverTime.week > u.end_week) return true;
    return false;
  };

  const openCreatePanel = () => {
    setEditUserId(null);
    setUserForm(defaultUserForm);
    setIsPanelOpen(true);
  };

  const openEditPanel = (u: any) => {
    setEditUserId(u.id);
    setUserForm({
      email: u.email || '',
      name: u.name || '',
      role: u.role || 'read_only',
      service_lane_id: u.service_lane_id || '',
      base_capacity: u.base_capacity || 1.0,
      location_id: u.location_id || '',
      start_week: u.start_week || 1,
      start_year: u.start_year || new Date().getFullYear(),
      end_week: u.end_week || '',
      end_year: u.end_year || '',
      kiss24_uuid: u.kiss24_uuid || '',
      kiss24_api_key: u.kiss24_api_key || ''
    });
    setIsPanelOpen(true);
  };

  const closePanel = () => {
    setIsPanelOpen(false);
    setEditUserId(null);
    setUserForm(defaultUserForm);
  };

  const submitUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (userForm.role === 'maintainer' && !userForm.service_lane_id) {
      toast.error("Please select a Service Lane for the Maintainer role.");
      return;
    }

    const payload = {
      ...userForm,
      location_id: userForm.location_id === '' ? null : userForm.location_id,
      service_lane_id: userForm.role === 'maintainer' && userForm.service_lane_id !== '' ? userForm.service_lane_id : null,
      end_week: userForm.end_week === '' ? null : parseInt(userForm.end_week as string),
      end_year: userForm.end_year === '' ? null : parseInt(userForm.end_year as string)
    };

    const success = await handleSave('/api/users/', payload, !!editUserId, editUserId);
    if (success) {
      closePanel();
    }
  };

  const executeDelete = async () => {
    if (deleteModal) {
      await handleDelete('/api/users/', deleteModal.id);
      setDeleteModal(null);
    }
  };

  const getServiceLaneName = (laneId: string) => {
    return services.find(s => s.id === laneId)?.name || 'Unknown Lane';
  };

  const displayUsers = users?.filter(u => userTab === 'active' ? !isOffboarded(u) : isOffboarded(u)) || [];
  const sortedUsers = [...displayUsers].sort((a, b) => {
    let res = 0;
    if (sortBy === 'name') res = (a.name || '').localeCompare(b.name || '');
    else if (sortBy === 'email') res = (a.email || '').localeCompare(b.email || '');
    else if (sortBy === 'role') res = (a.role || '').localeCompare(b.role || '');
    else if (sortBy === 'capacity') res = (a.base_capacity || 0) - (b.base_capacity || 0);
    return sortDir === 'asc' ? res : -res;
  });

  const paginatedUsers = sortedUsers.slice((userPage - 1) * ITEMS_PER_PAGE, userPage * ITEMS_PER_PAGE);

  const inputClasses = "w-full mt-1.5 p-2.5 border border-slate-200 dark:border-zinc-800 rounded-xl bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none text-sm transition-colors";

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Loading user accounts...</div>;
  }

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">
      <ConfirmModal
        isOpen={!!deleteModal}
        title="Confirm User Deletion"
        message={`Are you sure you want to delete ${deleteModal?.name}? This action cannot be undone.`}
        onConfirm={executeDelete}
        onCancel={() => setDeleteModal(null)}
      />

      {/* HEADER BAR */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Users size={22} className="text-blue-500" /> User Management
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-0.5">
            Manage access roles, capacities, and active operational intervals.
          </p>
        </div>
        {!isReadOnly && (
          <button
            onClick={openCreatePanel}
            className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 shadow-sm transition-colors cursor-pointer"
          >
            <Plus size={16} /> Add User
          </button>
        )}
      </div>

      {/* SUB-TABS */}
      <div className="flex gap-6 mb-4 border-b border-slate-200 dark:border-zinc-800 overflow-x-auto whitespace-nowrap">
        <button
          onClick={() => { setUserTab('active'); setUserPage(1); }}
          className={`pb-2.5 font-bold text-sm border-b-2 transition-colors ${userTab === 'active' ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-zinc-300'}`}
        >
          Active Users ({users?.filter(u => !isOffboarded(u)).length || 0})
        </button>
        <button
          onClick={() => { setUserTab('offboarded'); setUserPage(1); }}
          className={`pb-2.5 font-bold text-sm border-b-2 transition-colors ${userTab === 'offboarded' ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-zinc-300'}`}
        >
          Offboarded Users ({users?.filter(u => isOffboarded(u)).length || 0})
        </button>
      </div>

      {/* TABLE CONTAINER */}
      <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col bg-white dark:bg-zinc-900">
        {/* DESKTOP TABLE */}
        <table className="hidden md:table w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-slate-50 dark:bg-zinc-950/50 border-b border-slate-200 dark:border-zinc-800 select-none">
            <tr>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('name')}>
                User Details <SortIcon column="name" />
              </th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('role')}>
                Role <SortIcon column="role" />
              </th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => handleSort('capacity')}>
                Capacity <SortIcon column="capacity" />
              </th>
              {!isReadOnly && (
                <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
            {paginatedUsers.map(u => (
              <tr key={u.id} className="hover:bg-slate-50/50 dark:hover:bg-zinc-800/30 transition-colors">
                <td className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-300 border border-slate-200 dark:border-zinc-700 flex items-center justify-center font-bold">
                      {u.name?.charAt(0).toUpperCase() || 'U'}
                    </div>
                    <div>
                      <div className="font-bold text-slate-900 dark:text-zinc-100">{u.name}</div>
                      <div className="text-xs text-slate-500 dark:text-zinc-500 mt-0.5">{u.email}</div>
                    </div>
                  </div>
                </td>
                <td className="p-4">
                  <div className="flex flex-col items-start gap-1">
                    <span className="px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 text-[11px] font-extrabold uppercase tracking-wider text-slate-700 dark:text-zinc-300">
                      {u.role.replace('_', ' ')}
                    </span>
                    {u.role === 'maintainer' && u.service_lane_id && (
                      <span className="px-2 py-0.5 rounded bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 text-[10px] font-bold border border-purple-200 dark:border-purple-800">
                        {getServiceLaneName(u.service_lane_id)}
                      </span>
                    )}
                    {u.end_year && (
                      <span className="px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/30 border border-red-200 dark:border-red-800 text-[10px] font-extrabold uppercase tracking-wider text-red-700 dark:text-red-400">
                        Offboarded (W{u.end_week}/{u.end_year})
                      </span>
                    )}
                  </div>
                </td>
                <td className="p-4 font-medium text-slate-700 dark:text-zinc-300">
                  {u.base_capacity} cr/wk
                </td>
                  {!isReadOnly && (
                    <td className="p-4 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => openEditPanel(u)}
                          className="text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 p-2 rounded-xl transition-colors cursor-pointer"
                          title="Edit User"
                        >
                          <Edit2 size={16} />
                        </button>
                        <button
                          onClick={() => setDeleteModal({ isOpen: true, id: u.id, name: u.name })}
                          className="text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 p-2 rounded-xl transition-colors cursor-pointer"
                          title="Delete User"
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
          {paginatedUsers.map(u => (
            <div key={u.id} className="p-4 flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-300 flex items-center justify-center font-bold shrink-0">
                  {u.name?.charAt(0).toUpperCase() || 'U'}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-slate-900 dark:text-zinc-100 truncate">{u.name}</div>
                  <div className="text-xs text-slate-500 truncate">{u.email}</div>
                </div>
              </div>
              <div className="flex justify-between items-center bg-slate-50 dark:bg-zinc-950 p-2.5 rounded-xl border border-slate-100 dark:border-zinc-800">
                <div className="flex flex-col items-start gap-1">
                  <span className="px-2.5 py-0.5 rounded-full bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 text-[10px] font-extrabold uppercase tracking-wider text-slate-700 dark:text-zinc-300">
                    {u.role.replace('_', ' ')}
                  </span>
                  {u.role === 'maintainer' && u.service_lane_id && (
                    <span className="px-2 py-0.5 rounded bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 text-[10px] font-bold border border-purple-200 dark:border-purple-800">
                      {getServiceLaneName(u.service_lane_id)}
                    </span>
                  )}
                </div>
                <span className="font-bold text-xs text-slate-700 dark:text-zinc-300">{u.base_capacity} cr/wk</span>
              </div>
              {!isReadOnly && (
                <div className="flex justify-end gap-2 mt-1">
                  <button
                    onClick={() => openEditPanel(u)}
                    className="text-slate-600 dark:text-zinc-300 bg-slate-100 dark:bg-zinc-800 p-2 rounded-xl flex-1 flex justify-center items-center font-bold text-xs gap-1"
                  >
                    <Edit2 size={14} /> Edit
                  </button>
                  <button
                    onClick={() => setDeleteModal({ isOpen: true, id: u.id, name: u.name })}
                    className="text-red-600 bg-red-50 dark:bg-red-900/20 p-2 rounded-xl flex-1 flex justify-center items-center font-bold text-xs gap-1"
                  >
                    <Trash2 size={14} /> Delete
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        {displayUsers.length === 0 && (
          <div className="p-12 text-center text-sm text-slate-500 dark:text-zinc-500">
            No {userTab} users found.
          </div>
        )}

        {/* PAGINATION FOOTER */}
        {displayUsers.length > 0 && (
          <div className="px-4 py-3.5 border-t border-slate-200 dark:border-zinc-800 flex flex-col sm:flex-row justify-between items-center gap-3 bg-slate-50/50 dark:bg-zinc-950/50 text-xs font-medium">
            <span className="text-slate-500">
              Page <strong className="text-slate-800 dark:text-zinc-200">{userPage}</strong> of <strong className="text-slate-800 dark:text-zinc-200">{Math.ceil(displayUsers.length / ITEMS_PER_PAGE) || 1}</strong>
            </span>
            <div className="flex gap-2 w-full sm:w-auto">
              <button
                onClick={() => setUserPage(p => Math.max(1, p - 1))}
                disabled={userPage === 1}
                className="flex-1 sm:flex-none px-4 py-1.5 border border-slate-200 dark:border-zinc-800 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors bg-white dark:bg-zinc-900"
              >
                Previous
              </button>
              <button
                onClick={() => setUserPage(p => p + 1)}
                disabled={userPage >= Math.ceil(displayUsers.length / ITEMS_PER_PAGE)}
                className="flex-1 sm:flex-none px-4 py-1.5 border border-slate-200 dark:border-zinc-800 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-40 transition-colors bg-white dark:bg-zinc-900"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* STANDARDIZED RIGHT SLIDE-OVER FORM PANEL */}
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
                  {editUserId ? 'Edit User Account' : 'Create User Account'}
                </h3>
                <button
                  onClick={closePanel}
                  className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                >
                  <X size={18} />
                </button>
              </div>

              {/* PANEL BODY (SCROLLABLE FORM) */}
              <form onSubmit={submitUser} className="flex-1 p-6 overflow-y-auto space-y-4">
                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                    Full Name
                  </label>
                  <input
                    type="text"
                    className={inputClasses}
                    value={userForm.name}
                    onChange={e => setUserForm({ ...userForm, name: e.target.value })}
                    required
                    placeholder="e.g. John Doe"
                  />
                </div>

                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                    Email Address
                  </label>
                  <input
                    type="email"
                    disabled={!!editUserId}
                    className={`${inputClasses} disabled:opacity-50 disabled:cursor-not-allowed`}
                    value={userForm.email}
                    onChange={e => setUserForm({ ...userForm, email: e.target.value })}
                    required
                    placeholder="e.g. john@company.com"
                  />
                </div>

                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                    System Role
                  </label>
                  <select
                    className={inputClasses}
                    value={userForm.role}
                    onChange={e => setUserForm({ ...userForm, role: e.target.value, service_lane_id: e.target.value === 'maintainer' ? userForm.service_lane_id : '' })}
                  >
                    <option value="read_only">Read Only</option>
                    <option value="pentester">Pentester</option>
                    <option value="maintainer">Maintainer</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>

                {userForm.role === 'maintainer' && (
                  <div className="animate-in fade-in slide-in-from-top-1">
                    <label className="text-xs font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wider flex items-center gap-1">
                      Assigned Service Lane
                    </label>
                    <select
                      className={`${inputClasses} border-blue-300 dark:border-blue-800 focus:ring-blue-500`}
                      value={userForm.service_lane_id}
                      onChange={e => setUserForm({ ...userForm, service_lane_id: e.target.value })}
                      required
                    >
                      <option value="">-- Select Service Lane --</option>
                      {services.map(s => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                  </div>
                )}

                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                    Location Base
                  </label>
                  <select
                    className={inputClasses}
                    value={userForm.location_id}
                    onChange={e => setUserForm({ ...userForm, location_id: e.target.value })}
                    required
                  >
                    <option value="">-- Select Location --</option>
                    {locations?.map(loc => (
                      <option key={loc.id} value={loc.id}>{loc.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                    Base Capacity (Credits / Week)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    className={inputClasses}
                    value={userForm.base_capacity}
                    onChange={e => setUserForm({ ...userForm, base_capacity: parseFloat(e.target.value) })}
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-3 pt-2">
                  <div>
                    <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                      Start Year
                    </label>
                    <input
                      type="number"
                      className={inputClasses}
                      value={userForm.start_year}
                      onChange={e => setUserForm({ ...userForm, start_year: parseInt(e.target.value) })}
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">
                      Start Week
                    </label>
                    <input
                      type="number"
                      className={inputClasses}
                      value={userForm.start_week}
                      onChange={e => setUserForm({ ...userForm, start_week: parseInt(e.target.value) })}
                      required
                    />
                  </div>
                </div>

                <div className="p-4 bg-slate-50 dark:bg-zinc-950/80 rounded-2xl border border-slate-200 dark:border-zinc-800 space-y-3 mt-4">
                  <span className="text-xs font-bold text-slate-700 dark:text-zinc-300 block">
                    Offboard Interval (Optional)
                  </span>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[10px] font-bold text-slate-400 uppercase">Offboard Year</label>
                      <input
                        type="number"
                        className={inputClasses}
                        value={userForm.end_year}
                        onChange={e => setUserForm({ ...userForm, end_year: e.target.value })}
                        placeholder="Active"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] font-bold text-slate-400 uppercase">Offboard Week</label>
                      <input
                        type="number"
                        className={inputClasses}
                        value={userForm.end_week}
                        onChange={e => setUserForm({ ...userForm, end_week: e.target.value })}
                        placeholder="Active"
                      />
                    </div>
                  </div>
                </div>

                {/* PANEL FOOTER ACTIONS */}
                <div className="pt-6 border-t border-slate-100 dark:border-zinc-800 flex justify-end gap-3">
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
                    {editUserId ? 'Update User' : 'Create User'}
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