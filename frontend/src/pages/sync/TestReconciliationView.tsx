import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { 
  CloudSync, Search, ChevronLeft, ChevronRight, 
  Blocks, Database, AlertCircle, Link2, CheckCircle2, ShieldQuestion, ServerCrash, Copy
} from 'lucide-react';

export default function TestReconciliationView() {
  const currentYear = new Date().getFullYear();
  const [activeTab, setActiveTab] = useState<'database' | 'reconciliation'>('database');
  
  // --- Sync State ---
  const [lastSync, setLastSync] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);

  // --- RITM Database State (Tab 1) ---
  const [ritms, setRitms] = useState([]);
  const [isLoadingRitms, setIsLoadingRitms] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  
  // Unified Search & Sort for DB
  const [dbGlobalSearch, setDbGlobalSearch] = useState('');
  const [dbSort, setDbSort] = useState<'id' | 'name_app' | 'company'>('id');

  // --- Reconciliation State (Tab 2) ---
  const [unmatchedTests, setUnmatchedTests] = useState([]);
  const [unmatchedRitms, setUnmatchedRitms] = useState([]);
  const [isLoadingRecon, setIsLoadingRecon] = useState(false);
  
  // Selections
  const [selectedTestId, setSelectedTestId] = useState(null);
  const [selectedRitmId, setSelectedRitmId] = useState(null);
  const [isLinking, setIsLinking] = useState(false);

  // Reconciliation Filters & Sorting
  const [searchTest, setSearchTest] = useState('');
  const [searchRitm, setSearchRitm] = useState('');
  const [testSort, setTestSort] = useState<'name' | 'country'>('name');
  const [ritmSort, setRitmSort] = useState<'app_name' | 'company'>('app_name');

  // --- Data Fetching ---
  const fetchLastSync = async () => {
    try {
      const res = await axios.get('/api/snow/ritm-last-sync');
      setLastSync(res.data.last_sync);
    } catch (error) {
      console.error("Failed to fetch last sync", error);
    }
  };

  const fetchRitms = async () => {
    setIsLoadingRitms(true);
    try {
      const params = new URLSearchParams({ 
        page: page.toString(), 
        limit: '50',
        sort_by: dbSort 
      });
      
      if (dbGlobalSearch) {
        params.append('global_search', dbGlobalSearch);
      }

      const res = await axios.get(`/api/snow/ritms/current-year?${params.toString()}`);
      setRitms(res.data.items || []);
      setTotalPages(res.data.total_pages || 1);
      setTotalItems(res.data.total_items || 0);
    } catch (error) {
      toast.error("Failed to fetch RITM database.");
    } finally {
      setIsLoadingRitms(false);
    }
  };

  const fetchReconciliationData = async () => {
    setIsLoadingRecon(true);
    try {
      const res = await axios.get('/api/snow/match-tests');
      
      const flatTests: any[] = [];
      res.data.unmatched_tests.forEach((asset: any) => {
        asset.tests.forEach((t: any) => {
          flatTests.push({
            asset_name: asset.name,
            onetrust_id: asset.onetrust_id,
            test_name: t.name,
            test_uuid: t.uuid,
            country_name: t.country_name,
            service_name: t.service_name
          });
        });
      });

      setUnmatchedTests(flatTests);
      setUnmatchedRitms(res.data.unmatched_ritms || []);
      
      setSelectedTestId(null);
      setSelectedRitmId(null);
    } catch (error) {
      toast.error("Failed to fetch reconciliation data.");
    } finally {
      setIsLoadingRecon(false);
    }
  };

  // --- Effects ---
  useEffect(() => {
    fetchLastSync();
  }, []);

  // Debounced Effect for Database Search
  useEffect(() => {
    if (activeTab === 'database') {
      const timeoutId = setTimeout(() => {
        fetchRitms();
      }, 400); // Wait 400ms after last keystroke before querying backend
      
      return () => clearTimeout(timeoutId);
    } else if (activeTab === 'reconciliation') {
      fetchReconciliationData();
    }
  }, [activeTab, page, dbGlobalSearch, dbSort]);


  const handleLinkSelected = async () => {
    if (!selectedTestId || !selectedRitmId) return;
    setIsLinking(true);
    try {
      await axios.post('/api/snow/link-test-ritm', {
        test_id: selectedTestId,
        ritm_id: selectedRitmId
      });
      toast.success("Successfully linked Test to RITM!");
      fetchReconciliationData();
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to link records.");
    } finally {
      setIsLinking(false);
    }
  };

  const handleCopy = (text: string, label: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard!`);
  };

  // --- Reconciliation Tab Filtering & Sorting ---
  const filteredTests = unmatchedTests.filter(t => 
    t.test_name.toLowerCase().includes(searchTest.toLowerCase()) || 
    t.asset_name.toLowerCase().includes(searchTest.toLowerCase()) ||
    (t.onetrust_id && t.onetrust_id.includes(searchTest))
  );

  const sortedTests = [...filteredTests].sort((a, b) => {
    if (testSort === 'name') return (a.test_name || '').localeCompare(b.test_name || '');
    return (a.country_name || '').localeCompare(b.country_name || '');
  });

  const filteredRitms = unmatchedRitms.filter(r => 
    r.id.toLowerCase().includes(searchRitm.toLowerCase()) ||
    (r.name_app && r.name_app.toLowerCase().includes(searchRitm.toLowerCase())) ||
    (r.onetrust_id && r.onetrust_id.includes(searchRitm)) ||
    (r.company && r.company.toLowerCase().includes(searchRitm.toLowerCase()))
  );

  const sortedRitms = [...filteredRitms].sort((a, b) => {
    if (ritmSort === 'app_name') return (a.name_app || '').localeCompare(b.name_app || '');
    return (a.company || '').localeCompare(b.company || '');
  });

  return (
    <div className="flex flex-col h-full gap-6 animate-in fade-in">
      
      {/* Header & Sync Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-zinc-900 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Blocks className="h-6 w-6 text-blue-500" />
            Test & RITM Reconciliation
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1">
            Synchronize ServiceNow RITMs and map them to scheduled Pentests.
          </p>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right hidden sm:block">
            <p className="text-xs text-slate-500 dark:text-zinc-400 uppercase tracking-wider font-semibold">
              Last Sync: <span className="text-sm font-medium text-slate-900 dark:text-zinc-100">{lastSync ? new Date(lastSync).toLocaleString() : 'Never'}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-200 dark:border-zinc-800">
        <button
          onClick={() => setActiveTab('database')}
          className={`flex items-center gap-2 px-4 py-3 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'database' 
              ? 'border-blue-500 text-blue-600 dark:text-blue-400' 
              : 'border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-zinc-300'
          }`}
        >
          <Database className="h-4 w-4" />
          RITM {currentYear}
        </button>
        <button
          onClick={() => setActiveTab('reconciliation')}
          className={`flex items-center gap-2 px-4 py-3 font-medium text-sm border-b-2 transition-colors ${
            activeTab === 'reconciliation' 
              ? 'border-blue-500 text-blue-600 dark:text-blue-400' 
              : 'border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-zinc-300'
          }`}
        >
          <AlertCircle className="h-4 w-4" />
          Orphan Reconciliation
        </button>
      </div>

      {/* TAB CONTENT: RITM DATABASE */}
      {activeTab === 'database' && (
        <div className="flex flex-col gap-4">
          
          {/* Top Controls: Unified Search, Sort, and Pagination Label */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto">
              <div className="relative w-full sm:w-80">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search ID, App, Company, OneTrust..."
                  value={dbGlobalSearch}
                  onChange={(e) => { setDbGlobalSearch(e.target.value); setPage(1); }}
                  className="w-full pl-9 pr-4 py-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                />
              </div>
              <select 
                value={dbSort} 
                onChange={(e) => { setDbSort(e.target.value as any); setPage(1); }}
                className="w-full sm:w-auto bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl text-sm px-3 py-2 outline-none text-slate-600 dark:text-zinc-300 focus:ring-2 focus:ring-blue-500"
              >
                <option value="id">Sort by ID</option>
                <option value="name_app">Sort by Application</option>
                <option value="company">Sort by Company</option>
              </select>
            </div>
            
            <div className="text-sm text-slate-500 dark:text-zinc-400 font-medium">
              Showing page {page} of {totalPages} ({totalItems} total)
            </div>
          </div>

          <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 dark:bg-zinc-950/50 border-b border-slate-200 dark:border-zinc-800 text-slate-500 dark:text-zinc-400">
                  <tr>
                    <th className="px-4 py-3 font-medium">RITM Number</th>
                    <th className="px-4 py-3 font-medium">Application</th>
                    <th className="px-4 py-3 font-medium">Company</th>
                    <th className="px-4 py-3 font-medium">Stage</th>
                    <th className="px-4 py-3 font-medium">OneTrust ID</th>
                    <th className="px-4 py-3 font-medium">Service</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-zinc-800">
                  {isLoadingRitms ? (
                    <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500">Loading...</td></tr>
                  ) : ritms.length === 0 ? (
                    <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500">No RITMs found.</td></tr>
                  ) : (
                    ritms.map((r) => (
                      <tr key={r.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors">
                        <td className="px-4 py-3 font-medium text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                          {r.id}
                          <span onClick={(e) => { e.stopPropagation(); handleCopy(r.id, 'RITM ID'); }} className="text-slate-400 hover:text-blue-500 cursor-pointer"><Copy size={12} /></span>
                        </td>
                        <td className="px-4 py-3 text-slate-600 dark:text-zinc-300 max-w-[200px] truncate">
                          <div className="flex items-center gap-2">
                            <span className="truncate">{r.name_app || '-'}</span>
                            {r.name_app && <span onClick={(e) => { e.stopPropagation(); handleCopy(r.name_app, 'Application'); }} className="text-slate-400 hover:text-blue-500 cursor-pointer flex-shrink-0"><Copy size={12} /></span>}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-slate-600 dark:text-zinc-300">{r.company || '-'}</td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300">
                            {r.stage}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-600 dark:text-zinc-300">{r.onetrust_id || '-'}</td>
                        <td className="px-4 py-3 text-slate-600 dark:text-zinc-300">{r.service_requested || '-'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            
            <div className="flex items-center justify-end px-4 py-3 border-t border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-950/50">
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-1 rounded-lg hover:bg-slate-200 dark:hover:bg-zinc-800 disabled:opacity-50 transition-colors"
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages || totalPages === 0}
                  className="p-1 rounded-lg hover:bg-slate-200 dark:hover:bg-zinc-800 disabled:opacity-50 transition-colors"
                >
                  <ChevronRight className="h-5 w-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB CONTENT: ORPHAN RECONCILIATION */}
      {activeTab === 'reconciliation' && (
        <div className="flex flex-col gap-6 relative">
          
          {/* Sticky Action Bar */}
          {selectedTestId && selectedRitmId && (
            <div className="sticky top-20 z-10 flex items-center justify-between bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 p-4 rounded-xl shadow-md animate-in slide-in-from-top-4">
              <div className="flex items-center gap-3">
                <div className="bg-blue-100 dark:bg-blue-800/50 p-2 rounded-full">
                  <Link2 className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-blue-900 dark:text-blue-100">Ready to Link</p>
                  <p className="text-xs text-blue-700 dark:text-blue-300">1 Test and 1 RITM selected</p>
                </div>
              </div>
              <button
                onClick={handleLinkSelected}
                disabled={isLinking}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-5 py-2 rounded-lg font-medium transition-colors shadow-sm"
              >
                {isLinking ? <CloudSync className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                {isLinking ? 'Linking...' : 'Confirm Link'}
              </button>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            
            {/* LEFT COLUMN: UNMATCHED TESTS */}
            <div className="flex flex-col gap-4 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm min-h-[500px]">
              <div className="flex items-center justify-between border-b border-slate-100 dark:border-zinc-800 pb-3">
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                    <ShieldQuestion className="h-5 w-5 text-amber-500" /> Unmatched Tests
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-zinc-400 mt-0.5">Tests without a linked ServiceNow RITM</p>
                </div>
                <span className="px-2.5 py-1 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 text-xs font-bold rounded-lg">
                  {sortedTests.length}
                </span>
              </div>

              <div className="flex items-center gap-2 relative">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Filter by name or OneTrust ID..."
                    value={searchTest}
                    onChange={(e) => setSearchTest(e.target.value)}
                    className="w-full pl-9 pr-4 py-2 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl text-sm focus:ring-2 focus:ring-amber-500 outline-none transition-all"
                  />
                </div>
                <select 
                  value={testSort} 
                  onChange={(e) => setTestSort(e.target.value as any)}
                  className="bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl text-sm px-3 py-2 outline-none text-slate-600 dark:text-zinc-300 focus:ring-2 focus:ring-amber-500"
                >
                  <option value="name">Sort by Name</option>
                  <option value="country">Sort by Country</option>
                </select>
              </div>

              <div className="flex flex-col gap-3 overflow-y-auto max-h-[600px] pr-2 custom-scrollbar">
                {isLoadingRecon ? (
                  <p className="text-center text-sm text-slate-500 py-10">Loading tests...</p>
                ) : sortedTests.length === 0 ? (
                  <p className="text-center text-sm text-slate-500 py-10">No unmatched tests found.</p>
                ) : (
                  sortedTests.map(t => (
                    <button
                      key={t.test_uuid}
                      onClick={() => setSelectedTestId(selectedTestId === t.test_uuid ? null : t.test_uuid)}
                      className={`text-left p-4 rounded-xl border transition-all ${
                        selectedTestId === t.test_uuid 
                          ? 'border-amber-500 bg-amber-50 dark:bg-amber-900/10 ring-1 ring-amber-500 shadow-md' 
                          : 'border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:border-amber-300 dark:hover:border-amber-700'
                      }`}
                    >
                      <p className="font-semibold text-slate-900 dark:text-zinc-100 text-sm mb-1">{t.test_name}</p>
                      <p className="text-xs text-slate-500 dark:text-zinc-400 mb-2">Asset: {t.asset_name}</p>
                      <div className="inline-flex px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-300">
                        OneTrust ID: {t.onetrust_id || 'Missing'}
                      </div>
                      
                      {/* Expanded Details */}
                      {selectedTestId === t.test_uuid && (
                        <div className="mt-3 pt-3 border-t border-amber-200 dark:border-amber-800/50 flex flex-col gap-1.5">
                           <p className="text-xs text-amber-900 dark:text-amber-100"><span className="font-semibold">Country:</span> {t.country_name || 'N/A'}</p>
                           <p className="text-xs text-amber-900 dark:text-amber-100"><span className="font-semibold">Service:</span> {t.service_name || 'N/A'}</p>
                        </div>
                      )}
                    </button>
                  ))
                )}
              </div>
            </div>

            {/* RIGHT COLUMN: UNMATCHED RITMS */}
            <div className="flex flex-col gap-4 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm min-h-[500px]">
              <div className="flex items-center justify-between border-b border-slate-100 dark:border-zinc-800 pb-3">
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                    <ServerCrash className="h-5 w-5 text-rose-500" /> Unmatched RITMs
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-zinc-400 mt-0.5">RITMs without a scheduled Test</p>
                </div>
                <span className="px-2.5 py-1 bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-400 text-xs font-bold rounded-lg">
                  {sortedRitms.length}
                </span>
              </div>

              <div className="flex items-center gap-2 relative">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Filter by ID, App, or Company..."
                    value={searchRitm}
                    onChange={(e) => setSearchRitm(e.target.value)}
                    className="w-full pl-9 pr-4 py-2 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl text-sm focus:ring-2 focus:ring-rose-500 outline-none transition-all"
                  />
                </div>
                <select 
                  value={ritmSort} 
                  onChange={(e) => setRitmSort(e.target.value as any)}
                  className="bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl text-sm px-3 py-2 outline-none text-slate-600 dark:text-zinc-300 focus:ring-2 focus:ring-rose-500"
                >
                  <option value="app_name">Sort by App Name</option>
                  <option value="company">Sort by Company</option>
                </select>
              </div>

              <div className="flex flex-col gap-3 overflow-y-auto max-h-[600px] pr-2 custom-scrollbar">
                {isLoadingRecon ? (
                  <p className="text-center text-sm text-slate-500 py-10">Loading RITMs...</p>
                ) : sortedRitms.length === 0 ? (
                  <p className="text-center text-sm text-slate-500 py-10">No unmatched RITMs found.</p>
                ) : (
                  sortedRitms.map(r => (
                    <button
                      key={r.id}
                      onClick={() => setSelectedRitmId(selectedRitmId === r.id ? null : r.id)}
                      className={`text-left p-4 rounded-xl border transition-all ${
                        selectedRitmId === r.id 
                          ? 'border-rose-500 bg-rose-50 dark:bg-rose-900/10 ring-1 ring-rose-500 shadow-md' 
                          : 'border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:border-rose-300 dark:hover:border-rose-700'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <p className="font-semibold text-slate-900 dark:text-zinc-100 text-sm flex items-center gap-2">
                          {r.id}
                          <span onClick={(e) => { e.stopPropagation(); handleCopy(r.id, 'RITM ID'); }} className="text-slate-400 hover:text-blue-500 transition-colors p-1">
                            <Copy size={12} />
                          </span>
                        </p>
                      </div>

                      <div className="flex items-center justify-between mb-2">
                        <p className="text-xs text-slate-500 dark:text-zinc-400 truncate max-w-[80%]">
                          App: {r.name_app || 'Unknown'}
                        </p>
                        {r.name_app && (
                          <span onClick={(e) => { e.stopPropagation(); handleCopy(r.name_app, 'Application Name'); }} className="text-slate-400 hover:text-blue-500 transition-colors p-1">
                            <Copy size={12} />
                          </span>
                        )}
                      </div>

                      <div className="inline-flex px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-300">
                        OneTrust ID: {r.onetrust_id || 'Missing'}
                      </div>

                      {/* Expanded Details */}
                      {selectedRitmId === r.id && (
                        <div className="mt-3 pt-3 border-t border-rose-200 dark:border-rose-800/50 flex flex-col gap-1.5">
                           <p className="text-xs text-rose-900 dark:text-rose-100"><span className="font-semibold">Company:</span> {r.company || 'N/A'}</p>
                           <p className="text-xs text-rose-900 dark:text-rose-100"><span className="font-semibold">Stage:</span> {r.stage || 'N/A'}</p>
                           <p className="text-xs text-rose-900 dark:text-rose-100 line-clamp-3"><span className="font-semibold">Desc:</span> {r.description || 'N/A'}</p>
                        </div>
                      )}
                    </button>
                  ))
                )}
              </div>
            </div>

          </div>
        </div>
      )}
    </div>
  );
}