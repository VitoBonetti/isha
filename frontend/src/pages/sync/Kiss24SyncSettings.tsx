import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import {
  ShieldCheck, Database, RefreshCw, Building2, Server, UserSquare2, Layers,
  TerminalSquare, Monitor, LayoutList, ChevronLeft, ChevronRight, ExternalLink,
  Search, ArrowUpDown, ArrowUp, ArrowDown, Filter
} from 'lucide-react';

export default function Kiss24SyncSettings() {
  const [activeTab, setActiveTab] = useState<'actions' | 'assets' | 'tests'>('actions');

  // --- SYNC STATE ---
  const [isSyncingOrg, setIsSyncingOrg] = useState(false);
  const [isSyncingAsset, setIsSyncingAsset] = useState(false);
  const [isSyncingSnowID, setIsSyncingSnowID] = useState(false);
  const [isSyncingVulnTypesID, setIsSyncingVulnTypesID] = useState(false);
  const [isSyncingUserKissID, setIsSyncingUserKissID] = useState(false);

  // --- METRICS STATE ---
  const [totalKiss24Assets, setTotalKiss24Assets] = useState<number | null>(null);

  // --- ASSETS STATE ---
  const [assetData, setAssetData] = useState<any>(null);
  const [assetPage, setAssetPage] = useState(1);
  const [isFetchingAssets, setIsFetchingAssets] = useState(false);
  const [assetSearch, setAssetSearch] = useState('');
  const [debouncedAssetSearch, setDebouncedAssetSearch] = useState('');
  const [assetSortBy, setAssetSortBy] = useState('name');
  const [assetSortDir, setAssetSortDir] = useState<'asc' | 'desc'>('asc');

  // --- TESTS STATE ---
  const [testData, setTestData] = useState<any>(null);
  const [testPage, setTestPage] = useState(1);
  const [isFetchingTests, setIsFetchingTests] = useState(false);
  const [testSearch, setTestSearch] = useState('');
  const [debouncedTestSearch, setDebouncedTestSearch] = useState('');
  const [testLaneFilter, setTestLaneFilter] = useState('');
  const [testStatusFilter, setTestStatusFilter] = useState('');
  const [testSortBy, setTestSortBy] = useState('name');
  const [testSortDir, setTestSortDir] = useState<'asc' | 'desc'>('asc');

  // --- DEBOUNCE EFFECT FOR SEARCH BARS ---
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedAssetSearch(assetSearch), 500);
    return () => clearTimeout(timer);
  }, [assetSearch]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedTestSearch(testSearch), 500);
    return () => clearTimeout(timer);
  }, [testSearch]);

  // --- FETCHERS ---
  const fetchKiss24Metrics = async () => {
    try {
      const res = await axios.get('/api/kiss24/assets/total-count');
      setTotalKiss24Assets(res.data.total_assets);
    } catch (e) {
      console.error("Failed to fetch total KISS24 assets metric.");
    }
  };

  const fetchAssets = async () => {
    setIsFetchingAssets(true);
    try {
      const params = new URLSearchParams({
        page: assetPage.toString(),
        sort_by: assetSortBy,
        sort_dir: assetSortDir
      });
      if (debouncedAssetSearch) params.append('search', debouncedAssetSearch);

      const res = await axios.get(`/api/kiss24/raw/synced/?${params.toString()}`);
      setAssetData(res.data);
    } catch (e) {
      toast.error("Failed to fetch synced assets.");
    } finally { setIsFetchingAssets(false); }
  };

  const fetchTests = async () => {
    setIsFetchingTests(true);
    try {
      const params = new URLSearchParams({
        page: testPage.toString(),
        sort_by: testSortBy,
        sort_dir: testSortDir
      });
      if (debouncedTestSearch) params.append('search', debouncedTestSearch);
      if (testLaneFilter) params.append('service_lane', testLaneFilter);
      if (testStatusFilter) params.append('status', testStatusFilter);

      const res = await axios.get(`/api/kiss24/tests/synced/?${params.toString()}`);
      setTestData(res.data);
    } catch (e) {
      toast.error("Failed to fetch synced tests.");
    } finally { setIsFetchingTests(false); }
  };

  // Fetch metrics once on mount
  useEffect(() => {
    fetchKiss24Metrics();
  }, []);

  // Trigger Fetching when Tabs or Parameters change
  useEffect(() => {
    if (activeTab === 'assets') fetchAssets();
  }, [activeTab, assetPage, debouncedAssetSearch, assetSortBy, assetSortDir]);

  useEffect(() => {
    if (activeTab === 'tests') fetchTests();
  }, [activeTab, testPage, debouncedTestSearch, testLaneFilter, testStatusFilter, testSortBy, testSortDir]);


  // --- SORT HANDLERS ---
  const handleAssetSort = (col: string) => {
    if (assetSortBy === col) {
      setAssetSortDir(assetSortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setAssetSortBy(col);
      setAssetSortDir('asc');
    }
  };

  const handleTestSort = (col: string) => {
    if (testSortBy === col) {
      setTestSortDir(testSortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setTestSortBy(col);
      setTestSortDir('asc');
    }
  };

  const renderSortIcon = (currentSortBy: string, currentSortDir: string, colName: string) => {
    if (currentSortBy !== colName) return <ArrowUpDown size={12} className="ml-1 opacity-40 inline" />;
    return currentSortDir === 'asc' ? <ArrowUp size={12} className="ml-1 inline text-blue-500" /> : <ArrowDown size={12} className="ml-1 inline text-blue-500" />;
  };

  // --- SYNC ACTION HANDLERS ---
  const handleGlobalSyncOrg = async () => {
    setIsSyncingOrg(true);
    const toastId = toast.loading("Syncing Organization UUIDs...");
    try {
      await axios.post('/api/kiss24/sync-org-ids');
      toast.success("Organization Sync Complete!", { id: toastId });
    } catch (e: any) { toast.error(e.response?.data?.detail || "Sync Failed", { id: toastId }); }
    finally { setIsSyncingOrg(false); }
  };

  const handleGlobalSyncAsset = async () => {
    setIsSyncingAsset(true);
    const toastId = toast.loading("Syncing Asset IDs...");
    try {
      await axios.post('/api/kiss24/sync-asset-ids');
      toast.success("Asset Sync Complete!", { id: toastId });
      if (activeTab === 'assets') fetchAssets();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Sync Failed", { id: toastId }); }
    finally { setIsSyncingAsset(false); }
  };

  const handleSyncKissSnowID = async () => {
    setIsSyncingSnowID(true);
    const toastId = toast.loading("Updating CustomField 'Service Now ID'...");
    try {
      await axios.post(`/api/kiss24/sync-update-kiss24-snowid`);
      toast.success("CustomField updated", { id: toastId });
    } catch (e: any) { toast.error(e.response?.data?.detail || "Update Failed", { id: toastId }); }
    finally { setIsSyncingSnowID(false); }
  };

  const handleSyncKissVulnTypesID = async () => {
    setIsSyncingVulnTypesID(true);
    const toastId = toast.loading("Updating contexts and vuln types...");
    try {
      await axios.post(`/api/kiss24/sync-vuln-types`);
      toast.success("Contexts and Vuln Types updated", { id: toastId });
    } catch (e: any) { toast.error(e.response?.data?.detail || "Update Failed", { id: toastId }); }
    finally { setIsSyncingVulnTypesID(false); }
  };

  const handleSyncKissUserID = async () => {
    setIsSyncingUserKissID(true);
    const toastId = toast.loading("Updating users with kiss24 UUID...");
    try {
      await axios.post(`/api/kiss24/sync-user-kiss24-uuid`);
      toast.success("Users have been updated", { id: toastId });
    } catch (e: any) { toast.error(e.response?.data?.detail || "Update Failed", { id: toastId }); }
    finally { setIsSyncingUserKissID(false); }
  };

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">

      {/* HEADER BAR */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <ShieldCheck size={22} className="text-emerald-500" /> Keep Secure 24 Integration
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1 max-w-3xl">
            Manage data synchronization between the platform and the Keep Secure 24 external engine.
          </p>
        </div>
      </div>

      {/* TABS */}
      <div className="flex bg-slate-200 dark:bg-zinc-900/80 p-1 rounded-xl w-fit mb-6 shadow-inner border border-slate-200 dark:border-zinc-800/50">
        <button onClick={() => setActiveTab('actions')} className={`flex items-center gap-2 px-5 py-2 text-sm font-bold rounded-lg transition-all ${activeTab === 'actions' ? 'bg-white dark:bg-zinc-800 text-slate-900 dark:text-white shadow-sm' : 'text-slate-500 hover:text-slate-700 dark:text-zinc-400 dark:hover:text-zinc-200'}`}>
          <TerminalSquare size={16} /> Sync Actions
        </button>
        <button onClick={() => setActiveTab('assets')} className={`flex items-center gap-2 px-5 py-2 text-sm font-bold rounded-lg transition-all ${activeTab === 'assets' ? 'bg-white dark:bg-zinc-800 text-slate-900 dark:text-white shadow-sm' : 'text-slate-500 hover:text-slate-700 dark:text-zinc-400 dark:hover:text-zinc-200'}`}>
          <Monitor size={16} /> Synced Assets
        </button>
        <button onClick={() => setActiveTab('tests')} className={`flex items-center gap-2 px-5 py-2 text-sm font-bold rounded-lg transition-all ${activeTab === 'tests' ? 'bg-white dark:bg-zinc-800 text-slate-900 dark:text-white shadow-sm' : 'text-slate-500 hover:text-slate-700 dark:text-zinc-400 dark:hover:text-zinc-200'}`}>
          <LayoutList size={16} /> Synced Tests
        </button>
      </div>

      {/* --- TAB CONTENT: ACTIONS --- */}
      {activeTab === 'actions' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-6 rounded-2xl shadow-sm flex flex-col items-start gap-4 transition-colors hover:border-emerald-300 dark:hover:border-emerald-700">
            <div className="p-3 bg-emerald-50 dark:bg-emerald-500/10 rounded-xl text-emerald-600 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-500/20"><Building2 size={24} /></div>
            <div className="flex-1">
              <h3 className="text-base font-bold text-slate-900 dark:text-zinc-100 mb-1">Sync Organizations</h3>
              <p className="text-xs text-slate-500 dark:text-zinc-400">Fetch and update all missing Keep Secure 24 Organization UUIDs for operating countries currently mapped in the system.</p>
            </div>
            <button onClick={handleGlobalSyncOrg} disabled={isSyncingOrg} className="w-full bg-slate-100 dark:bg-zinc-800 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 text-slate-700 dark:text-zinc-300 hover:text-emerald-600 dark:hover:text-emerald-400 disabled:opacity-50 border border-slate-200 dark:border-zinc-700 px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 transition-colors">
              <RefreshCw size={16} className={isSyncingOrg ? 'animate-spin' : ''} /> {isSyncingOrg ? 'Syncing...' : 'Sync Organizations'}
            </button>
          </div>

          <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-6 rounded-2xl shadow-sm flex flex-col items-start gap-4 transition-colors hover:border-emerald-300 dark:hover:border-emerald-700">
            <div className="p-3 bg-emerald-50 dark:bg-emerald-500/10 rounded-xl text-emerald-600 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-500/20"><Server size={24} /></div>
            <div className="flex-1">
              <h3 className="text-base font-bold text-slate-900 dark:text-zinc-100 mb-1">Sync Asset IDs</h3>
              <p className="text-xs text-slate-500 dark:text-zinc-400">Cross-reference the active asset pool and update matching raw asset profiles with their respective Keep Secure 24 Asset UUIDs.</p>
            </div>
            <button onClick={handleGlobalSyncAsset} disabled={isSyncingAsset} className="w-full bg-slate-100 dark:bg-zinc-800 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 text-slate-700 dark:text-zinc-300 hover:text-emerald-600 dark:hover:text-emerald-400 disabled:opacity-50 border border-slate-200 dark:border-zinc-700 px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 transition-colors">
              <RefreshCw size={16} className={isSyncingAsset ? 'animate-spin' : ''} /> {isSyncingAsset ? 'Syncing...' : 'Sync Assets'}
            </button>
          </div>

          <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-6 rounded-2xl shadow-sm flex flex-col items-start gap-4 transition-colors hover:border-emerald-300 dark:hover:border-emerald-700">
            <div className="p-3 bg-emerald-50 dark:bg-emerald-500/10 rounded-xl text-emerald-600 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-500/20"><UserSquare2 size={24} /></div>
            <div className="flex-1">
              <h3 className="text-base font-bold text-slate-900 dark:text-zinc-100 mb-1">Sync Users</h3>
              <p className="text-xs text-slate-500 dark:text-zinc-400">Fetch Keep Secure 24 UUIDs for all active local users and assign them to the corresponding profiles.</p>
            </div>
            <button onClick={handleSyncKissUserID} disabled={isSyncingUserKissID} className="w-full bg-slate-100 dark:bg-zinc-800 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 text-slate-700 dark:text-zinc-300 hover:text-emerald-600 dark:hover:text-emerald-400 disabled:opacity-50 border border-slate-200 dark:border-zinc-700 px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 transition-colors">
              <RefreshCw size={16} className={isSyncingUserKissID ? 'animate-spin' : ''} /> {isSyncingUserKissID ? 'Syncing...' : 'Sync User Profiles'}
            </button>
          </div>

          <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-6 rounded-2xl shadow-sm flex flex-col items-start gap-4 transition-colors hover:border-blue-300 dark:hover:border-blue-700">
            <div className="p-3 bg-blue-50 dark:bg-blue-500/10 rounded-xl text-blue-600 dark:text-blue-400 border border-blue-100 dark:border-blue-500/20"><Layers size={24} /></div>
            <div className="flex-1">
              <h3 className="text-base font-bold text-slate-900 dark:text-zinc-100 mb-1">Sync Vulnerability Types</h3>
              <p className="text-xs text-slate-500 dark:text-zinc-400">Update contexts, CWE definitions, and core vulnerability types used when drafting new findings.</p>
            </div>
            <button onClick={handleSyncKissVulnTypesID} disabled={isSyncingVulnTypesID} className="w-full bg-slate-100 dark:bg-zinc-800 hover:bg-blue-50 dark:hover:bg-blue-500/10 text-slate-700 dark:text-zinc-300 hover:text-blue-600 dark:hover:text-blue-400 disabled:opacity-50 border border-slate-200 dark:border-zinc-700 px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 transition-colors">
              <RefreshCw size={16} className={isSyncingVulnTypesID ? 'animate-spin' : ''} /> {isSyncingVulnTypesID ? 'Syncing...' : 'Sync Contexts & Types'}
            </button>
          </div>

          <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-6 rounded-2xl shadow-sm flex flex-col items-start gap-4 transition-colors hover:border-blue-300 dark:hover:border-blue-700">
            <div className="p-3 bg-blue-50 dark:bg-blue-500/10 rounded-xl text-blue-600 dark:text-blue-400 border border-blue-100 dark:border-blue-500/20"><Database size={24} /></div>
            <div className="flex-1">
              <h3 className="text-base font-bold text-slate-900 dark:text-zinc-100 mb-1">Update SNow Custom Fields</h3>
              <p className="text-xs text-slate-500 dark:text-zinc-400">Inject the "Service Now ID" custom field into Keep Secure 24 for assets linked during reconciliation.</p>
            </div>
            <button onClick={handleSyncKissSnowID} disabled={isSyncingSnowID} className="w-full bg-slate-100 dark:bg-zinc-800 hover:bg-blue-50 dark:hover:bg-blue-500/10 text-slate-700 dark:text-zinc-300 hover:text-blue-600 dark:hover:text-blue-400 disabled:opacity-50 border border-slate-200 dark:border-zinc-700 px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 transition-colors">
              <RefreshCw size={16} className={isSyncingSnowID ? 'animate-spin' : ''} /> {isSyncingSnowID ? 'Updating Fields...' : 'Sync SNow Fields'}
            </button>
          </div>
        </div>
      )}

      {/* --- TAB CONTENT: ASSETS --- */}
      {activeTab === 'assets' && assetData && (
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-sm overflow-hidden flex flex-col">
          <div className="p-4 border-b border-slate-200 dark:border-zinc-800 flex justify-between items-center bg-slate-50 dark:bg-zinc-950/50 flex-wrap gap-4">
            <div>
              <h2 className="font-bold text-slate-800 dark:text-zinc-100 text-base">Synced Assets Inventory</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                <span className="font-bold text-emerald-600">
                  {totalKiss24Assets && totalKiss24Assets > 0
                    ? `${Math.round((assetData.total_synced / totalKiss24Assets) * 100)}%`
                    : '0%'}
                </span> of Keep Secure 24 assets are synchronized. ({assetData.total_synced} mapped / {totalKiss24Assets || '?'} total KISS24 assets)
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search name or country..."
                  className="pl-9 pr-4 py-2 bg-white dark:bg-zinc-900 border border-slate-300 dark:border-zinc-700 rounded-xl text-xs w-64 focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-zinc-100"
                  value={assetSearch}
                  onChange={e => { setAssetSearch(e.target.value); setAssetPage(1); }}
                />
              </div>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-700 dark:text-zinc-300">
              <thead className="bg-slate-50/80 dark:bg-zinc-900/80 text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider border-b border-slate-200 dark:border-zinc-800">
                <tr>
                  <th className="px-6 py-4 cursor-pointer hover:text-slate-700 dark:hover:text-zinc-300 transition-colors" onClick={() => handleAssetSort('name')}>
                    Asset Name {renderSortIcon(assetSortBy, assetSortDir, 'name')}
                  </th>
                  <th className="px-6 py-4 cursor-pointer hover:text-slate-700 dark:hover:text-zinc-300 transition-colors" onClick={() => handleAssetSort('country')}>
                    Country {renderSortIcon(assetSortBy, assetSortDir, 'country')}
                  </th>
                  <th className="px-6 py-4">SNow ID</th>
                  <th className="px-6 py-4 text-right">Keep Secure 24 Link</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                {assetData.items.map((a: any) => (
                  <tr key={a.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors">
                    <td className="px-6 py-3 font-medium text-slate-900 dark:text-zinc-100">{a.name}</td>
                    <td className="px-6 py-3">{a.country_name || '-'}</td>
                    <td className="px-6 py-3 text-slate-500 font-mono text-xs">{a.snow_number || 'N/A'}</td>
                    <td className="px-6 py-3 text-right">
                      <a href={`https://randstad.eu.vulnmanager.com/assets/${a.kiss24_asset_id}/show`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-blue-600 bg-blue-50 hover:bg-blue-100 dark:text-blue-400 dark:bg-blue-900/20 dark:hover:bg-blue-900/40 rounded-lg transition-colors">
                        View Asset <ExternalLink size={12} />
                      </a>
                    </td>
                  </tr>
                ))}
                {assetData.items.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-8 text-center text-slate-500 italic">No synced assets found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {assetData.total_pages > 1 && (
             <div className="p-3 border-t border-slate-200 dark:border-zinc-800 flex justify-end gap-2 bg-slate-50 dark:bg-zinc-950/50">
                <button disabled={assetPage === 1 || isFetchingAssets} onClick={() => setAssetPage(p => p - 1)} className="p-1.5 rounded-lg border border-slate-200 dark:border-zinc-700 text-slate-600 dark:text-zinc-400 hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-30"><ChevronLeft size={16}/></button>
                <div className="flex items-center px-3 text-xs font-bold text-slate-500">Page {assetPage} of {assetData.total_pages}</div>
                <button disabled={assetPage === assetData.total_pages || isFetchingAssets} onClick={() => setAssetPage(p => p + 1)} className="p-1.5 rounded-lg border border-slate-200 dark:border-zinc-700 text-slate-600 dark:text-zinc-400 hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-30"><ChevronRight size={16}/></button>
             </div>
          )}
        </div>
      )}

      {/* --- TAB CONTENT: TESTS --- */}
      {activeTab === 'tests' && testData && (
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-sm overflow-hidden flex flex-col">
          <div className="p-4 border-b border-slate-200 dark:border-zinc-800 flex justify-between items-center bg-slate-50 dark:bg-zinc-950/50 flex-wrap gap-4">
            <div>
              <h2 className="font-bold text-slate-800 dark:text-zinc-100 text-base">Synced Tests Tracker</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                <span className="font-bold text-emerald-600">{testData.total_synced}</span> of {testData.total_tests} auto-provisioned tests are synchronized.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="relative flex items-center">
                <Filter size={14} className="absolute left-3 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter Lane..."
                  className="pl-8 pr-4 py-2 bg-white dark:bg-zinc-900 border border-slate-300 dark:border-zinc-700 rounded-xl text-xs w-32 focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-zinc-100"
                  value={testLaneFilter}
                  onChange={e => { setTestLaneFilter(e.target.value); setTestPage(1); }}
                />
              </div>
              <select
                className="py-2 px-4 bg-white dark:bg-zinc-900 border border-slate-300 dark:border-zinc-700 rounded-xl text-xs focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-zinc-100"
                value={testStatusFilter}
                onChange={e => { setTestStatusFilter(e.target.value); setTestPage(1); }}
              >
                <option value="">All Statuses</option>
                <option value="NOT_PLANNED">Not Planned</option>
                <option value="SCHEDULED">Scheduled</option>
                <option value="IN_PROGRESS">In Progress</option>
                <option value="STOPPED">Stopped</option>
                <option value="COMPLETED">Completed</option>
              </select>
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search test name..."
                  className="pl-9 pr-4 py-2 bg-white dark:bg-zinc-900 border border-slate-300 dark:border-zinc-700 rounded-xl text-xs w-64 focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-zinc-100"
                  value={testSearch}
                  onChange={e => { setTestSearch(e.target.value); setTestPage(1); }}
                />
              </div>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-700 dark:text-zinc-300">
              <thead className="bg-slate-50/80 dark:bg-zinc-900/80 text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider border-b border-slate-200 dark:border-zinc-800">
                <tr>
                  <th className="px-6 py-4 cursor-pointer hover:text-slate-700 dark:hover:text-zinc-300 transition-colors" onClick={() => handleTestSort('name')}>
                    Test Name {renderSortIcon(testSortBy, testSortDir, 'name')}
                  </th>
                  <th className="px-6 py-4 cursor-pointer hover:text-slate-700 dark:hover:text-zinc-300 transition-colors" onClick={() => handleTestSort('service_lane')}>
                    Service Lane {renderSortIcon(testSortBy, testSortDir, 'service_lane')}
                  </th>
                  <th className="px-6 py-4 cursor-pointer hover:text-slate-700 dark:hover:text-zinc-300 transition-colors" onClick={() => handleTestSort('status')}>
                    Status {renderSortIcon(testSortBy, testSortDir, 'status')}
                  </th>
                  <th className="px-6 py-4 text-right">Keep Secure 24 Link</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                {testData.items.map((t: any) => (
                  <tr key={t.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors">
                    <td className="px-6 py-3 font-medium text-slate-900 dark:text-zinc-100">{t.name}</td>
                    <td className="px-6 py-3">
                       <span className="bg-slate-100 dark:bg-zinc-800 px-2.5 py-1 rounded-md text-xs font-bold">{t.service_lane || '-'}</span>
                    </td>
                    <td className="px-6 py-3">
                       <span className="text-slate-500 font-bold text-xs uppercase tracking-wider">{t.stages?.replace('_', ' ')}</span>
                    </td>
                    <td className="px-6 py-3 text-right">
                      <a href={`https://randstad.eu.vulnmanager.com/tests/${t.kiss24}/show`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-emerald-600 bg-emerald-50 hover:bg-emerald-100 dark:text-emerald-400 dark:bg-emerald-900/20 dark:hover:bg-emerald-900/40 rounded-lg transition-colors">
                        View Test <ExternalLink size={12} />
                      </a>
                    </td>
                  </tr>
                ))}
                {testData.items.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-8 text-center text-slate-500 italic">No synced tests found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {testData.total_pages > 1 && (
             <div className="p-3 border-t border-slate-200 dark:border-zinc-800 flex justify-end gap-2 bg-slate-50 dark:bg-zinc-950/50">
                <button disabled={testPage === 1 || isFetchingTests} onClick={() => setTestPage(p => p - 1)} className="p-1.5 rounded-lg border border-slate-200 dark:border-zinc-700 text-slate-600 dark:text-zinc-400 hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-30"><ChevronLeft size={16}/></button>
                <div className="flex items-center px-3 text-xs font-bold text-slate-500">Page {testPage} of {testData.total_pages}</div>
                <button disabled={testPage === testData.total_pages || isFetchingTests} onClick={() => setTestPage(p => p + 1)} className="p-1.5 rounded-lg border border-slate-200 dark:border-zinc-700 text-slate-600 dark:text-zinc-400 hover:bg-white dark:hover:bg-zinc-800 disabled:opacity-30"><ChevronRight size={16}/></button>
             </div>
          )}
        </div>
      )}

    </div>
  );
}