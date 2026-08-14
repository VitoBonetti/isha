import axios from "axios";
import { useState, useEffect } from 'react';
import { useSettings } from '../hooks/useSettings';
import TopNav from '../components/TopNav';
import ConfirmModal from '../components/Modals/ConfirmModal';
import toast, { Toaster } from 'react-hot-toast';
import { Key, Users, MapPin, Activity, Tags, Globe, Flag, Server, Trash2, Download, AlertTriangle, Plus, Database, Terminal, Edit2, LayoutTemplate, ChevronsUpDown, ChevronUp, ChevronDown, FolderClosed } from 'lucide-react';

// Sleek Custom Toggle Component
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

export default function SettingsView() {
  const {
    activeTab, setActiveTab,
    users, locations, services, categories, regions, countries, logs, dbLatency, isLoading, assetTypes,
    handleSave, handleDelete, downloadLog, handleWipeSystem
  } = useSettings();

  const [showForm, setShowForm] = useState<string | null>(null);
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; endpoint: string; id: string; name: string } | null>(null);
  const [actionModal, setActionModal] = useState<{isOpen: boolean, title: string, message: string, confirmText: string, variant: 'danger'|'warning', onConfirm: () => void} | null>(null);

  // Add the state for the server time near the top of the component
  const [serverTime, setServerTime] = useState({ year: new Date().getFullYear(), week: 1 });

  useEffect(() => {
    axios.get('/api/users/system/time')
      .then(res => setServerTime(res.data))
      .catch(console.error);
  }, []);

  // ServiceNow Sync State
  const [isSyncing, setIsSyncing] = useState(false);

  const handleSnowSync = async () => {
    setIsSyncing(true);
    const startTime = new Date().getTime();

    const loadingToastId = toast.loading("ServiceNow sync initiated. Fetching and mapping data in the background...");

    try {
      await axios.post('/api/assets/servicenow', {});

      const pollInterval = setInterval(async () => {
        try {
          const logsRes = await axios.get('/api/system/logs/');
          const latestLogs = logsRes.data;

          const completionLog = latestLogs.find((log: any) =>
            new Date(log.timestamp).getTime() > startTime &&
            (log.action.includes("SERVICE_NOW_SYNC_SUCCESS") || log.action.includes("SERVICE_NOW_SYNC_CRASH"))
          );

          if (completionLog) {
            clearInterval(pollInterval);
            setIsSyncing(false);

            if (completionLog.action.includes("SUCCESS")) {
              toast.success("Sync Complete! Check the terminal below for details.", { id: loadingToastId, duration: 6000 });
              setBqLogs(latestLogs);
            } else {
              toast.error("Sync Failed: " + completionLog.details, { id: loadingToastId, duration: 10000 });
              setBqLogs(latestLogs);
            }
          }
        } catch (e) {}
      }, 3000);

      setTimeout(() => {
        clearInterval(pollInterval);
        setIsSyncing(false);
        toast("Sync is taking longer than usual. Check the logs manually in a few minutes.", { id: loadingToastId, icon: '⏳' });
      }, 120000);

    } catch (err: any) {
      setIsSyncing(false);
      toast.error(err.response?.data?.detail || "Failed to trigger ServiceNow sync.", { id: loadingToastId });
    }
  };

  const [bqLogs, setBqLogs] = useState<any[]>([]);

  useEffect(() => {
    if (activeTab === 'system') {
      axios.get('/api/system/logs/')
        .then(res => setBqLogs(res.data))
        .catch(console.error);
    }
  }, [activeTab]);

  // Pagination & Sub-Tab States
  const ITEMS_PER_PAGE = 15;
  const [userTab, setUserTab] = useState<'active' | 'offboarded'>('active');
  const [userPage, setUserPage] = useState(1);

  const [regionTab, setRegionTab] = useState<'active' | 'disabled'>('active');
  const [regionPage, setRegionPage] = useState(1);

  const [countryTab, setCountryTab] = useState<'active' | 'disabled'>('active');
  const [countryPage, setCountryPage] = useState(1);

  const [globalApiKeys, setGlobalApiKeys] = useState<any[]>([]);
  const [apiKeyPage, setApiKeyPage] = useState(1);

  const [locPage, setLocPage] = useState(1);
  const [catPage, setCatPage] = useState(1);
  const [assetTypePage, setAssetTypePage] = useState(1);

  // Sorting States
  const [sortBy, setSortBy] = useState<string>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  // Reset sorting when switching tabs
  useEffect(() => {
    if (activeTab === 'api_keys') setSortBy('owner_name');
    else setSortBy('name');
    setSortDir('asc');
  }, [activeTab]);

  const handleSort = (column: string) => {
    if (sortBy === column) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortBy(column); setSortDir("asc"); }
  };

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return <ChevronsUpDown size={14} className="opacity-30 inline-block" />;
    return sortDir === "asc" ? <ChevronUp size={14} className="text-emerald-500 inline-block" /> : <ChevronDown size={14} className="text-emerald-500 inline-block" />;
  };

  useEffect(() => {
    const fetchGlobalKeys = () => {
      axios.get('/api/auth/keys?global_view=true')
        .then(res => setGlobalApiKeys(res.data))
        .catch(() => toast.error("Failed to load global API keys."));
    };

    if (activeTab === 'api_keys') fetchGlobalKeys();

    const handleRefresh = () => {
      if (activeTab === 'api_keys') fetchGlobalKeys();
    };

    window.addEventListener('refresh_api_keys', handleRefresh);
    return () => window.removeEventListener('refresh_api_keys', handleRefresh);
  }, [activeTab]);

  const handleRevokeGlobalKey = async (id: string) => {
    try {
      await axios.delete(`/api/auth/keys/${id}`);
      setGlobalApiKeys(prev => prev.filter(k => k.id !== id));
      toast.success("API Key permanently revoked.");
    } catch (err) { toast.error("Failed to revoke key."); }
  };

  // Forms
  const defaultUserForm = { email: '', name: '', role: 'read_only', base_capacity: 1.0, location_id: '', start_week: 1, start_year: new Date().getFullYear(), end_week: '', end_year: '', auto_provision_workspace: false };
  const [userForm, setUserForm] = useState(defaultUserForm);
  const [editUserId, setEditUserId] = useState<string | null>(null);

  const defaultLocForm = { name: '', is_active: true };
  const [locForm, setLocForm] = useState(defaultLocForm);
  const [editLocId, setEditLocId] = useState<string | null>(null);

  const defaultServiceForm = { name: '', theme_color: '#3b82f6', default_credits: 2.0, default_duration_weeks: 1, max_concurrent_per_week: 5, target_goal: 0, display_order: 99, is_active: true };
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
  const [editCountryId, setEditCountryId] = useState<string | null>(null);

  const [nukeModalOpen, setNukeModalOpen] = useState(false);
  const [nukeText, setNukeText] = useState("");

  const confirmDelete = (endpoint: string, id: string, name: string) => setDeleteModal({ isOpen: true, endpoint, id, name });
  const executeDelete = async () => { if (deleteModal) { await handleDelete(deleteModal.endpoint, deleteModal.id); setDeleteModal(null); }};

  const submitUser = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = { ...userForm, location_id: userForm.location_id === '' ? null : userForm.location_id, end_week: userForm.end_week === '' ? null : parseInt(userForm.end_week as string), end_year: userForm.end_year === '' ? null : parseInt(userForm.end_year as string) };
    if (await handleSave('/api/users/', payload, !!editUserId, editUserId)) { setShowForm(null); setEditUserId(null); setUserForm(defaultUserForm); }
  };
  const submitLocation = async (e: React.FormEvent) => { e.preventDefault(); if (await handleSave('/api/locations/', locForm, !!editLocId, editLocId)) { setShowForm(null); setEditLocId(null); setLocForm(defaultLocForm); }};
  const submitService = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await handleSave('/api/services/', serviceForm, !!editServiceId, editServiceId)) {
      setShowForm(null);
      setEditServiceId(null);
      setServiceForm(defaultServiceForm);
    }
  };
  const submitCategory = async (e: React.FormEvent) => { e.preventDefault(); const payload = { ...catForm, service_lane_id: catForm.service_lane_id === '' ? null : catForm.service_lane_id }; if (await handleSave('/api/board/categories/', payload, !!editCatId, editCatId)) { setShowForm(null); setEditCatId(null); setCatForm(defaultCatForm); }};
  const submitRegion = async (e: React.FormEvent) => { e.preventDefault(); if (await handleSave('/api/regions/', regionForm, !!editRegionId, editRegionId)) { setShowForm(null); setEditRegionId(null); setRegionForm(defaultRegionForm); }};
  const submitCountry = async (e: React.FormEvent) => { e.preventDefault(); const payload = { ...countryForm, region_id: countryForm.region_id === '' ? null : countryForm.region_id }; if (await handleSave('/api/countries/', payload, !!editCountryId, editCountryId)) { setShowForm(null); setEditCountryId(null); setCountryForm(defaultCountryForm); }};

  if (isLoading) return <div className="min-h-screen bg-slate-50 dark:bg-[#09090b] flex items-center justify-center text-slate-500 dark:text-zinc-500">Loading settings...</div>;

  const inputClasses = "w-full mt-1 p-2.5 md:p-2 border border-slate-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none text-sm md:text-base";
  const PREDEFINED_COLORS = ['#ef4444', '#f97316', '#f59e0b', '#84cc16', '#10b981', '#14b8a6', '#06b6d4', '#3b82f6', '#6366f1', '#8b5cf6', '#a855f7', '#ec4899', '#f43f5e', '#64748b', '#000000', '#ffffff', '#cccccc', '#eeeeee'];

  // FILTERED LISTS
  const isOffboarded = (u: any) => {
    if (!u.end_year || !u.end_week) return false;
    if (serverTime.year > u.end_year) return true;
    if (serverTime.year === u.end_year && serverTime.week > u.end_week) return true;
    return false;
  };

  const displayUsers = users?.filter(u => userTab === 'active' ? !isOffboarded(u) : isOffboarded(u)) || [];
  const displayRegions = regions?.filter(r => regionTab === 'active' ? r.is_active : !r.is_active) || [];
  const displayCountries = countries?.filter(c => countryTab === 'active' ? c.is_active : !c.is_active) || [];

  const sortedLocations = [...(locations || [])].sort((a, b) => {
    let res = a.name.localeCompare(b.name);
    return sortDir === 'asc' ? res : -res;
  });

  const sortedAssetTypes = [...(assetTypes || [])].sort((a, b) => {
    let res = a.name.localeCompare(b.name);
    return sortDir === 'asc' ? res : -res;
  });

  const sortedRegions = [...(displayRegions || [])].sort((a, b) => {
    let res = a.name.localeCompare(b.name);
    return sortDir === 'asc' ? res : -res;
  });

  const sortedCountries = [...(countries || [])].sort((a, b) => {
     let res = 0;
     if (sortBy === 'code') res = (a.code || '').localeCompare(b.code || '');
     else if (sortBy === 'name') res = (a.name || '').localeCompare(b.name || '');
     else if (sortBy === 'region_name') res = (a.region_name || '').localeCompare(b.region_name || '');
    return sortDir === 'asc' ? res : -res;
  });

  const sortedCategories = [...(categories || [])].sort((a, b) => {
    let res = 0;
    if (sortBy === 'name') res = a.name.localeCompare(b.name);
    else if (sortBy === 'target_goal') res = a.target_goal - b.target_goal;
    else if (sortBy === 'service_lane') res = (a.service_lane_name || '').localeCompare(b.service_lane_name || '');
    return sortDir === 'asc' ? res : -res;
  });

  const sortedApiKeys = [...(globalApiKeys || [])].sort((a, b) => {
    let res = 0;
    if (sortBy === 'owner_name') res = (a.owner_name || '').localeCompare(b.owner_name || '');
    else if (sortBy === 'key_name') res = (a.key_name || '').localeCompare(b.key_name || '');
    else if (sortBy === 'prefix') res = (a.prefix || '').localeCompare(b.prefix || '');
    return sortDir === 'asc' ? res : -res;
  });

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
      <ConfirmModal
        isOpen={actionModal?.isOpen || false}
        title={actionModal?.title || ""}
        message={actionModal?.message || ""}
        confirmText={actionModal?.confirmText}
        variant={actionModal?.variant}
        onConfirm={() => { if(actionModal) actionModal.onConfirm(); setActionModal(null); }}
        onCancel={() => setActionModal(null)}
      />

      {/* Nuke Modal */}
      {nukeModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-50 flex items-start sm:items-center justify-center p-4 animate-in fade-in overflow-y-auto">
          <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 w-[95%] sm:w-full max-w-md shadow-2xl animate-in zoom-in-95 my-8 sm:my-0 flex-shrink-0">
            <div className="flex flex-col sm:flex-row items-center sm:items-start gap-4 text-center sm:text-left">
              <div className="bg-red-100 dark:bg-red-500/10 text-red-600 dark:text-red-400 p-3 rounded-full shrink-0 border border-red-200 dark:border-red-500/20"><AlertTriangle size={24} /></div>
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100">Factory Reset</h3>
                <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1">This will permanently delete all tests, assets, events, and assignments. Configurations and users will be kept.</p>
              </div>
            </div>
            <div className="mt-6">
              <label className="block text-sm font-bold text-slate-700 dark:text-zinc-300 mb-2 text-center sm:text-left">Type "NUKE" to confirm:</label>
              <input type="text" className={inputClasses} value={nukeText} onChange={(e) => setNukeText(e.target.value)} placeholder="NUKE" />
            </div>
            <div className="flex flex-col sm:flex-row justify-end gap-3 mt-6">
              <button onClick={() => {setNukeModalOpen(false); setNukeText("");}} className="w-full sm:w-auto px-4 py-2.5 sm:py-2 text-sm font-medium bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors order-2 sm:order-1 flex justify-center items-center">Cancel</button>
              <button onClick={() => { if(nukeText === 'NUKE') { handleWipeSystem(); setNukeModalOpen(false); setNukeText(""); } }} disabled={nukeText !== 'NUKE'} className="w-full sm:w-auto px-4 py-2.5 sm:py-2 text-sm font-medium bg-red-600 hover:bg-red-700 disabled:bg-slate-300 dark:disabled:bg-zinc-800 text-white rounded-lg shadow-sm transition-colors order-1 sm:order-2 flex justify-center items-center">Execute Reset</button>
            </div>
          </div>
        </div>
      )}

      <main className="flex-1 pt-28 md:pt-32 pb-12 px-4 md:px-6 max-w-7xl mx-auto w-full flex flex-col md:flex-row gap-6 md:gap-8">

        {/* SIDEBAR: Horizontal Scrolling on Mobile, Vertical on Desktop */}
        <aside className="w-full md:w-64 shrink-0">
          <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-2 md:p-3 shadow-sm md:sticky md:top-32">
            <h3 className="hidden md:block text-xs font-bold uppercase text-slate-400 dark:text-zinc-500 mb-3 px-3">Platform Settings</h3>
            <nav className="flex flex-row md:flex-col gap-2 md:gap-1 overflow-x-auto md:overflow-visible no-scrollbar pb-1 md:pb-0 px-1 md:px-0 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              <button onClick={() => { setActiveTab('users'); setShowForm(null); }} className={`flex items-center gap-2 md:gap-3 px-3 py-2 md:py-2.5 rounded-xl text-sm font-medium transition-colors whitespace-nowrap flex-shrink-0 ${activeTab === 'users' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><Users size={18} /> Users</button>
              <button onClick={() => { setActiveTab('locations'); setShowForm(null); }} className={`flex items-center gap-2 md:gap-3 px-3 py-2 md:py-2.5 rounded-xl text-sm font-medium transition-colors whitespace-nowrap flex-shrink-0 ${activeTab === 'locations' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><MapPin size={18} /> Locations</button>
              <button onClick={() => { setActiveTab('asset_types'); setShowForm(null); }} className={`flex items-center gap-2 md:gap-3 px-3 py-2 md:py-2.5 rounded-xl text-sm font-medium transition-colors whitespace-nowrap flex-shrink-0 ${activeTab === 'asset_types' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><LayoutTemplate size={18} /> Asset Types</button>
              <button onClick={() => { setActiveTab('services'); setShowForm(null); }} className={`flex items-center gap-2 md:gap-3 px-3 py-2 md:py-2.5 rounded-xl text-sm font-medium transition-colors whitespace-nowrap flex-shrink-0 ${activeTab === 'services' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><Activity size={18} /> Services</button>
              <button onClick={() => { setActiveTab('categories'); setShowForm(null); }} className={`flex items-center gap-2 md:gap-3 px-3 py-2 md:py-2.5 rounded-xl text-sm font-medium transition-colors whitespace-nowrap flex-shrink-0 ${activeTab === 'categories' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><Tags size={18} /> Categories</button>
              <button onClick={() => { setActiveTab('regions'); setShowForm(null); }} className={`flex items-center gap-2 md:gap-3 px-3 py-2 md:py-2.5 rounded-xl text-sm font-medium transition-colors whitespace-nowrap flex-shrink-0 ${activeTab === 'regions' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><Globe size={18} /> Regions</button>
              <button onClick={() => { setActiveTab('countries'); setShowForm(null); }} className={`flex items-center gap-2 md:gap-3 px-3 py-2 md:py-2.5 rounded-xl text-sm font-medium transition-colors whitespace-nowrap flex-shrink-0 ${activeTab === 'countries' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><Flag size={18} /> Countries</button>
              <button onClick={() => { setActiveTab('api_keys'); setShowForm(null); }} className={`flex items-center gap-2 md:gap-3 px-3 py-2 md:py-2.5 rounded-xl text-sm font-medium transition-colors whitespace-nowrap flex-shrink-0 ${activeTab === 'api_keys' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><Key size={18} /> API Keys</button>
              <button onClick={() => { setActiveTab('system'); setShowForm(null); }} className={`flex items-center gap-2 md:gap-3 px-3 py-2 md:py-2.5 rounded-xl text-sm font-medium transition-colors whitespace-nowrap flex-shrink-0 ${activeTab === 'system' ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}><Server size={18} /> System Logs</button>
            </nav>
          </div>
        </aside>

        <section className="flex-1 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 md:p-8 shadow-sm min-h-[600px] flex flex-col w-full overflow-hidden">

          {/* USERS */}
          {activeTab === 'users' && (
            <div className="fade-in flex-1 flex flex-col">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 sm:gap-0 mb-6">
                <div>
                  <h2 className="text-lg md:text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2"><Users size={20} className="text-blue-500"/> User Management</h2>
                  <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mt-1">Manage access roles, capacities, and active intervals.</p>
                </div>
                <button onClick={() => { setEditUserId(null); setUserForm(defaultUserForm); setShowForm('users'); }} className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 sm:py-2 rounded-lg text-sm font-medium flex justify-center items-center gap-2">
                  <Plus size={16} /> Add User
                </button>
              </div>

              {showForm === 'users' && (
                <form onSubmit={submitUser} className="bg-slate-50 dark:bg-zinc-950/50 p-4 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 mb-6 sm:mb-8 space-y-4 shadow-inner">
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-2">{editUserId ? 'Edit User' : 'Create New User'}</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-5">
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
                    <div className="flex gap-3 md:gap-4">
                      <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 w-1/2">Start Year <input type="number" className={inputClasses} value={userForm.start_year} onChange={e => setUserForm({...userForm, start_year: parseInt(e.target.value)})} required /></label>
                      <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 w-1/2">Start Wk <input type="number" className={inputClasses} value={userForm.start_week} onChange={e => setUserForm({...userForm, start_week: parseInt(e.target.value)})} required /></label>
                    </div>
                    <div className="flex flex-col sm:flex-row gap-3 md:gap-4 col-span-1 md:col-span-2 bg-slate-100/50 dark:bg-zinc-800/20 p-3 md:p-4 rounded-xl border border-slate-200 dark:border-zinc-700/50">
                      <label className="text-sm font-bold w-full sm:w-1/2 text-slate-700 dark:text-zinc-300">Offboard Year (Optional) <input type="number" className="w-full mt-1 p-2.5 md:p-2 border border-slate-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-950 focus:ring-2 focus:ring-blue-500 outline-none" value={userForm.end_year} onChange={e => setUserForm({...userForm, end_year: e.target.value})} placeholder="Leave blank if active"/></label>
                      <label className="text-sm font-bold w-full sm:w-1/2 text-slate-700 dark:text-zinc-300">Offboard Wk (Optional) <input type="number" className="w-full mt-1 p-2.5 md:p-2 border border-slate-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-950 focus:ring-2 focus:ring-blue-500 outline-none" value={userForm.end_week} onChange={e => setUserForm({...userForm, end_week: e.target.value})} placeholder="Leave blank if active"/></label>
                    </div>
                  </div>
                  <div className="flex flex-col sm:flex-row justify-end gap-3 pt-4 border-t border-slate-200 dark:border-zinc-800">
                    <button type="submit" className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors order-1 sm:order-2 flex justify-center">{editUserId ? 'Update User' : 'Save User'}</button>
                    <button type="button" onClick={() => {setShowForm(null); setEditUserId(null);}} className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors order-2 sm:order-1 flex justify-center">Cancel</button>
                  </div>
                </form>
              )}

              {/* Sub-Tabs */}
              <div className="flex gap-6 mb-4 border-b border-slate-200 dark:border-zinc-800 overflow-x-auto no-scrollbar whitespace-nowrap">
                <button onClick={() => {setUserTab('active'); setUserPage(1);}} className={`pb-2 font-bold text-sm border-b-2 transition-colors ${userTab === 'active' ? 'border-blue-500 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>Active Users</button>
                <button onClick={() => {setUserTab('offboarded'); setUserPage(1);}} className={`pb-2 font-bold text-sm border-b-2 transition-colors ${userTab === 'offboarded' ? 'border-blue-500 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>Offboarded Users</button>
              </div>

              <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col flex-1 bg-white dark:bg-zinc-900">

                {/* DESKTOP TABLE */}
                <table className="hidden md:table w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800">
                    <tr>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">User Details</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Role</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Capacity</th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                    {displayUsers.slice((userPage - 1) * ITEMS_PER_PAGE, userPage * ITEMS_PER_PAGE).map(u => (
                      <tr key={u.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors">
                        <td className="p-4">
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-full bg-slate-200 dark:bg-zinc-800 text-slate-500 dark:text-zinc-400 flex items-center justify-center font-bold">
                              {u.name?.charAt(0).toUpperCase() || 'U'}
                            </div>
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
                                end_week: u.end_week || '', end_year: u.end_year || '', auto_provision_workspace: false
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

                {/* MOBILE CARDS */}
                <div className="flex md:hidden flex-col divide-y divide-slate-100 dark:divide-zinc-800">
                  {displayUsers.slice((userPage - 1) * ITEMS_PER_PAGE, userPage * ITEMS_PER_PAGE).map(u => (
                    <div key={u.id} className="p-4 flex flex-col gap-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-slate-200 dark:bg-zinc-800 text-slate-500 dark:text-zinc-400 flex items-center justify-center font-bold shrink-0">
                          {u.name?.charAt(0).toUpperCase() || 'U'}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="font-bold text-base text-slate-900 dark:text-zinc-100 truncate">{u.name}</div>
                          <div className="text-xs text-slate-500 dark:text-zinc-500 truncate">{u.email}</div>
                        </div>
                      </div>
                      <div className="flex justify-between items-center bg-slate-50 dark:bg-zinc-950/50 p-2.5 rounded-lg border border-slate-100 dark:border-zinc-800">
                        <div className="flex flex-col gap-1.5 items-start">
                          <span className="px-2.5 py-1 rounded-full bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 text-[10px] font-extrabold uppercase tracking-wider text-slate-700 dark:text-zinc-300">
                            {u.role.replace('_', ' ')}
                          </span>
                          {u.end_year && (
                             <span className="px-2.5 py-0.5 rounded-full bg-red-100 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-[9px] font-extrabold uppercase tracking-wider text-red-700 dark:text-red-400">
                               Offboarded (W{u.end_week}/{u.end_year})
                             </span>
                          )}
                        </div>
                        <div className="font-bold text-sm text-slate-700 dark:text-zinc-300 shrink-0">{u.base_capacity} cr/wk</div>
                      </div>
                      <div className="flex justify-end gap-2 mt-1">
                        <button onClick={() => {
                          setEditUserId(u.id);
                          setUserForm({
                            email: u.email, name: u.name, role: u.role, base_capacity: u.base_capacity,
                            location_id: u.location_id || '', start_week: u.start_week || 1, start_year: u.start_year || new Date().getFullYear(),
                            end_week: u.end_week || '', end_year: u.end_year || '', auto_provision_workspace: false
                          });
                          setShowForm('users');
                        }} className="text-slate-500 bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 p-2.5 rounded-lg transition-colors flex-1 flex justify-center">
                          <Edit2 size={16} />
                        </button>
                        <button onClick={() => confirmDelete('/api/users/', u.id, u.name)} className="text-red-500 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 p-2.5 rounded-lg transition-colors flex-1 flex justify-center">
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                {displayUsers.length === 0 && <div className="p-12 text-center text-sm text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-900/50">No users found.</div>}

                {/* Pagination Footer */}
                {displayUsers.length > 0 && (
                  <div className="px-4 md:px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex flex-col sm:flex-row justify-between items-center gap-3 sm:gap-0 bg-slate-50 dark:bg-zinc-950/50 mt-auto">
                    <span className="text-xs md:text-sm text-slate-500">Page {userPage} of {Math.ceil(displayUsers.length / ITEMS_PER_PAGE) || 1}</span>
                    <div className="flex gap-2 w-full sm:w-auto">
                      <button onClick={() => setUserPage(p => Math.max(1, p - 1))} disabled={userPage === 1} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Prev</button>
                      <button onClick={() => setUserPage(p => p + 1)} disabled={userPage >= Math.ceil(displayUsers.length / ITEMS_PER_PAGE)} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Next</button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ASSET TYPES */}
          {activeTab === 'asset_types' && (
            <div className="fade-in flex-1 flex flex-col">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 sm:gap-0 mb-6">
                <div>
                  <h2 className="text-lg md:text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2"><LayoutTemplate size={20} className="text-blue-500"/> Asset Types</h2>
                  <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mt-1">Manage categories of applications (APIs, Web, Mobile, etc.).</p>
                </div>
                <button onClick={() => { setEditCatId(null); setCatForm({name: '', target_goal: 0, service_lane_id: ''}); setShowForm('asset_types'); }} className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 sm:py-2 rounded-lg text-sm font-medium flex justify-center items-center gap-2 transition-colors">
                  <Plus size={16} /> Add Asset Type
                </button>
              </div>

              {showForm === 'asset_types' && (
                <form onSubmit={(e) => { e.preventDefault(); handleSave('/api/assets/types/', {name: catForm.name}, !!editCatId, editCatId).then(()=> setShowForm(null)); }} className="bg-slate-50 dark:bg-zinc-950/50 p-4 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 mb-6 sm:mb-8 shadow-inner">
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-4">{editCatId ? 'Edit Asset Type' : 'Add Asset Type'}</h3>
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 block mb-6">Asset Type Name <input className={inputClasses} value={catForm.name} onChange={e => setCatForm({...catForm, name: e.target.value})} required placeholder="e.g. Mobile Application" /></label>
                  <div className="flex flex-col sm:flex-row justify-end gap-3 border-t border-slate-200 dark:border-zinc-800 pt-4">
                    <button type="submit" className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors order-1 sm:order-2 flex justify-center">Save</button>
                    <button type="button" onClick={() => setShowForm(null)} className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors order-2 sm:order-1 flex justify-center">Cancel</button>
                  </div>
                </form>
              )}

              <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col flex-1 bg-white dark:bg-zinc-900">
                {/* DESKTOP TABLE */}
                <table className="hidden md:table w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800 select-none">
                    <tr>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort('name')}>
                        <div className="flex items-center gap-2">Type Name <SortIcon column="name" /></div>
                      </th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                    {sortedAssetTypes.slice((assetTypePage - 1) * ITEMS_PER_PAGE, assetTypePage * ITEMS_PER_PAGE).map((at: any) => (
                      <tr key={at.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors">
                        <td className="p-4 font-bold text-base text-slate-900 dark:text-zinc-100">{at.name}</td>
                        <td className="p-4 text-right">
                          <div className="flex justify-end gap-2">
                            <button onClick={() => { setEditCatId(at.id); setCatForm({...catForm, name: at.name}); setShowForm('asset_types'); }} className="text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-500/10 p-2 rounded-lg transition-colors"><Edit2 size={18} /></button>
                            <button onClick={() => confirmDelete('/api/assets/types/', at.id, `Asset Type "${at.name}" (WARNING: Deleting this will also delete all associated raw assets!)`)} className="text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 p-2 rounded-lg transition-colors"><Trash2 size={18} /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* MOBILE CARDS */}
                <div className="flex md:hidden flex-col divide-y divide-slate-100 dark:divide-zinc-800">
                  {sortedAssetTypes.slice((assetTypePage - 1) * ITEMS_PER_PAGE, assetTypePage * ITEMS_PER_PAGE).map((at: any) => (
                    <div key={at.id} className="p-4 flex justify-between items-center gap-4">
                      <span className="font-bold text-base text-slate-900 dark:text-zinc-100 truncate flex-1">{at.name}</span>
                      <div className="flex gap-2 shrink-0">
                        <button onClick={() => { setEditCatId(at.id); setCatForm({...catForm, name: at.name}); setShowForm('asset_types'); }} className="text-slate-500 bg-slate-100 dark:bg-zinc-800 p-2.5 rounded-lg"><Edit2 size={16} /></button>
                        <button onClick={() => confirmDelete('/api/assets/types/', at.id, `Asset Type "${at.name}"`)} className="text-red-500 bg-red-50 dark:bg-red-900/20 p-2.5 rounded-lg"><Trash2 size={16} /></button>
                      </div>
                    </div>
                  ))}
                </div>

                {(!assetTypes || assetTypes.length === 0) && <div className="p-12 text-center text-sm text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-900/50">No asset types found.</div>}

                {assetTypes && assetTypes.length > 0 && (
                  <div className="px-4 md:px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex flex-col sm:flex-row justify-between items-center gap-3 sm:gap-0 bg-slate-50 dark:bg-zinc-950/50 mt-auto">
                    <span className="text-xs md:text-sm text-slate-500">Page {assetTypePage} of {Math.ceil((assetTypes.length) / ITEMS_PER_PAGE) || 1}</span>
                    <div className="flex gap-2 w-full sm:w-auto">
                      <button onClick={() => setAssetTypePage(p => Math.max(1, p - 1))} disabled={assetTypePage === 1} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Prev</button>
                      <button onClick={() => setAssetTypePage(p => p + 1)} disabled={assetTypePage >= Math.ceil(assetTypes.length / ITEMS_PER_PAGE)} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Next</button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* SERVICES (Already Card Based) */}
          {activeTab === 'services' && (
            <div className="fade-in flex-1 flex flex-col">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 sm:gap-0 mb-6">
                <div>
                  <h2 className="text-lg md:text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2"><Activity size={20} className="text-blue-500"/> Dynamic Service Lanes</h2>
                  <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mt-1">Define distinct testing lanes, default credits, and visual themes.</p>
                </div>
                <button onClick={() => { setShowForm('services'); setEditServiceId(null); setServiceForm(defaultServiceForm); }} className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 sm:py-2 rounded-lg text-sm font-medium flex justify-center items-center gap-2 transition-colors">
                  <Plus size={16} /> Add Service
                </button>
              </div>

              {showForm === 'services' && (
                <form onSubmit={submitService} className="bg-slate-50 dark:bg-zinc-950/50 p-4 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 mb-6 sm:mb-8 space-y-4 shadow-inner">
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-2">{editServiceId ? 'Edit Service Lane' : 'Add Service Lane'}</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-5">
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Name <input className={inputClasses} value={serviceForm.name} onChange={e => setServiceForm({...serviceForm, name: e.target.value})} required /></label>
                    <div className="text-sm font-bold text-slate-700 dark:text-zinc-300">
                      Theme Color
                      <div className="mt-2 flex flex-col gap-3">
                        <div className="flex flex-wrap gap-2 p-3 bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg">
                          {PREDEFINED_COLORS.map(color => (
                            <button
                              key={color} type="button" title={color}
                              onClick={() => setServiceForm({ ...serviceForm, theme_color: color })}
                              className={`w-6 h-6 rounded-full border-2 transition-all hover:scale-110 ${serviceForm.theme_color.toLowerCase() === color ? 'border-slate-900 dark:border-white scale-110 shadow-md' : 'border-transparent shadow-sm'}`}
                              style={{ backgroundColor: color }}
                            />
                          ))}
                        </div>
                        <div className="flex items-center gap-3">
                          <input type="text" className={`${inputClasses} !mt-0 font-mono uppercase w-full sm:w-32`} value={serviceForm.theme_color} onChange={e => setServiceForm({...serviceForm, theme_color: e.target.value})} placeholder="#3B82F6" maxLength={7} pattern="^#[0-9A-Fa-f]{6}$" required />
                          <div className="w-10 h-10 rounded-lg shadow-inner border border-slate-200 dark:border-zinc-700 shrink-0 transition-colors" style={{ backgroundColor: serviceForm.theme_color.length === 7 ? serviceForm.theme_color : 'transparent' }}></div>
                        </div>
                      </div>
                    </div>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Default Credits <input type="number" step="0.1" className={inputClasses} value={serviceForm.default_credits} onChange={e => setServiceForm({...serviceForm, default_credits: parseFloat(e.target.value)})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Default Duration (Wks) <input type="number" className={inputClasses} value={serviceForm.default_duration_weeks} onChange={e => setServiceForm({...serviceForm, default_duration_weeks: parseInt(e.target.value)})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Max Concurrent / Wk <input type="number" className={inputClasses} value={serviceForm.max_concurrent_per_week || ''} onChange={e => setServiceForm({...serviceForm, max_concurrent_per_week: parseInt(e.target.value)})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Target Goal (Annual) <input type="number" className={inputClasses} value={serviceForm.target_goal || ''} onChange={e => setServiceForm({...serviceForm, target_goal: parseInt(e.target.value) || 0})} placeholder="e.g. 100" /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 col-span-1 md:col-span-2">Display Order <input type="number" className={inputClasses} value={serviceForm.display_order} onChange={e => setServiceForm({...serviceForm, display_order: parseInt(e.target.value)})} placeholder="e.g. 1" /></label>

                    <div className="col-span-1 md:col-span-2 pt-2 mt-2 border-t border-slate-200 dark:border-zinc-800 space-y-3">
                      <span className="block px-1">
                        <Toggle checked={serviceForm.is_active} onChange={(c) => setServiceForm({...serviceForm, is_active: c})} label="Service Lane is Active" />
                      </span>
                      <span className="block px-1">
                        <Toggle checked={serviceForm.auto_provision_workspace} onChange={(c) => setServiceForm({...serviceForm, auto_provision_workspace: c})} label="Auto-Provision Drive Workspace" />
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-col sm:flex-row justify-end gap-3 pt-4 border-t border-slate-200 dark:border-zinc-800">
                    <button type="submit" className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors order-1 sm:order-2 flex justify-center">{editServiceId ? 'Update' : 'Save'}</button>
                    <button type="button" onClick={() => {setShowForm(null); setEditServiceId(null);}} className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors order-2 sm:order-1 flex justify-center">Cancel</button>
                  </div>
                </form>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {services?.map((item: any) => (
                  <div key={item.id} className={`border p-4 md:p-5 rounded-2xl flex flex-col sm:flex-row sm:justify-between items-start transition-colors bg-white dark:bg-zinc-900 shadow-sm hover:shadow-md gap-4 sm:gap-0 ${item.is_active ? 'border-slate-200 dark:border-zinc-800 hover:border-blue-500 dark:hover:border-blue-500' : 'border-slate-200 dark:border-zinc-800 opacity-60 grayscale'}`}>
                    <div className="w-full">
                      <div className="font-bold text-base md:text-lg text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                        {item.theme_color && <div className="w-4 h-4 rounded-full shadow-sm shrink-0" style={{backgroundColor: item.theme_color}}></div>}
                        <span className="truncate">{item.name}</span>
                      </div>
                      <div className="mt-2 text-xs md:text-sm text-slate-500 dark:text-zinc-400 font-medium">
                        <div>Credits: <span className="text-slate-900 dark:text-zinc-200">{item.default_credits}cr</span></div>
                        <div>Duration: <span className="text-slate-900 dark:text-zinc-200">{item.default_duration_weeks}w</span></div>
                        <div>Max: <span className="text-slate-900 dark:text-zinc-200">{item.max_concurrent_per_week || '∞'}</span></div>
                        <div>Goal: <span className="text-slate-900 dark:text-zinc-200">{item.target_goal || 0}</span></div>
                      </div>
                      <div className={`mt-3 md:mt-4 px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wider w-fit shadow-sm border ${item.is_active ? 'bg-emerald-100 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20 text-emerald-800 dark:text-emerald-400' : 'bg-slate-100 dark:bg-zinc-800 border-slate-200 dark:border-zinc-700 text-slate-500 dark:text-zinc-400'}`}>
                        {item.is_active ? 'Active' : 'Inactive'}
                      </div>
                    </div>
                    <div className="flex sm:flex-col justify-end w-full sm:w-auto gap-2 sm:gap-1 mt-2 sm:mt-0 pt-3 sm:pt-0 border-t border-slate-100 dark:border-transparent sm:border-0">
                      <button onClick={() => {
                        setEditServiceId(item.id);
                        setServiceForm({
                          name: item.name, theme_color: item.theme_color, default_credits: item.default_credits,
                          default_duration_weeks: item.default_duration_weeks, max_concurrent_per_week: item.max_concurrent_per_week || 5,
                          target_goal: item.target_goal || 0, display_order: item.display_order || 99, is_active: item.is_active,
                          auto_provision_workspace: item.auto_provision_workspace || false
                        });
                        setShowForm('services');
                      }} className="flex-1 sm:flex-none flex justify-center text-slate-500 bg-slate-100 dark:bg-zinc-800 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-500/10 p-2.5 md:p-2 rounded-lg transition-colors"><Edit2 size={16} className="md:w-[18px] md:h-[18px]" /></button>
                      <button onClick={() => confirmDelete('/api/services/', item.id, item.name)} className="flex-1 sm:flex-none flex justify-center text-red-500 bg-red-50 dark:bg-red-900/20 hover:text-red-600 hover:bg-red-100 p-2.5 md:p-2 rounded-lg transition-colors"><Trash2 size={16} className="md:w-[18px] md:h-[18px]" /></button>
                    </div>
                  </div>
                ))}
                {(!services || services.length === 0) && <div className="col-span-full p-12 text-center text-sm text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-900/50 rounded-2xl">No services found.</div>}
              </div>
            </div>
          )}

          {/* REGIONS */}
          {activeTab === 'regions' && (
            <div className="fade-in flex-1 flex flex-col">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 sm:gap-0 mb-6">
                <div>
                  <h2 className="text-lg md:text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2"><Globe size={20} className="text-blue-500"/> Regions</h2>
                  <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mt-1">Broad operational boundaries.</p>
                </div>
                <button onClick={() => { setEditRegionId(null); setRegionForm(defaultRegionForm); setShowForm('regions'); }} className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 sm:py-2 rounded-lg text-sm font-medium flex justify-center items-center gap-2 transition-colors">
                  <Plus size={16} /> Add Region
                </button>
              </div>

              {showForm === 'regions' && (
                <form onSubmit={submitRegion} className="bg-slate-50 dark:bg-zinc-950/50 p-4 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 mb-6 sm:mb-8 shadow-inner">
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-4">{editRegionId ? 'Edit Region' : 'Add Region'}</h3>
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 block mb-6">Region Name <input className={inputClasses} value={regionForm.name} onChange={e => setRegionForm({...regionForm, name: e.target.value})} required /></label>
                  <div className="mb-6 pt-2">
                    <Toggle checked={regionForm.is_active} onChange={(c) => setRegionForm({...regionForm, is_active: c})} label="Region is Active" />
                  </div>
                  <div className="flex flex-col sm:flex-row justify-end gap-3 border-t border-slate-200 dark:border-zinc-800 pt-4">
                    <button type="submit" className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors order-1 sm:order-2 flex justify-center">{editRegionId ? 'Update Region' : 'Save Region'}</button>
                    <button type="button" onClick={() => {setShowForm(null); setEditRegionId(null);}} className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors order-2 sm:order-1 flex justify-center">Cancel</button>
                  </div>
                </form>
              )}

              {/* Sub-Tabs */}
              <div className="flex gap-6 mb-4 border-b border-slate-200 dark:border-zinc-800 overflow-x-auto no-scrollbar whitespace-nowrap">
                <button onClick={() => {setRegionTab('active'); setRegionPage(1);}} className={`pb-2 font-bold text-sm border-b-2 transition-colors ${regionTab === 'active' ? 'border-blue-500 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>Active Regions</button>
                <button onClick={() => {setRegionTab('disabled'); setRegionPage(1);}} className={`pb-2 font-bold text-sm border-b-2 transition-colors ${regionTab === 'disabled' ? 'border-blue-500 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>Disabled Regions</button>
              </div>

              <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col flex-1 bg-white dark:bg-zinc-900">
                {/* DESKTOP TABLE */}
                <table className="hidden md:table w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800">
                    <tr>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort('name')}>
                        <div className="flex items-center gap-2">Region Name<SortIcon column="name" /></div>
                      </th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                    {sortedRegions.slice((regionPage - 1) * ITEMS_PER_PAGE, regionPage * ITEMS_PER_PAGE).map(r => (
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

                {/* MOBILE CARDS */}
                <div className="flex md:hidden flex-col divide-y divide-slate-100 dark:divide-zinc-800">
                  {sortedRegions.slice((regionPage - 1) * ITEMS_PER_PAGE, regionPage * ITEMS_PER_PAGE).map(r => (
                    <div key={r.id} className="p-4 flex justify-between items-center gap-4">
                      <span className="font-bold text-base text-slate-900 dark:text-zinc-100 truncate flex-1">{r.name}</span>
                      <div className="flex gap-2 shrink-0">
                        <button onClick={() => {
                          setEditRegionId(r.id);
                          setRegionForm({ name: r.name, is_active: r.is_active });
                          setShowForm('regions');
                        }} className="text-slate-500 bg-slate-100 dark:bg-zinc-800 p-2.5 rounded-lg"><Edit2 size={16} /></button>
                        <button onClick={() => confirmDelete('/api/regions/', r.id, r.name)} className="text-red-500 bg-red-50 dark:bg-red-900/20 p-2.5 rounded-lg"><Trash2 size={16} /></button>
                      </div>
                    </div>
                  ))}
                </div>

                {displayRegions.length === 0 && <div className="p-12 text-center text-sm text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-900/50">No regions found.</div>}

                {/* Pagination Footer */}
                {displayRegions.length > 0 && (
                  <div className="px-4 md:px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex flex-col sm:flex-row justify-between items-center gap-3 sm:gap-0 bg-slate-50 dark:bg-zinc-950/50 mt-auto">
                    <span className="text-xs md:text-sm text-slate-500">Page {regionPage} of {Math.ceil(displayRegions.length / ITEMS_PER_PAGE) || 1}</span>
                    <div className="flex gap-2 w-full sm:w-auto">
                      <button onClick={() => setRegionPage(p => Math.max(1, p - 1))} disabled={regionPage === 1} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Prev</button>
                      <button onClick={() => setRegionPage(p => p + 1)} disabled={regionPage >= Math.ceil(displayRegions.length / ITEMS_PER_PAGE)} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Next</button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* COUNTRIES */}
          {activeTab === 'countries' && (
            <div className="fade-in flex-1 flex flex-col">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 sm:gap-0 mb-6">
                <div>
                  <h2 className="text-lg md:text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2"><Flag size={20} className="text-blue-500"/> Countries</h2>
                  <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mt-1">Manage operating countries and analytics mappings.</p>
                </div>
                <button onClick={() => { setEditCountryId(null); setCountryForm(defaultCountryForm); setShowForm('countries'); }} className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 sm:py-2 rounded-lg text-sm font-medium flex justify-center items-center gap-2 transition-colors">
                  <Plus size={16} /> Add Country
                </button>
              </div>

              {showForm === 'countries' && (
                <form onSubmit={submitCountry} className="bg-slate-50 dark:bg-zinc-950/50 p-4 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 mb-6 sm:mb-8 space-y-4 shadow-inner">
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-2">{editCountryId ? 'Edit Country' : 'Add Country'}</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-5">
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Code (e.g. US) <input className={inputClasses} value={countryForm.code} onChange={e => setCountryForm({...countryForm, code: e.target.value.toUpperCase()})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Name <input className={inputClasses} value={countryForm.name} onChange={e => setCountryForm({...countryForm, name: e.target.value})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 col-span-1 md:col-span-2">Region
                      <select className={inputClasses} value={countryForm.region_id} onChange={e => setCountryForm({...countryForm, region_id: e.target.value})}>
                        <option value="">-- None --</option>
                        {regions?.map(r => <option key={r.id} value={r.id}>{r.name || r.regions}</option>)}
                      </select>
                    </label>
                    <div className="col-span-1 md:col-span-2 pt-2 border-t border-slate-200 dark:border-zinc-800 px-1">
                      <Toggle checked={countryForm.is_active} onChange={(c) => setCountryForm({...countryForm, is_active: c})} label="Country is Active" />
                    </div>
                  </div>
                  <div className="flex flex-col sm:flex-row justify-end gap-3 pt-4 border-t border-slate-200 dark:border-zinc-800 mt-2">
                    <button type="submit" className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors order-1 sm:order-2 flex justify-center">{editCountryId ? 'Update Country' : 'Save Country'}</button>
                    <button type="button" onClick={() => {setShowForm(null); setEditCountryId(null);}} className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors order-2 sm:order-1 flex justify-center">Cancel</button>
                  </div>
                </form>
              )}

              {/* Sub-Tabs */}
              <div className="flex gap-6 mb-4 border-b border-slate-200 dark:border-zinc-800 overflow-x-auto no-scrollbar whitespace-nowrap">
                <button onClick={() => {setCountryTab('active'); setCountryPage(1);}} className={`pb-2 font-bold text-sm border-b-2 transition-colors ${countryTab === 'active' ? 'border-blue-500 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>Active Countries</button>
                <button onClick={() => {setCountryTab('disabled'); setCountryPage(1);}} className={`pb-2 font-bold text-sm border-b-2 transition-colors ${countryTab === 'disabled' ? 'border-blue-500 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>Disabled Countries</button>
              </div>

              <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col flex-1 bg-white dark:bg-zinc-900">
                {/* DESKTOP TABLE */}
                <table className="hidden md:table w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800">
                    <tr>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort('code')}>
                        <div className="flex items-center gap-2">Code<SortIcon column="code" /></div>
                      </th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort('name')}>
                        <div className="flex items-center gap-2">Country Name<SortIcon column="name" /></div>
                      </th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort('region_name')}>
                        <div className="flex items-center gap-2">Region<SortIcon column="region_name" /></div>
                      </th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                    {sortedCountries.slice((countryPage - 1) * ITEMS_PER_PAGE, countryPage * ITEMS_PER_PAGE).map(c => (
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

                {/* MOBILE CARDS */}
                <div className="flex md:hidden flex-col divide-y divide-slate-100 dark:divide-zinc-800">
                  {sortedCountries.slice((countryPage - 1) * ITEMS_PER_PAGE, countryPage * ITEMS_PER_PAGE).map(c => (
                    <div key={c.id} className="p-4 flex flex-col gap-3">
                      <div className="flex justify-between items-start gap-4 w-full">
                        <div className="flex items-center gap-2 min-w-0 flex-1">
                          <span className="font-mono text-slate-500 dark:text-zinc-400 text-xs bg-slate-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded border border-slate-200 dark:border-zinc-700 shrink-0">{c.code}</span>
                          <span className="font-bold text-base text-slate-900 dark:text-zinc-100 truncate">{c.name}</span>
                        </div>
                        <span className="px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 text-indigo-700 dark:text-indigo-400 text-[10px] font-bold shadow-sm shrink-0 whitespace-nowrap">
                          {c.region_name || 'Unmapped'}
                        </span>
                      </div>
                      <div className="flex justify-end gap-2 mt-1">
                        <button onClick={() => {
                          setEditCountryId(c.id);
                          setCountryForm({ code: c.code, name: c.name, region_id: c.region_id || '', is_active: c.is_active });
                          setShowForm('countries');
                        }} className="text-slate-500 bg-slate-100 dark:bg-zinc-800 p-2.5 rounded-lg flex-1 flex justify-center"><Edit2 size={16} /></button>
                        <button onClick={() => confirmDelete('/api/countries/', c.id, c.name)} className="text-red-500 bg-red-50 dark:bg-red-900/20 p-2.5 rounded-lg flex-1 flex justify-center"><Trash2 size={16} /></button>
                      </div>
                    </div>
                  ))}
                </div>

                {displayCountries.length === 0 && <div className="p-12 text-center text-sm text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-900/50">No countries found.</div>}

                {/* Pagination Footer */}
                {displayCountries.length > 0 && (
                  <div className="px-4 md:px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex flex-col sm:flex-row justify-between items-center gap-3 sm:gap-0 bg-slate-50 dark:bg-zinc-950/50 mt-auto">
                    <span className="text-xs md:text-sm text-slate-500">Page {countryPage} of {Math.ceil(displayCountries.length / ITEMS_PER_PAGE) || 1}</span>
                    <div className="flex gap-2 w-full sm:w-auto">
                      <button onClick={() => setCountryPage(p => Math.max(1, p - 1))} disabled={countryPage === 1} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Prev</button>
                      <button onClick={() => setCountryPage(p => p + 1)} disabled={countryPage >= Math.ceil(displayCountries.length / ITEMS_PER_PAGE)} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Next</button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* CATEGORIES */}
          {activeTab === 'categories' && (
            <div className="fade-in flex-1 flex flex-col">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 sm:gap-0 mb-6">
                <div>
                  <h2 className="text-lg md:text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2"><Tags size={20} className="text-blue-500"/> Service Forecasts</h2>
                  <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mt-1">Specific target goals mapped to service lanes.</p>
                </div>
                <button onClick={() => { setEditCatId(null); setCatForm(defaultCatForm); setShowForm('categories'); }} className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 sm:py-2 rounded-lg text-sm font-medium flex justify-center items-center gap-2 transition-colors">
                  <Plus size={16} /> Add Category
                </button>
              </div>

              {showForm === 'categories' && (
                <form onSubmit={submitCategory} className="bg-slate-50 dark:bg-zinc-950/50 p-4 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 mb-6 sm:mb-8 space-y-4 shadow-inner">
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-2">{editCatId ? 'Edit Category' : 'Add Category'}</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-5">
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 col-span-1 md:col-span-2">Name <input className={inputClasses} value={catForm.name} onChange={e => setCatForm({...catForm, name: e.target.value})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Target Goal <input type="number" className={inputClasses} value={catForm.target_goal} onChange={e => setCatForm({...catForm, target_goal: parseInt(e.target.value)})} required /></label>
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Link to Service Lane
                      <select className={inputClasses} value={catForm.service_lane_id} onChange={e => setCatForm({...catForm, service_lane_id: e.target.value})}>
                        <option value="">-- None --</option>
                        {services?.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                      </select>
                    </label>
                  </div>
                  <div className="flex flex-col sm:flex-row justify-end gap-3 pt-4 border-t border-slate-200 dark:border-zinc-800 mt-2">
                    <button type="submit" className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors order-1 sm:order-2 flex justify-center">{editCatId ? 'Update Category' : 'Save Category'}</button>
                    <button type="button" onClick={() => {setShowForm(null); setEditCatId(null);}} className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors order-2 sm:order-1 flex justify-center">Cancel</button>
                  </div>
                </form>
              )}

              <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col flex-1 bg-white dark:bg-zinc-900">
                {/* DESKTOP TABLE */}
                <table className="hidden md:table w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800 select-none">
                    <tr>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort('name')}>
                        <div className="flex items-center gap-2">Category Name <SortIcon column="name" /></div>
                      </th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort('target_goal')}>
                        <div className="flex items-center gap-2">Target Goal <SortIcon column="target_goal" /></div>
                      </th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort('service_lane')}>
                        <div className="flex items-center gap-2">Service Lane <SortIcon column="service_lane" /></div>
                      </th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                    {sortedCategories.slice((catPage - 1) * ITEMS_PER_PAGE, catPage * ITEMS_PER_PAGE).map(c => (
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

                {/* MOBILE CARDS */}
                <div className="flex md:hidden flex-col divide-y divide-slate-100 dark:divide-zinc-800">
                  {sortedCategories.slice((catPage - 1) * ITEMS_PER_PAGE, catPage * ITEMS_PER_PAGE).map(c => (
                    <div key={c.id} className="p-4 flex flex-col gap-3">
                      <div className="flex justify-between items-start gap-4">
                        <span className="font-bold text-base text-slate-900 dark:text-zinc-100 leading-tight">{c.name}</span>
                        <span className="text-xs font-bold text-slate-500 dark:text-zinc-400 bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded shrink-0">Goal: {c.target_goal}</span>
                      </div>
                      <div className="flex justify-between items-end mt-1">
                        <span className="px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/20 text-blue-700 dark:text-blue-400 text-[10px] font-bold shadow-sm max-w-[60%] truncate">
                          {c.service_lane_name || 'Unlinked'}
                        </span>
                        <div className="flex gap-2 shrink-0">
                          <button onClick={() => {
                            setEditCatId(c.id);
                            setCatForm({ name: c.name, target_goal: c.target_goal, service_lane_id: c.service_lane_id || '' });
                            setShowForm('categories');
                          }} className="text-slate-500 bg-slate-100 dark:bg-zinc-800 p-2 rounded-lg"><Edit2 size={16} /></button>
                          <button onClick={() => confirmDelete('/api/board/categories/', c.id, c.name)} className="text-red-500 bg-red-50 dark:bg-red-900/20 p-2 rounded-lg"><Trash2 size={16} /></button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {sortedCategories.length === 0 && <div className="p-12 text-center text-sm text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-900/50">No categories found.</div>}

                {/* Pagination Footer */}
                {sortedCategories.length > 0 && (
                  <div className="px-4 md:px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex flex-col sm:flex-row justify-between items-center gap-3 sm:gap-0 bg-slate-50 dark:bg-zinc-950/50 mt-auto">
                    <span className="text-xs md:text-sm text-slate-500">Page {catPage} of {Math.ceil(sortedCategories.length / ITEMS_PER_PAGE) || 1}</span>
                    <div className="flex gap-2 w-full sm:w-auto">
                      <button onClick={() => setCatPage(p => Math.max(1, p - 1))} disabled={catPage === 1} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Prev</button>
                      <button onClick={() => setCatPage(p => p + 1)} disabled={catPage >= Math.ceil(sortedCategories.length / ITEMS_PER_PAGE)} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Next</button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* LOCATIONS */}
          {activeTab === 'locations' && (
            <div className="fade-in flex-1 flex flex-col">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 sm:gap-0 mb-6">
                <div>
                  <h2 className="text-lg md:text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2"><MapPin size={20} className="text-blue-500"/> Locations</h2>
                  <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mt-1">Geographic bases for calculating national holidays.</p>
                </div>
                <button onClick={() => { setEditLocId(null); setLocForm(defaultLocForm); setShowForm('locations'); }} className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 sm:py-2 rounded-lg text-sm font-medium flex justify-center items-center gap-2">
                  <Plus size={16} /> Add Location
                </button>
              </div>

              {showForm === 'locations' && (
                <form onSubmit={submitLocation} className="bg-slate-50 dark:bg-zinc-950/50 p-4 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 mb-6 sm:mb-8 shadow-inner">
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-4">{editLocId ? 'Edit Location' : 'Add Location'}</h3>
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 block mb-6">Location Name <input className={inputClasses} value={locForm.name} onChange={e => setLocForm({...locForm, name: e.target.value})} required placeholder="e.g. London" /></label>
                  <div className="flex flex-col sm:flex-row justify-end gap-3 border-t border-slate-200 dark:border-zinc-800 pt-4">
                    <button type="submit" className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors order-1 sm:order-2 flex justify-center">{editLocId ? 'Update Location' : 'Save Location'}</button>
                    <button type="button" onClick={() => {setShowForm(null); setEditLocId(null);}} className="w-full sm:w-auto px-5 py-2.5 sm:py-2 text-sm font-medium bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors order-2 sm:order-1 flex justify-center">Cancel</button>
                  </div>
                </form>
              )}

              <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col flex-1 bg-white dark:bg-zinc-900">
                {/* DESKTOP TABLE */}
                <table className="hidden md:table w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800 select-none">
                    <tr>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort('name')}>
                        <div className="flex items-center gap-2">Location Name <SortIcon column="name" /></div>
                      </th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                    {sortedLocations.slice((locPage - 1) * ITEMS_PER_PAGE, locPage * ITEMS_PER_PAGE).map(loc => (
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

                {/* MOBILE CARDS */}
                <div className="flex md:hidden flex-col divide-y divide-slate-100 dark:divide-zinc-800">
                  {sortedLocations.slice((locPage - 1) * ITEMS_PER_PAGE, locPage * ITEMS_PER_PAGE).map(loc => (
                    <div key={loc.id} className="p-4 flex justify-between items-center gap-4">
                      <span className="font-bold text-base text-slate-900 dark:text-zinc-100 truncate flex-1">{loc.name}</span>
                      <div className="flex gap-2 shrink-0">
                        <button onClick={() => {
                          setEditLocId(loc.id);
                          setLocForm({ name: loc.name, is_active: loc.is_active });
                          setShowForm('locations');
                        }} className="text-slate-500 bg-slate-100 dark:bg-zinc-800 p-2.5 rounded-lg"><Edit2 size={16} /></button>
                        <button onClick={() => confirmDelete('/api/locations/', loc.id, loc.name)} className="text-red-500 bg-red-50 dark:bg-red-900/20 p-2.5 rounded-lg"><Trash2 size={16} /></button>
                      </div>
                    </div>
                  ))}
                </div>

                {sortedLocations.length === 0 && <div className="p-12 text-center text-sm text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-900/50">No locations found.</div>}

                {/* Pagination Footer */}
                {sortedLocations.length > 0 && (
                  <div className="px-4 md:px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex flex-col sm:flex-row justify-between items-center gap-3 sm:gap-0 bg-slate-50 dark:bg-zinc-950/50 mt-auto">
                    <span className="text-xs md:text-sm text-slate-500">Page {locPage} of {Math.ceil(sortedLocations.length / ITEMS_PER_PAGE) || 1}</span>
                    <div className="flex gap-2 w-full sm:w-auto">
                      <button onClick={() => setLocPage(p => Math.max(1, p - 1))} disabled={locPage === 1} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Prev</button>
                      <button onClick={() => setLocPage(p => p + 1)} disabled={locPage >= Math.ceil(sortedLocations.length / ITEMS_PER_PAGE)} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Next</button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* GLOBAL API KEYS (ADMIN ONLY) */}
          {activeTab === 'api_keys' && (
            <div className="fade-in flex-1 flex flex-col">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h2 className="text-lg md:text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2"><Key size={20} className="text-blue-500"/> Global API Keys</h2>
                  <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mt-1">Monitor and revoke active API keys across the entire platform.</p>
                </div>
              </div>

              <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col flex-1 bg-white dark:bg-zinc-900">
                {/* DESKTOP TABLE */}
                <table className="hidden md:table w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800 select-none">
                    <tr>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort('owner_name')}>
                        <div className="flex items-center gap-2">Key Owner <SortIcon column="owner_name" /></div>
                      </th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort('key_name')}>
                        <div className="flex items-center gap-2">Key Name <SortIcon column="key_name" /></div>
                      </th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort('prefix')}>
                        <div className="flex items-center gap-2">Prefix <SortIcon column="prefix" /></div>
                      </th>
                      <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                    {sortedApiKeys.slice((apiKeyPage - 1) * ITEMS_PER_PAGE, apiKeyPage * ITEMS_PER_PAGE).map(k => (
                      <tr key={k.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors">
                        <td className="p-4">
                          <div className="font-bold text-slate-900 dark:text-zinc-100">{k.owner_name}</div>
                          <div className="text-xs text-slate-500">{k.owner_email}</div>
                        </td>
                        <td className="p-4 font-medium text-slate-700 dark:text-zinc-300">{k.key_name}</td>
                        <td className="p-4 text-slate-500 dark:text-zinc-400 font-mono text-xs">{k.prefix}••••••••</td>
                        <td className="p-4 text-right">
                          <button onClick={() => {
                             setActionModal({
                               isOpen: true, variant: 'danger', confirmText: "Revoke Key", title: "Revoke API Key",
                               message: `Are you sure you want to revoke the key "${k.key_name}" owned by ${k.owner_name}? Any scripts using this key will immediately fail.`,
                               onConfirm: () => handleRevokeGlobalKey(k.id)
                             });
                          }} className="text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 p-2 rounded-lg transition-colors" title="Revoke Key">
                            <Trash2 size={18} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* MOBILE CARDS */}
                <div className="flex md:hidden flex-col divide-y divide-slate-100 dark:divide-zinc-800">
                  {sortedApiKeys.slice((apiKeyPage - 1) * ITEMS_PER_PAGE, apiKeyPage * ITEMS_PER_PAGE).map(k => (
                    <div key={k.id} className="p-4 flex flex-col gap-3">
                      <div className="flex justify-between items-start gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="font-bold text-base text-slate-900 dark:text-zinc-100 truncate">{k.owner_name}</div>
                          <div className="text-xs text-slate-500 dark:text-zinc-400 truncate">{k.owner_email}</div>
                        </div>
                        <button onClick={() => {
                            setActionModal({
                              isOpen: true, variant: 'danger', confirmText: "Revoke Key", title: "Revoke API Key",
                              message: `Are you sure you want to revoke the key "${k.key_name}" owned by ${k.owner_name}? Any scripts using this key will immediately fail.`,
                              onConfirm: () => handleRevokeGlobalKey(k.id)
                            });
                        }} className="text-red-500 bg-red-50 dark:bg-red-900/20 p-2.5 rounded-lg shrink-0" title="Revoke Key">
                          <Trash2 size={16} />
                        </button>
                      </div>
                      <div className="flex justify-between items-center bg-slate-50 dark:bg-zinc-950/50 p-2.5 rounded-lg border border-slate-100 dark:border-zinc-800 mt-1">
                        <span className="font-medium text-slate-700 dark:text-zinc-300 text-sm truncate pr-2">{k.key_name}</span>
                        <span className="font-mono text-[10px] text-slate-500 dark:text-zinc-400 bg-white dark:bg-zinc-900 px-1.5 py-0.5 rounded border border-slate-200 dark:border-zinc-700 shrink-0">{k.prefix}••••</span>
                      </div>
                    </div>
                  ))}
                </div>

                {globalApiKeys.length === 0 && <div className="p-12 text-center text-sm text-slate-500 dark:text-zinc-500 bg-slate-50/50 dark:bg-zinc-900/50">No API keys are currently active.</div>}

                {/* Pagination Footer */}
                {globalApiKeys.length > 0 && (
                  <div className="px-4 md:px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex flex-col sm:flex-row justify-between items-center gap-3 sm:gap-0 bg-slate-50 dark:bg-zinc-950/50 mt-auto">
                    <span className="text-xs md:text-sm text-slate-500">Page {apiKeyPage} of {Math.ceil(globalApiKeys.length / ITEMS_PER_PAGE) || 1}</span>
                    <div className="flex gap-2 w-full sm:w-auto">
                      <button onClick={() => setApiKeyPage(p => Math.max(1, p - 1))} disabled={apiKeyPage === 1} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Prev</button>
                      <button onClick={() => setApiKeyPage(p => p + 1)} disabled={apiKeyPage >= Math.ceil(globalApiKeys.length / ITEMS_PER_PAGE)} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white sm:bg-transparent">Next</button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* SYSTEM LOGS */}
          {activeTab === 'system' && (
            <div className="space-y-8 fade-in">
              <div>
                <h2 className="text-lg md:text-xl font-bold text-slate-900 dark:text-zinc-100 mb-4 flex items-center gap-2"><Terminal size={20} className="text-slate-500 dark:text-zinc-400"/> Audit Logs</h2>

                <div className="flex flex-col sm:flex-row gap-3 mb-4">
                  <a href="/api/system/logs/download/csv" target="_blank" rel="noopener noreferrer" className="bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 px-4 py-2.5 sm:py-2 rounded-lg flex justify-center items-center gap-2 text-sm font-bold transition-colors w-full sm:w-auto">
                    <Download size={16} /> Download Logs
                  </a>
                  <button onClick={() => confirmDelete('/api/system/logs/clear', '', 'All Audit Logs')} className="text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10 hover:bg-red-100 dark:hover:bg-red-500/20 px-4 py-2.5 sm:py-2 rounded-lg flex justify-center items-center gap-2 text-sm font-bold transition-colors w-full sm:w-auto">
                    <Trash2 size={16} /> Delete all Logs
                  </button>
                </div>

                {/* Fully Scrollable Terminal Container */}
                <div className="bg-[#0c0c0e] rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden flex flex-col h-[400px] w-full max-w-full">
                  {/* Terminal Header */}
                  <div className="bg-slate-800 px-3 md:px-4 py-2 flex items-center gap-2 shrink-0">
                    <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-red-500 shrink-0"></div>
                    <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-amber-500 shrink-0"></div>
                    <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-emerald-500 shrink-0"></div>
                    <span className="ml-2 text-[10px] md:text-xs font-mono text-slate-400 truncate">gostplanner.audit_logs</span>
                  </div>

                  {/* Terminal Body */}
                  <div className="p-3 md:p-4 overflow-auto custom-scrollbar font-mono text-[10px] md:text-[11px] text-slate-300 flex-1 w-full relative">
                    <div className="w-max min-w-full space-y-1.5">
                      {(!bqLogs || bqLogs.length === 0) ? (
                         <div className="text-slate-600 italic">No logs found in BigQuery.</div>
                      ) : (
                        bqLogs.map((log: any, idx: number) => (
                          <div key={idx} className="flex gap-2 md:gap-3 hover:bg-white/5 p-1 rounded transition-colors whitespace-nowrap">
                            <span className="text-emerald-400 shrink-0">[{new Date(log.timestamp).toLocaleString()}]</span>
                            <span className="text-blue-400 shrink-0 font-bold">[{log.action}]</span>
                            <span className="text-slate-300 pr-4">{log.details}</span>
                            <span className="text-slate-500 ml-auto shrink-0 pl-4 border-l border-slate-800">User: {log.user_id?.split('-')[0]}... ({log.role})</span>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* --- SERVICENOW INTEGRATION SECTION --- */}
              <div className="pt-6 border-t border-slate-200 dark:border-zinc-800">
                <h2 className="text-lg md:text-xl font-bold text-slate-900 dark:text-zinc-100 mb-2 flex items-center gap-2">
                  <Database size={20} className="text-blue-500" /> ServiceNow CMDB
                </h2>
                <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mb-4 max-w-2xl">
                  Manually trigger a background synchronization to fetch and map active application assets from the ServiceNow CMDB. This process processes up to 10,000 items and will run in the background.
                </p>
                <button
                  onClick={handleSnowSync}
                  disabled={isSyncing}
                  className="w-full sm:w-auto bg-slate-100 dark:bg-zinc-800 hover:bg-blue-50 dark:hover:bg-blue-500/10 text-slate-700 dark:text-zinc-300 hover:text-blue-600 dark:hover:text-blue-400 disabled:opacity-50 disabled:cursor-not-allowed border border-slate-200 dark:border-zinc-700 px-4 py-2.5 md:py-2 rounded-lg text-sm font-bold flex justify-center items-center gap-2 transition-colors"
                >
                  {isSyncing ? (
                    <>
                      <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Queuing Sync...
                    </>
                  ) : (
                    <>
                      <Database size={16} /> Sync Assets Now
                    </>
                  )}
                </button>
              </div>

              {/* --- DANGER ZONE SECTION --- */}
              <div className="pt-6 border-t border-slate-200 dark:border-zinc-800">
                <h2 className="text-lg md:text-xl font-bold text-red-600 dark:text-red-500 mb-2 flex items-center gap-2"><AlertTriangle size={20} /> Danger Zone</h2>
                <div className="flex flex-col sm:flex-row gap-4 mt-4">
                  <button onClick={() => setNukeModalOpen(true)} className="w-full sm:w-auto bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-6 md:px-8 rounded-xl shadow-sm transition-colors focus:ring-4 focus:ring-red-500/20 text-sm md:text-base">Execute Factory Reset</button>
                  <button onClick={() => {
                    setActionModal({
                      isOpen: true, variant: 'danger', confirmText: "Wipe Secrets", title: "Wipe All Secure Notes",
                      message: "Are you sure you want to permanently wipe ALL encrypted notes from the vault? This action cannot be reversed.",
                      onConfirm: async () => { await axios.delete('/api/board/system/wipe-secrets'); toast.success("Notes wiped."); }
                    });
                  }} className="w-full sm:w-auto bg-orange-600 hover:bg-orange-700 text-white font-bold py-3 px-6 md:px-8 rounded-xl shadow-sm transition-colors text-sm md:text-base">Wipe All Secure Notes
                  </button>
                </div>
              </div>
            </div>
          )}

        </section>
      </main>
    </div>
  );
}