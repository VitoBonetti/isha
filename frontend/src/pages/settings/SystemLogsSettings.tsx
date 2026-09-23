import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import ConfirmModal from '../../components/Modals/ConfirmModal';
import { Terminal, Download, Trash2, Search, Filter, Calendar, ChevronLeft, ChevronRight, Activity } from 'lucide-react';
import { useSettings } from '../../hooks/useSettings';
import { useAppContext } from "../../context/AppContext";

export default function SystemLogsSettings() {
  const { currentUser } = useAppContext();
  const { handleDelete } = useSettings();

  const isReadOnly = currentUser?.role === 'read_only';

  // --- STATE: DOWNLOAD CSV ---
  const [isDownloading, setIsDownloading] = useState(false);

  // --- STATE: TABS ---
  const [activeTab, setActiveTab] = useState<'recent' | 'search'>('recent');

  // --- STATE: RECENT LOGS ---
  const [bqLogs, setBqLogs] = useState<any[]>([]);
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; endpoint: string; id: string; name: string } | null>(null);

  // --- STATE: SEARCH & FILTERS ---
  const [filterOptions, setFilterOptions] = useState<{
    resource_types: string[];
    actions_by_resource: Record<string, string[]>;
    users: { label: string; values: string[] }[];
  }>({
    resource_types: [],
    actions_by_resource: {},
    users: []
  });

  const [searchForm, setSearchForm] = useState({
    resource_type: '',
    action: '',
    user_id_label: '',
    time_preset: '24h',
    start_date: '',
    end_date: ''
  });

  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchPage, setSearchPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [isSearching, setIsSearching] = useState(false);

  // --- INITIAL DATA FETCH ---
  useEffect(() => {
    // Fetch Recent Logs
    axios.get('/api/system/logs/') // Adjust to your actual recent logs endpoint if different
      .then(res => setBqLogs(res.data))
      .catch(console.error);

    // Fetch Filter Options for Search
    axios.get('/api/system/logs/filters')
      .then(res => setFilterOptions(res.data))
      .catch(err => console.error("Failed to load log filters", err));
  }, []);

  // --- HANDLERS: RECENT LOGS ---
  const confirmDelete = (endpoint: string, id: string, name: string) => setDeleteModal({ isOpen: true, endpoint, id, name });

  const executeDelete = async () => {
    if (deleteModal) {
      await handleDelete(deleteModal.endpoint, deleteModal.id);
      setDeleteModal(null);
      // Refresh recent logs
      axios.get('/api/system/logs/').then(res => setBqLogs(res.data));
    }
  };

  // --- HANDLERS: SEARCH ---
  const handleSearch = async (pageToFetch = 1) => {
    setIsSearching(true);
    try {
      // Find the user object to extract the array of UUIDs/Emails mapping
      const selectedUser = filterOptions.users.find(u => u.label === searchForm.user_id_label);

      const payload = {
        resource_type: searchForm.resource_type || null,
        action: searchForm.action || null,
        user_id_group: selectedUser ? selectedUser.values : null,
        time_preset: searchForm.time_preset !== 'custom' ? searchForm.time_preset : null,
        start_date: searchForm.time_preset === 'custom' && searchForm.start_date ? new Date(searchForm.start_date).toISOString() : null,
        end_date: searchForm.time_preset === 'custom' && searchForm.end_date ? new Date(searchForm.end_date).toISOString() : null,
        page: pageToFetch,
        limit: 100
      };

      const res = await axios.post('/api/system/logs/search', payload);
      setSearchResults(res.data.items);
      setTotalCount(res.data.total_count);
      setTotalPages(res.data.total_pages);
      setSearchPage(res.data.page);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Search failed");
    } finally {
      setIsSearching(false);
    }
  };

  // --- HANDLERS: DOWNLOAD CSV ---
  const handleDownloadSearchCSV = async () => {
    setIsDownloading(true);
    try {
      const selectedUser = filterOptions.users.find(u => u.label === searchForm.user_id_label);

      const payload = {
        resource_type: searchForm.resource_type || null,
        action: searchForm.action || null,
        user_id_group: selectedUser ? selectedUser.values : null,
        time_preset: searchForm.time_preset !== 'custom' ? searchForm.time_preset : null,
        start_date: searchForm.time_preset === 'custom' && searchForm.start_date ? new Date(searchForm.start_date).toISOString() : null,
        end_date: searchForm.time_preset === 'custom' && searchForm.end_date ? new Date(searchForm.end_date).toISOString() : null,
        page: 1, // Ignored by backend CSV generator, but required by schema
        limit: 100
      };

      // We must set responseType to 'blob' so axios handles the binary stream correctly
      const res = await axios.post('/api/system/logs/search/download/csv', payload, {
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'filtered_audit_logs.csv');
      document.body.appendChild(link);
      link.click();
      link.remove();

      toast.success("Download complete!");
    } catch (e: any) {
      toast.error("Failed to download CSV");
    } finally {
      setIsDownloading(false);
    }
  };

  // Trigger a search when the user hits 'Enter' or clicks the search button
  const triggerNewSearch = () => {
    setSearchPage(1);
    handleSearch(1);
  };

  // --- RENDER HELPERS ---
  const renderLogRows = (logs: any[]) => {
    if (!logs || logs.length === 0) {
      return <div className="text-slate-500 italic font-sans p-4 text-center">No logs found matching criteria.</div>;
    }
    return logs.map((log: any, idx: number) => (
      <div key={idx} className="flex gap-3 hover:bg-white/5 p-1 rounded transition-colors whitespace-nowrap">
        <span className="text-emerald-400 shrink-0">[{new Date(log.timestamp).toLocaleString()}]</span>
        <span className="text-blue-400 shrink-0 font-bold w-32 truncate">[{log.action}]</span>
        <span className="text-purple-400 shrink-0 w-32 truncate" title={log.resource_type}>{log.resource_type}</span>
        <span className="text-slate-300 pr-4">{log.details}</span>
        <span className="text-slate-500 ml-auto shrink-0 pl-4 border-l border-slate-800">
          User: {log.user_id?.length > 20 ? log.user_id.substring(0, 15) + '...' : log.user_id} ({log.role})
        </span>
      </div>
    ));
  };

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200 flex flex-col h-full">
      <ConfirmModal
        isOpen={!!deleteModal}
        title="Confirm Deletion"
        message={`Are you sure you want to delete ${deleteModal?.name}? This action cannot be undone.`}
        onConfirm={executeDelete}
        onCancel={() => setDeleteModal(null)}
      />

      {/* Header & Global Actions */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Activity size={22} className="text-slate-500 dark:text-zinc-400" /> Audit Logs
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-0.5">
            Monitor background workers, webhooks, and administrative actions.
          </p>
        </div>
        {!isReadOnly && (
          <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto">

            {activeTab === 'recent' ? (
              <a href="/api/system/logs/download/csv" target="_blank" rel="noopener noreferrer" className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 hover:bg-slate-50 dark:hover:bg-zinc-800 text-slate-700 dark:text-zinc-300 px-4 py-2.5 sm:py-2 rounded-xl flex justify-center items-center gap-2 text-sm font-bold shadow-sm transition-colors">
                <Download size={16} /> Download All Logs
              </a>
            ) : (
              <button
                onClick={handleDownloadSearchCSV}
                disabled={isDownloading}
                className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 hover:bg-slate-50 dark:hover:bg-zinc-800 text-slate-700 dark:text-zinc-300 px-4 py-2.5 sm:py-2 rounded-xl flex justify-center items-center gap-2 text-sm font-bold shadow-sm transition-colors disabled:opacity-50"
              >
                {isDownloading ? <div className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></div> : <Download size={16} />}
                Download Filtered CSV
              </button>
            )}

            <button onClick={() => confirmDelete('/api/system/logs/clear', '', 'All Audit Logs')} className="text-red-600 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/40 px-4 py-2.5 sm:py-2 rounded-xl flex justify-center items-center gap-2 text-sm font-bold shadow-sm transition-colors">
              <Trash2 size={16} /> Delete all Logs
            </button>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex bg-slate-200 dark:bg-zinc-900/80 p-1 rounded-xl w-fit mb-6 shadow-inner border border-slate-200 dark:border-zinc-800/50">
        <button
          onClick={() => setActiveTab('recent')}
          className={`flex items-center gap-2 px-5 py-2 text-sm font-bold rounded-lg transition-all ${
            activeTab === 'recent'
              ? 'bg-white dark:bg-zinc-800 text-slate-900 dark:text-white shadow-sm'
              : 'text-slate-500 dark:text-zinc-400 hover:text-slate-700 dark:hover:text-zinc-200 hover:bg-slate-100/50 dark:hover:bg-zinc-800/30'
          }`}
        >
          <Terminal size={16} /> Recent View
        </button>
        <button
          onClick={() => setActiveTab('search')}
          className={`flex items-center gap-2 px-5 py-2 text-sm font-bold rounded-lg transition-all ${
            activeTab === 'search'
              ? 'bg-white dark:bg-zinc-800 text-slate-900 dark:text-white shadow-sm'
              : 'text-slate-500 dark:text-zinc-400 hover:text-slate-700 dark:hover:text-zinc-200 hover:bg-slate-100/50 dark:hover:bg-zinc-800/30'
          }`}
        >
          <Search size={16} /> Live Search
        </button>
      </div>

      {/* Search Filters UI */}
      {activeTab === 'search' && (
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 mb-6 shadow-sm">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">

            {/* Resource Type */}
            <div>
              <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2">Resource Type</label>
              <select
                value={searchForm.resource_type}
                onChange={(e) => setSearchForm({ ...searchForm, resource_type: e.target.value, action: '' })}
                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 text-slate-900 dark:text-zinc-100 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Resources</option>
                {filterOptions.resource_types.map(rt => (
                  <option key={rt} value={rt}>{rt}</option>
                ))}
              </select>
            </div>

            {/* Action */}
            <div>
              <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2">Action</label>
              <select
                value={searchForm.action}
                onChange={(e) => setSearchForm({ ...searchForm, action: e.target.value })}
                disabled={!searchForm.resource_type}
                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 text-slate-900 dark:text-zinc-100 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              >
                <option value="">All Actions</option>
                {searchForm.resource_type && filterOptions.actions_by_resource[searchForm.resource_type]?.map(act => (
                  <option key={act} value={act}>{act}</option>
                ))}
              </select>
            </div>

            {/* User */}
            <div>
              <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2">User</label>
              <select
                value={searchForm.user_id_label}
                onChange={(e) => setSearchForm({ ...searchForm, user_id_label: e.target.value })}
                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 text-slate-900 dark:text-zinc-100 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Users</option>
                {filterOptions.users.map(u => (
                  <option key={u.label} value={u.label}>{u.label}</option>
                ))}
              </select>
            </div>

            {/* Time Preset */}
            <div>
              <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2">Timeframe</label>
              <select
                value={searchForm.time_preset}
                onChange={(e) => setSearchForm({ ...searchForm, time_preset: e.target.value })}
                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 text-slate-900 dark:text-zinc-100 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Any Time</option>
                <option value="24h">Last 24 Hours</option>
                <option value="7d">Last 7 Days</option>
                <option value="30d">Last 30 Days</option>
                <option value="custom">Custom Date Range...</option>
              </select>
            </div>

            {/* Custom Dates (Conditionally Rendered) */}
            {searchForm.time_preset === 'custom' && (
              <>
                <div>
                  <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1"><Calendar size={12}/> Start Date</label>
                  <input
                    type="datetime-local"
                    value={searchForm.start_date}
                    onChange={(e) => setSearchForm({ ...searchForm, start_date: e.target.value })}
                    className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 text-slate-900 dark:text-zinc-100 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1"><Calendar size={12}/> End Date</label>
                  <input
                    type="datetime-local"
                    value={searchForm.end_date}
                    onChange={(e) => setSearchForm({ ...searchForm, end_date: e.target.value })}
                    className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 text-slate-900 dark:text-zinc-100 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </>
            )}

            {/* Search Button */}
            <div className="md:col-span-4 flex justify-end mt-2">
              <button
                onClick={triggerNewSearch}
                disabled={isSearching}
                className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-xl font-bold text-sm shadow-sm transition-colors flex items-center gap-2 disabled:opacity-50"
              >
                {isSearching ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div> : <Search size={16} />}
                Search Logs
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Terminal View */}
      <div className="bg-[#0c0c0e] rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden flex flex-col flex-1 min-h-[500px] w-full max-w-full">
        <div className="bg-slate-800 px-3 md:px-4 py-3 flex items-center justify-between gap-2 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500 shrink-0"></div>
            <div className="w-3 h-3 rounded-full bg-amber-500 shrink-0"></div>
            <div className="w-3 h-3 rounded-full bg-emerald-500 shrink-0"></div>
            <span className="ml-2 text-[11px] font-mono text-slate-400 font-medium tracking-wider">
              {activeTab === 'recent' ? 'mario_platform.recent_logs (Limit 100)' : `mario_platform.search_results (Total: ${totalCount})`}
            </span>
          </div>

          {/* Pagination Controls (Only visible on Search tab with results) */}
          {activeTab === 'search' && totalPages > 1 && (
            <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
              <button
                disabled={searchPage === 1 || isSearching}
                onClick={() => handleSearch(searchPage - 1)}
                className="hover:text-white disabled:opacity-30 transition-colors"
              >
                <ChevronLeft size={16} />
              </button>
              <span>Page {searchPage} of {totalPages}</span>
              <button
                disabled={searchPage === totalPages || isSearching}
                onClick={() => handleSearch(searchPage + 1)}
                className="hover:text-white disabled:opacity-30 transition-colors"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>

        {/* Terminal Body */}
        <div className="p-4 overflow-auto custom-scrollbar font-mono text-[11px] text-slate-300 flex-1 w-full relative">
          <div className="w-max min-w-full space-y-2">
            {activeTab === 'recent'
              ? renderLogRows(bqLogs)
              : renderLogRows(searchResults)
            }
          </div>
        </div>
      </div>
    </div>
  );
}