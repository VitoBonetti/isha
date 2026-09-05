import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import TopNav from "../components/TopNav";
import SecureNoteModal from "../components/Modals/SecureNoteModal";
import ConfirmModal from "../components/Modals/ConfirmModal";
import toast, { Toaster } from "react-hot-toast";
import { Search, ShieldAlert, Calendar, ChevronsUpDown, ChevronUp, ChevronDown, LockOpen, Lock, FolderOpen, FolderPlus, Database, Filter } from "lucide-react";
import { useAppContext } from "../context/AppContext";
import type { Test } from "../types/board";

export default function TestsView() {
  const { currentUser } = useAppContext();
  const [tests, setTests] = useState<any[]>([]);
  const [assetTypes, setAssetTypes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Filtering States
  const [searchTerm, setSearchTerm] = useState("");
  const [filterYear, setFilterYear] = useState<string>("All");
  const [filterService, setFilterService] = useState<string>("All");
  const [filterStatus, setFilterStatus] = useState<string>("All");
  const [filterAssetType, setFilterAssetType] = useState<string>("All");
  const [filterIsKpi, setFilterIsKpi] = useState<"All" | "true" | "false">("All");
  const [filterIsCritical, setFilterIsCritical] = useState<"All" | "true" | "false">("All");
  const [filterPentester, setFilterPentester] = useState<string>("All");

  const [showFilters, setShowFilters] = useState(false);
  const filterRef = useRef<HTMLDivElement>(null);
  const filterBtnRef = useRef<HTMLButtonElement>(null);

  // Pagination State
  const [page, setPage] = useState(1);
  const ITEMS_PER_PAGE = 50;

  // Sorting State
  const [sortBy, setSortBy] = useState<string>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  // Secret note
  const [secretTarget, setSecretTarget] = useState<Test | null>(null);
  const [secretConfirmOpen, setSecretConfirmOpen] = useState<Test | null>(null);

  useEffect(() => {
    fetchTests();
    axios.get('/api/assets/types').then(res => setAssetTypes(res.data)).catch(console.error);

    const handleClickOutside = (e: MouseEvent) => {
      if (filterRef.current && !filterRef.current.contains(e.target as Node) && filterBtnRef.current && !filterBtnRef.current.contains(e.target as Node)) {
        setShowFilters(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Reset to page 1 whenever any filter or sort order changes
  useEffect(() => {
    setPage(1);
  }, [searchTerm, filterYear, filterService, filterStatus, filterAssetType, filterIsKpi, filterIsCritical, filterPentester, sortBy, sortDir]);

  const fetchTests = async () => {
    try {
      setLoading(true);
      const res = await axios.get("/api/tests/");
      setTests(res.data);
    } catch (error) {
      toast.error("Failed to load tests.");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateWorkspace = async (testId: string) => {
      const toastId = toast.loading("Provisioning workspace...");
      try {
        await axios.post(`/api/tests/${testId}/workspace`);
        toast.dismiss(toastId);
        toast.success("Workspace creation started! The board will refresh shortly.");
      } catch (error) {
        toast.dismiss(toastId);
        toast.error("Failed to create workspace.");
      }
    };

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(column);
      setSortDir("asc");
    }
  };

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return <ChevronsUpDown size={14} className="opacity-30 inline-block" />;
    return sortDir === "asc" ? <ChevronUp size={14} className="text-emerald-500 inline-block" /> : <ChevronDown size={14} className="text-emerald-500 inline-block" />;
  };

  // Extract unique filter dropdown options dynamically
  const uniqueServices = Array.from(new Set(tests.map(t => t.service_lane_name).filter(Boolean))).sort();
  const uniqueYears = Array.from(new Set(tests.map(t => t.start_year).filter(Boolean))).sort((a, b) => Number(b) - Number(a));
  const uniquePentesters = Array.from(new Set(tests.flatMap(t => (t.assigned_pentesters || "Unassigned").split(", ")))).filter(p => p !== "Unassigned").sort();

  // 1. Filter
  const filteredTests = tests.filter(test => {
    // Text Search
    const matchesSearch = test.name.toLowerCase().includes(searchTerm.toLowerCase());

    // Dropdown Filters
    const matchesYear = filterYear === "All" || String(test.start_year) === filterYear || (filterYear === "null" && !test.start_year);
    const matchesService = filterService === "All" || test.service_lane_name === filterService;
    const matchesAssetType = filterAssetType === "All" || test.asset_type_name === filterAssetType;
    const matchesIsKpi = filterIsKpi === "All" || (filterIsKpi === "true" ? test.is_kpi : !test.is_kpi);
    const matchesIsCritical = filterIsCritical === "All" || (filterIsCritical === "true" ? test.is_critical : !test.is_critical);

    const assignedArray = (test.assigned_pentesters || "Unassigned").split(", ");
    const matchesPentester = filterPentester === "All" || assignedArray.includes(filterPentester);

    // Status Logic
    let matchesStatus = true;
    if (filterStatus !== "All") {
      const s = test.status?.toUpperCase() || "";
      if (filterStatus === "Backlog") matchesStatus = (s === "NOT_PLANNED" || s === "NOT PLANNED");
      else matchesStatus = (s === filterStatus.toUpperCase());
    }

    return matchesSearch && matchesYear && matchesService && matchesStatus && matchesAssetType && matchesIsKpi && matchesIsCritical && matchesPentester;
  });

  // 2. Sort
  const sortedTests = [...filteredTests].sort((a, b) => {
    if (sortBy === "schedule") {
      const yearA = a.start_year || 0;
      const yearB = b.start_year || 0;
      const weekA = a.start_week || 0;
      const weekB = b.start_week || 0;

      if (yearA !== yearB) return sortDir === "asc" ? yearA - yearB : yearB - yearA;
      return sortDir === "asc" ? weekA - weekB : weekB - weekA;
    }

    let aValue = "";
    let bValue = "";

    if (sortBy === "name") {
      aValue = a.name || "";
      bValue = b.name || "";
    } else if (sortBy === "service") {
      aValue = a.service_lane_name || "";
      bValue = b.service_lane_name || "";
    } else if (sortBy === "status") {
      aValue = a.status || "";
      bValue = b.status || "";
    }

    if (aValue.toLowerCase() < bValue.toLowerCase()) return sortDir === "asc" ? -1 : 1;
    if (aValue.toLowerCase() > bValue.toLowerCase()) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  // 3. Paginate
  const totalPages = Math.ceil(sortedTests.length / ITEMS_PER_PAGE);
  const paginatedTests = sortedTests.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

  const getStatusPill = (status: string) => {
    const s = status?.toUpperCase() || "";
    if (s === "COMPLETED") return <span className="px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-wider bg-emerald-100 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20">Completed</span>;
    if (s === "STOPPED") return <span className="px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-wider bg-red-100 text-red-800 dark:bg-red-500/10 dark:text-red-400 border border-red-200 dark:border-red-500/20">Stopped</span>;
    if (s === "NOT_PLANNED" || s === "NOT PLANNED") return <span className="px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-wider bg-slate-100 text-slate-800 dark:bg-zinc-800 dark:text-zinc-400 border border-slate-200 dark:border-zinc-700">Backlog</span>;
    return <span className="px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-wider bg-blue-100 text-blue-800 dark:bg-blue-500/10 dark:text-blue-400 border border-blue-200 dark:border-blue-500/20">Scheduled</span>;
  };

  const selectStyles = "w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-sm outline-none focus:ring-2 focus:ring-indigo-500";

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100 pb-12">
      <TopNav />
      <Toaster position="bottom-right" />

      <ConfirmModal
        isOpen={!!secretConfirmOpen}
        variant="secure"
        title="Access Secure Vault"
        message="You are about to decrypt sensitive credentials. Proceed?"
        confirmText="Decrypt & Open"
        onConfirm={() => { setSecretTarget(secretConfirmOpen); setSecretConfirmOpen(null); }}
        onCancel={() => setSecretConfirmOpen(null)}
      />
      {secretTarget && <SecureNoteModal test={secretTarget} onClose={() => { setSecretTarget(null); fetchTests(); }} />}

      <div className="pt-28 md:pt-32 px-4 md:px-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-extrabold flex items-center gap-2">
            <ShieldAlert size={28} className="text-indigo-500" />
            Test Registry
          </h1>
          {!loading && (
            <span className="bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 text-xs font-bold px-2.5 py-1 rounded-full border border-slate-200 dark:border-zinc-700 shadow-sm mt-1">
              {filteredTests.length} Found
            </span>
          )}
        </div>
        <p className="text-slate-500 dark:text-zinc-400 mb-6 md:mb-8 text-sm md:text-base">Comprehensive read-only log of all tests, stages, and assignments.</p>

        {/* Actions Bar with Advanced Dropdown Filters */}
        <div className="flex flex-col gap-4 bg-white dark:bg-zinc-900 p-4 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm relative z-10 mb-6">
          <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 w-full">
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 flex-1 w-full">
              <div className="relative w-full md:max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search by test name..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 md:py-2 rounded-lg border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 focus:ring-2 focus:ring-indigo-500 outline-none text-sm"
                />
              </div>

              <button
                ref={filterBtnRef}
                onClick={() => setShowFilters(!showFilters)}
                className={`w-full sm:w-auto flex justify-center items-center gap-2 px-4 py-2.5 md:py-2 rounded-lg border transition-colors text-sm ${showFilters ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-400 font-bold' : 'border-slate-300 dark:border-zinc-700 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}
              >
                <Filter className="h-4 w-4" /> Advanced Filters
              </button>

              {/* Quick Filter: Year */}
              <select value={filterYear} onChange={e => setFilterYear(e.target.value)} className={`${selectStyles} max-w-[120px] font-bold border-slate-300 dark:border-zinc-700`}>
                <option value="All">All Years</option>
                {uniqueYears.map(year => <option key={year as number} value={String(year)}>{year as number}</option>)}
                <option value="null">Unscheduled</option>
              </select>
            </div>
          </div>

          {/* Advanced Filters Popover */}
          {showFilters && (
            <div ref={filterRef} className="absolute top-full left-0 right-0 mt-2 w-full bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl p-4 md:p-6 z-20 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6 animate-in fade-in slide-in-from-top-2">
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Status</label>
                  <select className={selectStyles} value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
                    <option value="All">All Statuses</option>
                    <option value="Scheduled">Scheduled</option>
                    <option value="Backlog">Backlog</option>
                    <option value="Completed">Completed</option>
                    <option value="Stopped">Stopped</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Pentester</label>
                  <select className={selectStyles} value={filterPentester} onChange={e => setFilterPentester(e.target.value)}>
                    <option value="All">All Pentesters</option>
                    <option value="Unassigned">Unassigned</option>
                    {uniquePentesters.map(p => <option key={p as string} value={p as string}>{p as string}</option>)}
                  </select>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Service Lane</label>
                  <select className={selectStyles} value={filterService} onChange={e => setFilterService(e.target.value)}>
                    <option value="All">All Services</option>
                    {uniqueServices.map(s => <option key={s as string} value={s as string}>{s as string}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Asset Type</label>
                  <select className={selectStyles} value={filterAssetType} onChange={e => setFilterAssetType(e.target.value)}>
                    <option value="All">All Types</option>
                    {assetTypes.map(t => <option key={t.id} value={t.name}>{t.name}</option>)}
                  </select>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Is KPI</label>
                  <select className={selectStyles} value={filterIsKpi} onChange={e => setFilterIsKpi(e.target.value as any)}>
                    <option value="All">Any</option>
                    <option value="true">Yes</option>
                    <option value="false">No</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Is Critical</label>
                  <select className={selectStyles} value={filterIsCritical} onChange={e => setFilterIsCritical(e.target.value as any)}>
                    <option value="All">Any</option>
                    <option value="true">Yes</option>
                    <option value="false">No</option>
                  </select>
                </div>
              </div>

              <div className="sm:col-span-2 lg:col-span-4 flex justify-end mt-2 pt-4 border-t border-slate-100 dark:border-zinc-800">
                <button onClick={() => {
                  setFilterStatus("All"); setFilterService("All"); setFilterYear("All");
                  setFilterAssetType("All"); setFilterIsKpi("All"); setFilterIsCritical("All");
                  setFilterPentester("All"); setPage(1);
                }} className="text-sm text-indigo-500 font-bold hover:text-indigo-600 p-2 transition-colors">
                  Clear All Filters
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden flex flex-col w-full">
          {loading ? (
            <div className="p-12 text-center text-slate-500 text-sm">Loading tests...</div>
          ) : (
            <>
              {/* DESKTOP VIEW: Standard Table */}
              <table className="hidden md:table w-full text-left text-sm">
                <thead className="bg-slate-50 dark:bg-zinc-800/50 border-b border-slate-200 dark:border-zinc-700 select-none">
                  <tr>
                    <th
                      className="p-4 font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
                      onClick={() => handleSort("name")}
                    >
                      <div className="flex items-center gap-2">Test Details <SortIcon column="name" /></div>
                    </th>
                    <th
                      className="p-4 font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
                      onClick={() => handleSort("service")}
                    >
                      <div className="flex items-center gap-2">Service Lane <SortIcon column="service" /></div>
                    </th>
                    <th
                      className="p-4 font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
                      onClick={() => handleSort("schedule")}
                    >
                      <div className="flex items-center gap-2">Schedule <SortIcon column="schedule" /></div>
                    </th>
                    <th className="p-4 font-semibold text-slate-500 uppercase tracking-wider">Assigned To</th>
                    <th
                      className="p-4 font-semibold text-slate-500 uppercase tracking-wider text-right cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
                      onClick={() => handleSort("status")}
                    >
                      <div className="flex items-center justify-end gap-2"><SortIcon column="status" /> Status</div>
                    </th>
                    <th className="p-4 w-12 text-center"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-zinc-700">
                  {paginatedTests.map((test) => (
                    <tr key={test.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors">
                      <td className="p-4 max-w-[200px]">
                        <div className="flex flex-col">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Link
                              to={`/tests/${test.id}`}
                              state={{ from: '/tests', label: 'Test Registry' }}
                              className="font-bold text-blue-600 dark:text-blue-400 hover:underline text-left truncate block max-w-full"
                              title={`View Test Details: ${test.name}`}
                            >
                              {test.name}
                            </Link>
                            {test.is_kpi && <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 flex-shrink-0">KPI</span>}
                            {test.is_critical && <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 flex-shrink-0">CRIT</span>}
                          </div>
                          {test.asset_type_name && (
                            <span className="text-[11px] text-slate-500 dark:text-zinc-400 mt-1">{test.asset_type_name}</span>
                          )}
                        </div>
                      </td>
                      <td className="p-4">
                        <div className="flex flex-col gap-1 items-start">
                          <span className="font-medium text-slate-700 dark:text-zinc-300 whitespace-nowrap">
                            {test.service_lane_name || 'N/A'}
                          </span>
                          {test.category_name && (
                            <span className="text-[10px] font-bold bg-slate-100 text-slate-600 dark:bg-zinc-800 dark:text-zinc-400 px-1.5 py-0.5 rounded uppercase tracking-wider">
                              {test.category_name}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="p-4">
                        {test.start_week ? (
                          <div className="flex items-center gap-1.5 text-slate-700 dark:text-zinc-300 font-medium whitespace-nowrap">
                            <Calendar size={14} className="text-slate-400"/> Wk {test.start_week}, {test.start_year}
                            {test.duration_weeks > 1 && <span className="text-xs text-slate-500">({test.duration_weeks} wks)</span>}
                          </div>
                        ) : (
                          <span className="text-slate-400 italic">Unscheduled</span>
                        )}
                      </td>
                      <td className="p-4 font-medium text-slate-600 dark:text-zinc-400">
                        {test.assigned_pentesters}
                      </td>
                      <td className="p-4 text-right whitespace-nowrap">
                         {getStatusPill(test.status)}
                      </td>
                      <td className="p-4 text-center">
                        <div className="flex items-center justify-end gap-1">
                          {currentUser?.role === 'admin' && test.raw_asset_id && (
                            <Link
                              to={`/raw/${test.raw_asset_id}`}
                              state={{ from: '/tests', label: 'Test Registry' }}
                              className="p-1.5 text-emerald-500 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/30 rounded transition-colors flex items-center"
                              title="View Raw Asset Info"
                            >
                              <Database size={14} />
                            </Link>
                          )}
                          {test.drive_folder_url ? (
                            <a
                              href={test.drive_folder_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              title="Open Google Drive Workspace"
                              className="p-1.5 text-blue-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors flex items-center"
                            >
                              <FolderOpen size={14} />
                            </a>
                          ) : (
                            currentUser?.role === 'admin' && test.auto_provision_workspace && (
                              <button
                                title="Create Drive Workspace"
                                className="p-1.5 text-slate-400 hover:text-emerald-500 hover:bg-emerald-50 dark:hover:bg-emerald-900/30 rounded transition-colors"
                                onClick={() => handleCreateWorkspace(test.id)}
                              >
                                <FolderPlus size={14} />
                              </button>
                            )
                          )}
                          {currentUser?.role !== 'read_only' && (test.has_secret || test.is_service_active && test.auto_provision_workspace) && (
                            <button
                              onClick={() => setSecretConfirmOpen(test)}
                              className={`p-1.5 rounded transition-colors ${test.has_secret ? 'text-indigo-600 bg-indigo-100 dark:bg-indigo-900/30' : 'text-slate-400 hover:text-indigo-500 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}
                              title={test.has_secret ? "View Secure Note" : "Add Secure Note"}
                            >
                              {test.has_secret ? <Lock size={14} /> : <LockOpen size={14} />}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* MOBILE VIEW: Stacked Cards */}
              <div className="flex md:hidden flex-col divide-y divide-slate-100 dark:divide-zinc-800 w-full">
              {paginatedTests.map((test) => (
                <div key={test.id} className="p-4 flex flex-col gap-3">
                  <div className="flex justify-between items-start gap-2">
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Link
                          to={`/tests/${test.id}`}
                          state={{ from: '/tests', label: 'Test Registry' }}
                          className="font-bold text-sm text-blue-600 dark:text-blue-400 hover:underline text-left break-words"
                        >
                          {test.name}
                        </Link>
                        {test.is_kpi && <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300">KPI</span>}
                        {test.is_critical && <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300">CRIT</span>}
                      </div>
                      {test.asset_type_name && (
                        <span className="text-[11px] text-slate-500 dark:text-zinc-400 mt-0.5">{test.asset_type_name}</span>
                      )}
                    </div>

                    <div className="flex shrink-0 gap-1">
                      {currentUser?.role === 'admin' && test.raw_asset_id && (
                        <Link
                          to={`/raw/${test.raw_asset_id}`}
                          state={{ from: '/tests', label: 'Test Registry' }}
                          className="p-1.5 text-emerald-500 bg-emerald-50 dark:bg-emerald-900/20 rounded transition-colors"
                          title="View Raw Asset Info"
                        >
                          <Database size={14} />
                        </Link>
                      )}
                      {test.drive_folder_url ? (
                        <a
                          href={test.drive_folder_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1.5 text-blue-500 bg-blue-50 dark:bg-blue-900/20 rounded transition-colors"
                        >
                          <FolderOpen size={14} />
                        </a>
                      ) : (
                        currentUser?.role === 'admin' && test.auto_provision_workspace && (
                          <button
                            className="p-1.5 text-slate-400 hover:text-emerald-500 bg-slate-100 dark:bg-zinc-800 rounded transition-colors"
                            onClick={() => handleCreateWorkspace(test.id)}
                          >
                            <FolderPlus size={14} />
                          </button>
                        )
                      )}
                      {currentUser?.role !== 'read_only' && (test.has_secret || test.is_service_active && test.auto_provision_workspace) && (
                        <button
                          onClick={() => setSecretConfirmOpen(test)}
                          className={`p-1.5 rounded transition-colors ${test.has_secret ? 'text-indigo-600 bg-indigo-100 dark:bg-indigo-900/30' : 'text-slate-400 bg-slate-100 dark:bg-zinc-800'}`}
                        >
                          {test.has_secret ? <Lock size={14} /> : <LockOpen size={14} />}
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 mt-1">
                    <div className="flex flex-col gap-0.5 items-start">
                      <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Service Lane</span>
                      <span className="text-xs font-medium text-slate-700 dark:text-zinc-300 truncate">{test.service_lane_name || 'N/A'}</span>
                      {test.category_name && (
                        <span className="mt-0.5 text-[9px] font-bold bg-slate-100 text-slate-600 dark:bg-zinc-800 dark:text-zinc-400 px-1.5 py-0.5 rounded uppercase tracking-wider truncate max-w-full">
                          {test.category_name}
                        </span>
                      )}
                    </div>
                    <div className="flex flex-col gap-0.5 items-end">
                      <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Status</span>
                      {getStatusPill(test.status)}
                    </div>
                  </div>

                  <div className="flex flex-col gap-2 mt-1 bg-slate-50 dark:bg-zinc-950/50 p-2.5 rounded-lg border border-slate-100 dark:border-zinc-800">
                     <div className="flex items-center gap-1.5 text-xs text-slate-700 dark:text-zinc-300 font-medium">
                        <Calendar size={12} className="text-slate-400"/>
                        {test.start_week ? (
                          <span>Wk {test.start_week}, {test.start_year} {test.duration_weeks > 1 && <span className="text-slate-500 ml-1">({test.duration_weeks} wks)</span>}</span>
                        ) : (
                          <span className="text-slate-400 italic">Unscheduled</span>
                        )}
                      </div>
                      <div className="text-xs text-slate-600 dark:text-zinc-400">
                        <span className="font-bold text-slate-400 mr-1">Team:</span>
                        {test.assigned_pentesters || <span className="italic">Unassigned</span>}
                      </div>
                  </div>
                </div>
              ))}
              </div>
            </>
          )}

          {filteredTests.length === 0 && !loading && (
            <div className="p-12 text-center text-slate-500 text-sm">No tests match your search.</div>
          )}

          {/* Pagination Footer */}
          {!loading && filteredTests.length > 0 && (
            <div className="px-4 md:px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex flex-col sm:flex-row justify-between items-center gap-4 sm:gap-0 bg-slate-50 dark:bg-zinc-950/50 mt-auto">
              <span className="text-xs md:text-sm text-slate-500">Page {page} of {totalPages || 1}</span>
              <div className="flex gap-2 w-full sm:w-auto">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white dark:bg-zinc-900"
                >
                  Prev
                </button>
                <button
                  onClick={() => setPage(p => p + 1)}
                  disabled={page >= totalPages}
                  className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white dark:bg-zinc-900"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}