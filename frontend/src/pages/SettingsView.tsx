import { useState } from 'react';
import { useSettings } from '../hooks/useSettings';
import TopNav from '../components/TopNav';
import ConfirmModal from '../components/Modals/ConfirmModal';
import { Toaster } from 'react-hot-toast';
import { Users, MapPin, Activity, Tags, Globe, Flag, Server, Trash2, Download, AlertTriangle, Plus, Database, Terminal, Edit2 } from 'lucide-react';

export default function SettingsView() {
  const {
    activeTab, setActiveTab,
    users, locations, services, categories, regions, countries, logs, dbLatency, isLoading,
    handleSave, handleDelete, downloadLog, handleWipeSystem
  } = useSettings();

  const [showForm, setShowForm] = useState<string | null>(null);

  // Global Delete Confirmation State
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; endpoint: string; id: string; name: string } | null>(null);

  const defaultUserForm = { email: '', name: '', role: 'read_only', base_capacity: 1.0, location_id: '', start_week: 1, start_year: new Date().getFullYear(), end_week: '', end_year: '' };
  const [userForm, setUserForm] = useState(defaultUserForm);
  const [editUserId, setEditUserId] = useState<string | null>(null);

  const defaultLocForm = { name: '', is_active: true };
  const [locForm, setLocForm] = useState(defaultLocForm);
  const [editLocId, setEditLocId] = useState<string | null>(null);

  const defaultServiceForm = { name: '', theme_color: '#3b82f6', default_credits: 2.0, default_duration_weeks: 1, max_concurrent_per_week: 5, match_keywords: '', display_order: 99, is_active: true };
  const [serviceForm, setServiceForm] = useState(defaultServiceForm);
  const [editServiceId, setEditServiceId] = useState<string | null>(null);

  const defaultCatForm = { name: '', target_goal: 0, service_lane_id: '' };
  const [catForm, setCatForm] = useState(defaultCatForm);
  const [editCatId, setEditCatId] = useState<string | null>(null);

  const defaultRegionForm = { name: '', is_active: true };
  const [regionForm, setRegionForm] = useState(defaultRegionForm);
  const [editRegionId, setEditRegionId] = useState<string | null>(null);

  const defaultCountryForm = { code: '', name: '', region_id: '', is_active: true };
  const [countryForm, setCountryForm] = useState(defaultCountryForm);
  const [editCountryId, setEditCountryId] = useState<string | null>(null);;

  const [nukeModalOpen, setNukeModalOpen] = useState(false);
  const [nukeText, setNukeText] = useState("");

  const confirmDelete = (endpoint: string, id: string, name: string) => {
    setDeleteModal({ isOpen: true, endpoint, id, name });
  };

  const executeDelete = async () => {
    if (!deleteModal) return;
    await handleDelete(deleteModal.endpoint, deleteModal.id);
    setDeleteModal(null);
  };

  const submitUser = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = { ...userForm, location_id: userForm.location_id === '' ? null : userForm.location_id, end_week: userForm.end_week === '' ? null : parseInt(userForm.end_week as string), end_year: userForm.end_year === '' ? null : parseInt(userForm.end_year as string) };
    if (await handleSave('/api/users/', payload, !!editUserId, editUserId)) { setShowForm(null); setEditUserId(null); setUserForm(defaultUserForm); }
  };

  const submitLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await handleSave('/api/locations/', locForm, !!editLocId, editLocId)) { setShowForm(null); setEditLocId(null); setLocForm(defaultLocForm); }
  };

  const submitService = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      ...serviceForm,
      match_keywords: typeof serviceForm.match_keywords === 'string' ? serviceForm.match_keywords.split(',').map(s => s.trim()) : serviceForm.match_keywords
    };
    if (await handleSave('/api/services/', payload, !!editServiceId, editServiceId)) { setShowForm(null); setEditServiceId(null); setServiceForm(defaultServiceForm); }
  };

  const submitCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = { ...catForm, service_lane_id: catForm.service_lane_id === '' ? null : catForm.service_lane_id };
    if (await handleSave('/api/board/categories/', payload, !!editCatId, editCatId)) { setShowForm(null); setEditCatId(null); setCatForm(defaultCatForm); }
  };

  const submitRegion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await handleSave('/api/regions/', regionForm, !!editRegionId, editRegionId)) { setShowForm(null); setEditRegionId(null); setRegionForm(defaultRegionForm); }
  };

  const submitCountry = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = { ...countryForm, region_id: countryForm.region_id === '' ? null : countryForm.region_id };
    if (await handleSave('/api/countries/', payload, !!editCountryId, editCountryId)) { setShowForm(null); setEditCountryId(null); setCountryForm(defaultCountryForm); }
  };

  if (isLoading) return <div className="min-h-screen bg-slate-50 dark:bg-[#09090b] flex items-center justify-center text-slate-500 dark:text-zinc-500">Loading settings...</div>;

  const inputClasses = "w-full mt-1 p-2.5 border border-slate-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none";

  const renderSimpleList = (title: string, desc: string, data: any[], endpoint: string, formType: string, onEdit?: (item: any) => void) => (
    <div className="fade-in">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-zinc-100">{title}</h2>
          <p className="text-sm text-slate-500 dark:text-zinc-400">{desc}</p>
        </div>
        <button onClick={() => { setShowForm(formType); onEdit && onEdit(null); }} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors">
          <Plus size={16} /> Add {title.split(' ')[0]}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {data?.map((item: any) => (
          <div key={item.id} className="border border-slate-200 dark:border-zinc-800 p-5 rounded-2xl flex justify-between items-start hover:border-blue-500 dark:hover:border-blue-500 transition-colors bg-white dark:bg-zinc-900 shadow-sm hover:shadow-md">
            <div>
              <div className="font-bold text-lg text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                {item.theme_color && <div className="w-4 h-4 rounded-full shadow-sm" style={{backgroundColor: item.theme_color}}></div>}
                {item.name || item.code || item.regions}
              </div>

              <div className="mt-2 space-y-1">
                {item.region_name && <div className="text-sm text-slate-500 dark:text-zinc-400 font-medium">Region: <span className="text-slate-900 dark:text-zinc-200">{item.region_name}</span></div>}
                {item.target_goal !== undefined && <div className="text-sm text-slate-500 dark:text-zinc-400 font-medium">Target Goal: <span className="text-slate-900 dark:text-zinc-200">{item.target_goal}</span></div>}
                {item.default_credits !== undefined && <div className="text-sm text-slate-500 dark:text-zinc-400 font-medium">Credits: <span className="text-slate-900 dark:text-zinc-200">{item.default_credits}cr</span> / Duration: <span className="text-slate-900 dark:text-zinc-200">{item.default_duration_weeks}w</span></div>}
              </div>

              <div className="mt-4 px-2.5 py-1 rounded-full bg-emerald-100 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 text-emerald-800 dark:text-emerald-400 text-[10px] font-extrabold uppercase tracking-wider w-fit shadow-sm">
                {item.is_active !== false ? 'Active' : 'Inactive'}
              </div>
            </div>
            <div className="flex flex-col gap-1">
              {onEdit && (
                <button onClick={() => onEdit(item)} className="text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-500/10 p-2 rounded-lg transition-colors">
                  <Edit2 size={18} />
                </button>
              )}
              <button onClick={() => confirmDelete(endpoint, item.id, item.name || item.code)} className="text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 p-2 rounded-lg transition-colors">
                <Trash2 size={18} />
              </button>
            </div>
          </div>
        ))}
        {(!data || data.length === 0) && (
          <div className="col-span-full p-12 text-center text-slate-500 dark:text-zinc-500 border-2 border-dashed border-slate-200 dark:border-zinc-800 rounded-2xl bg-slate-50/50 dark:bg-zinc-900/50">
            No records found. Click the button above to add one.
          </div>
        )}
      </div>
    </div>
  );

  const PREDEFINED_COLORS = [
    '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#10b981', '#14b8a6',
    '#06b6d4', '#3b82f6', '#6366f1', '#8b5cf6', '#a855f7', '#ec4899',
    '#f43f5e', '#64748b', '#000000', '#ffffff', '#cccccc', '#eeeeee'
  ];

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100 flex flex-col transition-colors duration-300">
      <TopNav />
      <Toaster position="bottom-right" />

      <ConfirmModal
        isOpen={!!deleteModal}
        title="Confirm Deletion"
        message={`Are you sure you want to delete ${deleteModal?.name}? This action cannot be undone.`}
        onConfirm={executeDelete}
        onCancel={() => setDeleteModal(null)}
      />

      {nukeModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 w-full max-w-md shadow-2xl animate-in zoom-in-95">
            <div className="flex items-start gap-4">
              <div className="bg-red-100 dark:bg-red-500/10 text-red-600 dark:text-red-400 p-3 rounded-full shrink-0 border border-red-200 dark:border-red-500/20">
                <AlertTriangle size={24} />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100">Factory Reset</h3>
                <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1">This will permanently delete all tests, assets, events, and assignments. Configurations and users will be kept.</p>
              </div>
            </div>
            <div className="mt-6">
              <label className="block text-sm font-bold text-slate-700 dark:text-zinc-300 mb-2">Type "NUKE" to confirm:</label>
              <input
                type="text"
                className={inputClasses}
                value={nukeText}
                onChange={(e) => setNukeText(e.target.value)}
                placeholder="NUKE"
              />
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => {setNukeModalOpen(false); setNukeText("");}} className="px-4 py-2 text-sm font-medium bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors">Cancel</button>
              <button
                onClick={() => { if(nukeText === 'NUKE') { handleWipeSystem(); setNukeModalOpen(false); setNukeText(""); } }}
                disabled={nukeText !== 'NUKE'}
                className="px-4 py-2 text-sm font-medium bg-red-600 hover:bg-red-700 disabled:bg-slate-300 dark:disabled:bg-zinc-800 text-white rounded-lg shadow-sm transition-colors"
              >
                Execute Reset
              </button>
            </div>
          </div>
        </div>
      )}

      <main className="flex-1 pt-32 pb-12 px-6 max-w-7xl mx-auto w-full flex flex-col md:flex-row gap-8">
        {/* Sidebar */}
        <aside className="w-full md:w-64 shrink-0">
          <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-3 shadow-sm sticky top-32">
            <h3 className="text-xs font-bold uppercase text-slate-400 dark:text-zinc-500 mb-3 px-3">Platform Settings</h3>
            <nav className="flex flex-col gap-1">
              <button onClick={() => { setActiveTab('users'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'users' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><Users size={18} /> Users</button>
              <button onClick={() => { setActiveTab('locations'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'locations' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><MapPin size={18} /> Locations</button>
              <button onClick={() => { setActiveTab('services'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'services' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><Activity size={18} /> Services</button>
              <button onClick={() => { setActiveTab('categories'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'categories' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><Tags size={18} /> Categories</button>
              <button onClick={() => { setActiveTab('regions'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'regions' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><Globe size={18} /> Regions</button>
              <button onClick={() => { setActiveTab('countries'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'countries' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><Flag size={18} /> Countries</button>
              <button onClick={() => { setActiveTab('system'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'system' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><Server size={18} /> System Logs</button>
            </nav>
          </div>
        </aside>

        {/* Content */}
        <section className="flex-1 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-8 shadow-sm min-h-[600px]">

          {/* USERS */}
          {activeTab === 'users' && (
            <div className="fade-in">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-zinc-100">User Management</h2>
                  <p className="text-sm text-slate-500 dark:text-zinc-400">Manage access roles, capacities, and active intervals.</p>
                </div>
                <button onClick={() => { setEditUserId(null); setUserForm(defaultUserForm); setShowForm('users'); }} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
                  <Plus size={16} /> Add User
                </button>
              </div>

              {showForm === 'users' && (
                <form onSubmit={submitUser} className="bg-slate-50 dark:bg-zinc-950/50 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 mb-8 space-y-4 shadow-inner">
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-2">{editUserId ? 'Edit User' : 'Create New User'}</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Name <input className={inputClasses} value={userForm.name} onChange={e => setUserForm({...userForm, name: e.target.value})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Email <input type="email" disabled={!!editUserId} className={`${inputClasses} disabled:opacity-50`} value={userForm.email} onChange={e => setUserForm({...userForm, email: e.target.value})} required /></label>

                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Role
                      <select className={inputClasses} value={userForm.role} onChange={e => setUserForm({...userForm, role: e.target.value})}>
                        <option value="read_only">Read Only</option>
                        <option value="pentester">Pentester</option>
                        <option value="admin">Admin</option>
                      </select>
                    </label>

                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Location
                      <select className={inputClasses} value={userForm.location_id} onChange={e => setUserForm({...userForm, location_id: e.target.value})} required>
                        <option value="">-- Select Location --</option>
                        {locations?.map(loc => <option key={loc.id} value={loc.id}>{loc.name}</option>)}
                      </select>
                    </label>

                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Capacity <input type="number" step="0.1" className={inputClasses} value={userForm.base_capacity} onChange={e => setUserForm({...userForm, base_capacity: parseFloat(e.target.value)})} required /></label>

                    <div className="flex gap-4">
                      <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 w-1/2">Start Year <input type="number" className={inputClasses} value={userForm.start_year} onChange={e => setUserForm({...userForm, start_year: parseInt(e.target.value)})} required /></label>
                      <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 w-1/2">Start Wk <input type="number" className={inputClasses} value={userForm.start_week} onChange={e => setUserForm({...userForm, start_week: parseInt(e.target.value)})} required /></label>
                    </div>

                    <div className="flex gap-4 col-span-1 md:col-span-2 bg-red-50/50 dark:bg-red-500/10 p-4 rounded-xl border border-red-100 dark:border-red-500/20">
                      <label className="text-sm font-bold w-1/2 text-red-800 dark:text-red-400">Offboard Year (Optional) <input type="number" className="w-full mt-1 p-2.5 border border-red-200 dark:border-red-500/30 rounded-lg bg-white dark:bg-zinc-950 focus:ring-2 focus:ring-red-500 outline-none" value={userForm.end_year} onChange={e => setUserForm({...userForm, end_year: e.target.value})} placeholder="Leave blank if active"/></label>
                      <label className="text-sm font-bold w-1/2 text-red-800 dark:text-red-400">Offboard Wk (Optional) <input type="number" className="w-full mt-1 p-2.5 border border-red-200 dark:border-red-500/30 rounded-lg bg-white dark:bg-zinc-950 focus:ring-2 focus:ring-red-500 outline-none" value={userForm.end_week} onChange={e => setUserForm({...userForm, end_week: e.target.value})} placeholder="Leave blank if active"/></label>
                    </div>
                  </div>
                  <div className="flex justify-end gap-3 pt-4 border-t border-slate-200 dark:border-zinc-800">
                    <button type="button" onClick={() => {setShowForm(null); setEditUserId(null);}} className="px-5 py-2.5 text-sm font-medium bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors">Cancel</button>
                    <button type="submit" className="px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors">{editUserId ? 'Update User' : 'Save User'}</button>
                  </div>
                </form>
              )}

              <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800">
                    <tr>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">User Details</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Role</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Capacity</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                    {users?.map(u => (
                      <tr key={u.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors">
                        <td className="p-4">
                          <div className="flex items-center gap-3">
                            {u.avatar_url ? (
                              <img src={u.avatar_url} alt={u.name} className="w-9 h-9 rounded-full border border-slate-200 dark:border-zinc-700" />
                            ) : (
                              <div className="w-9 h-9 rounded-full bg-slate-200 dark:bg-zinc-800 text-slate-500 dark:text-zinc-400 flex items-center justify-center font-bold">
                                {u.name.charAt(0)}
                              </div>
                            )}
                            <div>
                              <div className="font-bold text-base text-slate-900 dark:text-zinc-100">{u.name}</div>
                              <div className="text-slate-500 dark:text-zinc-500 mt-0.5">{u.email}</div>
                            </div>
                          </div>
                        </td>
                        <td className="p-4 flex flex-col items-start gap-1.5">
                          <span className="px-2.5 py-1 rounded-full bg-slate-100 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 text-[11px] font-extrabold uppercase tracking-wider text-slate-700 dark:text-zinc-300">
                            {u.role.replace('_', ' ')}
                          </span>
                          {/* Visually indicate if a user was soft-deleted/offboarded */}
                          {u.end_year && (
                             <span className="px-2.5 py-1 rounded-full bg-red-100 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-[10px] font-extrabold uppercase tracking-wider text-red-700 dark:text-red-400">
                               Offboarded (W{u.end_week}/{u.end_year})
                             </span>
                          )}
                        </td>
                        <td className="p-4 font-medium text-slate-700 dark:text-zinc-300">{u.base_capacity} cr/wk</td>
                        <td className="p-4 text-right">
                          <div className="flex justify-end gap-2">
                            <button onClick={() => {
                              setEditUserId(u.id);
                              setUserForm({
                                email: u.email, name: u.name, role: u.role, base_capacity: u.base_capacity,
                                location_id: u.location_id || '', start_week: u.start_week || 1, start_year: u.start_year || new Date().getFullYear(),
                                end_week: u.end_week || '', end_year: u.end_year || ''
                              });
                              setShowForm('users');
                            }} className="text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-500/10 p-2 rounded-lg transition-colors">
                              <Edit2 size={18} />
                            </button>
                            <button onClick={() => confirmDelete('/api/users/', u.id, u.name)} className="text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 p-2 rounded-lg transition-colors">
                              <Trash2 size={18} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(!users || users.length === 0) && <div className="p-12 text-center text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-900/50">No users found.</div>}
              </div>
            </div>
          )}

          {/* LOCATIONS (Now a Table!) */}
          {activeTab === 'locations' && (
            <div className="fade-in">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-zinc-100">Locations</h2>
                  <p className="text-sm text-slate-500 dark:text-zinc-400">Geographic bases for calculating national holidays.</p>
                </div>
                <button onClick={() => { setEditLocId(null); setLocForm(defaultLocForm); setShowForm('locations'); }} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
                  <Plus size={16} /> Add Location
                </button>
              </div>

              {showForm === 'locations' && (
                <form onSubmit={submitLocation} className="bg-slate-50 dark:bg-zinc-950/50 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 mb-8 shadow-inner">
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-4">{editLocId ? 'Edit Location' : 'Add Location'}</h3>
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 block mb-6">Location Name <input className={inputClasses} value={locForm.name} onChange={e => setLocForm({...locForm, name: e.target.value})} required placeholder="e.g. London" /></label>
                  <div className="flex justify-end gap-3 border-t border-slate-200 dark:border-zinc-800 pt-4">
                    <button type="button" onClick={() => {setShowForm(null); setEditLocId(null);}} className="px-5 py-2.5 text-sm font-medium bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors">Cancel</button>
                    <button type="submit" className="px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors">{editLocId ? 'Update Location' : 'Save Location'}</button>
                  </div>
                </form>
              )}

              <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800">
                    <tr>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Location Name</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                    {locations?.map(loc => (
                      <tr key={loc.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors">
                        <td className="p-4 font-bold text-base text-slate-900 dark:text-zinc-100">{loc.name}</td>
                        <td className="p-4 text-right">
                          <div className="flex justify-end gap-2">
                            <button onClick={() => {
                              setEditLocId(loc.id);
                              setLocForm({ name: loc.name, is_active: loc.is_active });
                              setShowForm('locations');
                            }} className="text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-500/10 p-2 rounded-lg transition-colors">
                              <Edit2 size={18} />
                            </button>
                            <button onClick={() => confirmDelete('/api/locations/', loc.id, loc.name)} className="text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 p-2 rounded-lg transition-colors">
                              <Trash2 size={18} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(!locations || locations.length === 0) && <div className="p-12 text-center text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-900/50">No locations found.</div>}
              </div>
            </div>
          )}

          {/* SERVICES (Color picker crash fixed via Uncontrolled Input) */}
          {activeTab === 'services' && (
            <div>
              {renderSimpleList('Dynamic Service Lanes', 'Define distinct testing lanes, default credits, and visual themes.', services, '/api/services/', 'services', (item) => {
                if (item) {
                  setEditServiceId(item.id);
                  setServiceForm({
                    name: item.name, theme_color: item.theme_color, default_credits: item.default_credits,
                    default_duration_weeks: item.default_duration_weeks, max_concurrent_per_week: item.max_concurrent_per_week || 5,
                    match_keywords: item.match_keywords || '', display_order: item.display_order, is_active: item.is_active
                  });
                  setShowForm('services');
                } else {
                  setEditServiceId(null);
                  setServiceForm(defaultServiceForm);
                }
              })}

              {showForm === 'services' && (
                <form onSubmit={submitService} className="bg-slate-50 dark:bg-zinc-950/50 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 my-6 space-y-4 shadow-inner">
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-2">{editServiceId ? 'Edit Service Lane' : 'Add Service Lane'}</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Name <input className={inputClasses} value={serviceForm.name} onChange={e => setServiceForm({...serviceForm, name: e.target.value})} required /></label>
                    <div className="text-sm font-bold text-slate-700 dark:text-zinc-300">
                      Theme Color
                      <div className="mt-2 flex flex-col gap-3">
                        {/* 1. Clickable Palette */}
                        <div className="flex flex-wrap gap-2 p-3 bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg">
                          {PREDEFINED_COLORS.map(color => (
                            <button
                              key={color}
                              type="button"
                              onClick={() => setServiceForm({ ...serviceForm, theme_color: color })}
                              className={`w-6 h-6 rounded-full border-2 transition-all hover:scale-110 ${serviceForm.theme_color.toLowerCase() === color ? 'border-slate-900 dark:border-white scale-110 shadow-md' : 'border-transparent shadow-sm'}`}
                              style={{ backgroundColor: color }}
                              title={color}
                            />
                          ))}
                        </div>
                        {/* 2. Manual Hex Code Input & Preview */}
                        <div className="flex items-center gap-3">
                          <input
                            type="text"
                            className={`${inputClasses} !mt-0 font-mono uppercase w-32`}
                            value={serviceForm.theme_color}
                            onChange={e => setServiceForm({...serviceForm, theme_color: e.target.value})}
                            placeholder="#3B82F6"
                            maxLength={7}
                            pattern="^#[0-9A-Fa-f]{6}$"
                            required
                          />
                          <div
                            className="w-10 h-10 rounded-lg shadow-inner border border-slate-200 dark:border-zinc-700 shrink-0 transition-colors"
                            style={{ backgroundColor: serviceForm.theme_color.length === 7 ? serviceForm.theme_color : 'transparent' }}
                          ></div>
                        </div>
                      </div>
                    </div>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Default Credits <input type="number" step="0.1" className={inputClasses} value={serviceForm.default_credits} onChange={e => setServiceForm({...serviceForm, default_credits: parseFloat(e.target.value)})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Default Duration (Wks) <input type="number" className={inputClasses} value={serviceForm.default_duration_weeks} onChange={e => setServiceForm({...serviceForm, default_duration_weeks: parseInt(e.target.value)})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 col-span-1 md:col-span-2">Match Keywords (comma separated) <input className={inputClasses} value={serviceForm.match_keywords} onChange={e => setServiceForm({...serviceForm, match_keywords: e.target.value})} placeholder="e.g. web, dast, external" /></label>
                  </div>
                  <div className="flex justify-end gap-3 pt-4 border-t border-slate-200 dark:border-zinc-800">
                    <button type="button" onClick={() => {setShowForm(null); setEditServiceId(null);}} className="px-5 py-2.5 text-sm font-medium bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors">Cancel</button>
                    <button type="submit" className="px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors">{editServiceId ? 'Update' : 'Save'}</button>
                  </div>
                </form>
              )}
            </div>
          )}

          {/* CATEGORIES (Table View) */}
          {activeTab === 'categories' && (
            <div className="fade-in">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-zinc-100">Service Forecasts</h2>
                  <p className="text-sm text-slate-500 dark:text-zinc-400">Specific target goals mapped to service lanes.</p>
                </div>
                <button onClick={() => { setEditCatId(null); setCatForm(defaultCatForm); setShowForm('categories'); }} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors">
                  <Plus size={16} /> Add Category
                </button>
              </div>

              {showForm === 'categories' && (
                <form onSubmit={submitCategory} className="bg-slate-50 dark:bg-zinc-950/50 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 mb-8 space-y-4 shadow-inner">
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-2">{editCatId ? 'Edit Category' : 'Add Category'}</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 col-span-1 md:col-span-2">Name <input className={inputClasses} value={catForm.name} onChange={e => setCatForm({...catForm, name: e.target.value})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Target Goal <input type="number" className={inputClasses} value={catForm.target_goal} onChange={e => setCatForm({...catForm, target_goal: parseInt(e.target.value)})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Link to Service Lane
                      <select className={inputClasses} value={catForm.service_lane_id} onChange={e => setCatForm({...catForm, service_lane_id: e.target.value})}>
                        <option value="">-- None --</option>
                        {services?.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                      </select>
                    </label>
                  </div>
                  <div className="flex justify-end gap-3 pt-4 border-t border-slate-200 dark:border-zinc-800">
                    <button type="button" onClick={() => {setShowForm(null); setEditCatId(null);}} className="px-5 py-2.5 text-sm font-medium bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors">Cancel</button>
                    <button type="submit" className="px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors">{editCatId ? 'Update Category' : 'Save Category'}</button>
                  </div>
                </form>
              )}

              <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800">
                    <tr>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Category Name</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Target Goal</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Service Lane</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                    {categories?.map(c => (
                      <tr key={c.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors">
                        <td className="p-4 font-bold text-slate-900 dark:text-zinc-100">{c.name}</td>
                        <td className="p-4 text-slate-700 dark:text-zinc-300 font-medium">{c.target_goal}</td>
                        <td className="p-4">
                          <span className="px-2.5 py-1 rounded-full bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/20 text-blue-700 dark:text-blue-400 text-xs font-bold shadow-sm">
                            {c.service_lane_name || 'Unlinked'}
                          </span>
                        </td>
                        <td className="p-4 text-right">
                          <div className="flex justify-end gap-2">
                            <button onClick={() => {
                              setEditCatId(c.id);
                              setCatForm({ name: c.name, target_goal: c.target_goal, service_lane_id: c.service_lane_id || '' });
                              setShowForm('categories');
                            }} className="text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-500/10 p-2 rounded-lg transition-colors"><Edit2 size={18} /></button>
                            <button onClick={() => confirmDelete('/api/board/categories/', c.id, c.name)} className="text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 p-2 rounded-lg transition-colors"><Trash2 size={18} /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(!categories || categories.length === 0) && <div className="p-12 text-center text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-900/50">No categories found.</div>}
              </div>
            </div>
          )}

          {/* REGIONS (Table View) */}
          {activeTab === 'regions' && (
            <div className="fade-in">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-zinc-100">Regions</h2>
                  <p className="text-sm text-slate-500 dark:text-zinc-400">Broad operational boundaries.</p>
                </div>
                <button onClick={() => { setEditRegionId(null); setRegionForm(defaultRegionForm); setShowForm('regions'); }} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors">
                  <Plus size={16} /> Add Region
                </button>
              </div>

              {showForm === 'regions' && (
                <form onSubmit={submitRegion} className="bg-slate-50 dark:bg-zinc-950/50 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 mb-8 shadow-inner">
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-4">{editRegionId ? 'Edit Region' : 'Add Region'}</h3>
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 block mb-6">Region Name <input className={inputClasses} value={regionForm.name} onChange={e => setRegionForm({...regionForm, name: e.target.value})} required /></label>
                  <div className="flex justify-end gap-3 border-t border-slate-200 dark:border-zinc-800 pt-4">
                    <button type="button" onClick={() => {setShowForm(null); setEditRegionId(null);}} className="px-5 py-2.5 text-sm font-medium bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors">Cancel</button>
                    <button type="submit" className="px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors">{editRegionId ? 'Update Region' : 'Save Region'}</button>
                  </div>
                </form>
              )}

              <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800">
                    <tr>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Region Name</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                    {regions?.map(r => (
                      <tr key={r.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors">
                        <td className="p-4 font-bold text-base text-slate-900 dark:text-zinc-100">{r.name}</td>
                        <td className="p-4 text-right">
                          <div className="flex justify-end gap-2">
                            <button onClick={() => {
                              setEditRegionId(r.id);
                              setRegionForm({ name: r.name, is_active: r.is_active });
                              setShowForm('regions');
                            }} className="text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-500/10 p-2 rounded-lg transition-colors"><Edit2 size={18} /></button>
                            <button onClick={() => confirmDelete('/api/regions/', r.id, r.name)} className="text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 p-2 rounded-lg transition-colors"><Trash2 size={18} /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(!regions || regions.length === 0) && <div className="p-12 text-center text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-900/50">No regions found.</div>}
              </div>
            </div>
          )}

          {/* COUNTRIES (Table View) */}
          {activeTab === 'countries' && (
            <div className="fade-in">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-zinc-100">Countries</h2>
                  <p className="text-sm text-slate-500 dark:text-zinc-400">Manage operating countries and analytics mappings.</p>
                </div>
                <button onClick={() => { setEditCountryId(null); setCountryForm(defaultCountryForm); setShowForm('countries'); }} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors">
                  <Plus size={16} /> Add Country
                </button>
              </div>

              {showForm === 'countries' && (
                <form onSubmit={submitCountry} className="bg-slate-50 dark:bg-zinc-950/50 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 mb-8 space-y-4 shadow-inner">
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-2">{editCountryId ? 'Edit Country' : 'Add Country'}</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Code (e.g. US) <input className={inputClasses} value={countryForm.code} onChange={e => setCountryForm({...countryForm, code: e.target.value.toUpperCase()})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Name <input className={inputClasses} value={countryForm.name} onChange={e => setCountryForm({...countryForm, name: e.target.value})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 col-span-1 md:col-span-2">Region
                      <select className={inputClasses} value={countryForm.region_id} onChange={e => setCountryForm({...countryForm, region_id: e.target.value})}>
                        <option value="">-- None --</option>
                        {regions?.map(r => <option key={r.id} value={r.id}>{r.name || r.regions}</option>)}
                      </select>
                    </label>
                  </div>
                  <div className="flex justify-end gap-3 pt-4 border-t border-slate-200 dark:border-zinc-800">
                    <button type="button" onClick={() => {setShowForm(null); setEditCountryId(null);}} className="px-5 py-2.5 text-sm font-medium bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors">Cancel</button>
                    <button type="submit" className="px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors">{editCountryId ? 'Update Country' : 'Save Country'}</button>
                  </div>
                </form>
              )}

              <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800">
                    <tr>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Code</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Country Name</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Region Mapping</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                    {countries?.map(c => (
                      <tr key={c.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors">
                        <td className="p-4 text-slate-500 dark:text-zinc-400 font-mono font-bold">{c.code}</td>
                        <td className="p-4 font-bold text-slate-900 dark:text-zinc-100">{c.name}</td>
                        <td className="p-4">
                          <span className="px-2.5 py-1 rounded-full bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 text-indigo-700 dark:text-indigo-400 text-xs font-bold shadow-sm">
                            {c.region_name || 'Unmapped'}
                          </span>
                        </td>
                        <td className="p-4 text-right">
                          <div className="flex justify-end gap-2">
                            <button onClick={() => {
                              setEditCountryId(c.id);
                              setCountryForm({ code: c.code, name: c.name, region_id: c.region_id || '', is_active: c.is_active });
                              setShowForm('countries');
                            }} className="text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-500/10 p-2 rounded-lg transition-colors"><Edit2 size={18} /></button>
                            <button onClick={() => confirmDelete('/api/countries/', c.id, c.name)} className="text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 p-2 rounded-lg transition-colors"><Trash2 size={18} /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(!countries || countries.length === 0) && <div className="p-12 text-center text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-900/50">No countries found.</div>}
              </div>
            </div>
          )}

          {/* SYSTEM LOGS */}
          {activeTab === 'system' && (
            <div className="space-y-8 fade-in">
              <div>
                <h2 className="text-xl font-bold text-slate-900 dark:text-zinc-100 mb-4 flex items-center gap-2"><Database size={20} className="text-blue-500"/> Infrastructure Logic</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 flex justify-between items-center bg-slate-50 dark:bg-zinc-900 shadow-sm">
                    <span className="font-bold text-slate-700 dark:text-zinc-300">PostgreSQL Primary</span>

                    {dbLatency !== null ? (
                      <span className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400 font-extrabold uppercase tracking-wider bg-emerald-100 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 px-3 py-1.5 rounded-full">
                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                        Connected ({dbLatency}ms)
                      </span>
                    ) : (
                      <span className="flex items-center gap-2 text-sm text-red-700 dark:text-red-400 font-extrabold uppercase tracking-wider bg-red-100 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 px-3 py-1.5 rounded-full">
                        <div className="w-2 h-2 rounded-full bg-red-500"></div>
                        Offline
                      </span>
                    )}

                  </div>
                </div>
              </div>

              <div>
                <h2 className="text-xl font-bold text-slate-900 dark:text-zinc-100 mb-4 flex items-center gap-2"><Terminal size={20} className="text-slate-500 dark:text-zinc-400"/> Security Audit Logs</h2>
                <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm bg-white dark:bg-zinc-900">
                  {(!logs || logs?.length === 0) ? <div className="p-12 text-center text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-950/50">No text logs generated yet in the backend /logs folder.</div> :
                    <ul className="divide-y divide-slate-100 dark:divide-zinc-800">
                      {logs.map(log => (
                        <li key={log} className="p-4 flex justify-between items-center hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors">
                          <span className="font-mono text-sm font-medium text-slate-700 dark:text-zinc-300">{log}</span>
                          <div className="flex gap-2">
                            <button onClick={() => downloadLog(log)} className="text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-500/10 px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-bold transition-colors"><Download size={16} /> Download</button>
                            {/* Reusing our awesome Confirm Modal for Log Deletion! */}
                            <button onClick={() => confirmDelete('/api/system/logs/', log, log)} className="text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-bold transition-colors"><Trash2 size={16} /> Delete</button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  }
                </div>
              </div>
              <div className="pt-6 border-t border-slate-200 dark:border-zinc-800">
                <h2 className="text-xl font-bold text-red-600 dark:text-red-500 mb-2 flex items-center gap-2"><AlertTriangle size={20} /> Danger Zone</h2>
                <button onClick={() => setNukeModalOpen(true)} className="bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-8 rounded-xl shadow-sm mt-4 transition-colors focus:ring-4 focus:ring-red-500/20">Execute Factory Reset</button>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}