import { useState, useEffect } from "react";
import axios from "axios";
import TopNav from "../components/TopNav";
import TestHistoryModal from "../components/Modals/TestHistoryModal";
import SecureNoteModal from "../components/Modals/SecureNoteModal";
import ConfirmModal from "../components/Modals/ConfirmModal";
import toast, { Toaster } from "react-hot-toast";
import { Search, ShieldAlert, Calendar, ChevronsUpDown, ChevronUp, ChevronDown, LockOpen, Lock, FolderOpen, FolderPlus } from "lucide-react";
import { useAppContext } from "../context/AppContext";
import type { Test } from "../types/board";

export default function TestsView() {
  const { currentUser } = useAppContext();
  const [tests, setTests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  // Filtering States
  const [filterYear, setFilterYear] = useState<string>("All");
  const [filterService, setFilterService] = useState<string>("All");
  const [filterStatus, setFilterStatus] = useState<string>("All");

  const [historyTest, setHistoryTest] = useState<Test | null>(null);

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
  }, []);

  // Reset to page 1 whenever any filter or sort order changes
  useEffect(() => {
    setPage(1);
  }, [searchTerm, filterYear, filterService, filterStatus, sortBy, sortDir]);

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

  // Extract unique services dynamically for the dropdown
  const uniqueServices = Array.from(new Set(tests.map(t => t.service_lane_name).filter(Boolean))).sort();

  // 1. Filter
  const filteredTests = tests.filter(test => {
    // Text Search
    const matchesSearch = test.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (test.assigned_pentesters && test.assigned_pentesters.toLowerCase().includes(searchTerm.toLowerCase()));

    // Dropdown Filters
    const matchesYear = filterYear === "All" || String(test.start_year) === filterYear;
    const matchesService = filterService === "All" || test.service_lane_name === filterService;

    // Status Logic
    let matchesStatus = true;
    if (filterStatus !== "All") {
      const s = test.status.toUpperCase();
      if (filterStatus === "Backlog") matchesStatus = (s === "NOT_PLANNED" || s === "NOT PLANNED");
      else matchesStatus = (s === filterStatus.toUpperCase());
    }

    return matchesSearch && matchesYear && matchesService && matchesStatus;
  });

  // 2. Sort
  const sortedTests = [...filteredTests].sort((a, b) => {
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
    const s = status.toUpperCase();
    if (s === "COMPLETED") return <span className="px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-wider bg-emerald-100 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20">Completed</span>;
    if (s === "STOPPED") return <span className="px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-wider bg-red-100 text-red-800 dark:bg-red-500/10 dark:text-red-400 border border-red-200 dark:border-red-500/20">Stopped</span>;
    if (s === "NOT_PLANNED" || s === "NOT PLANNED") return <span className="px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-wider bg-slate-100 text-slate-800 dark:bg-zinc-800 dark:text-zinc-400 border border-slate-200 dark:border-zinc-700">Backlog</span>;
    return <span className="px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-wider bg-blue-100 text-blue-800 dark:bg-blue-500/10 dark:text-blue-400 border border-blue-200 dark:border-blue-500/20">Scheduled</span>;
  };

  const selectStyles = "px-4 py-2 rounded-lg border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm font-bold text-slate-700 dark:text-zinc-300 outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer";

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100 pb-12">
      <TopNav />
      <Toaster position="bottom-right" />

      {historyTest && <TestHistoryModal test={historyTest} onClose={() => setHistoryTest(null)} />}
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

      <div className="pt-32 px-6 max-w-7xl mx-auto">
        <h1 className="text-2xl font-extrabold flex items-center gap-2">
          <ShieldAlert size={28} className="text-indigo-500" />
          Test Registry
        </h1>
        <p className="text-slate-500 dark:text-zinc-400 mb-8">Comprehensive read-only log of all tests, stages, and assignments.</p>

        {/* Action Bar with New Filters */}
        <div className="bg-white dark:bg-zinc-900 p-4 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm mb-6 flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="relative w-full max-w-md shrink-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input type="text" placeholder="Search by test name or pentester..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 focus:ring-2 focus:ring-indigo-500 outline-none text-sm" />
          </div>

          <div className="flex flex-wrap justify-end items-center gap-3">
            <select value={filterService} onChange={e => setFilterService(e.target.value)} className={selectStyles}>
              <option value="All">All Services</option>
              {uniqueServices.map(s => <option key={s as string} value={s as string}>{s as string}</option>)}
            </select>

            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className={selectStyles}>
              <option value="All">All Statuses</option>
              <option value="Scheduled">Scheduled</option>
              <option value="Backlog">Backlog</option>
              <option value="Completed">Completed</option>
              <option value="Stopped">Stopped</option>
            </select>

            <select value={filterYear} onChange={e => setFilterYear(e.target.value)} className={selectStyles}>
              <option value="All">All Years</option>
              <option value="2025">2025</option>
              <option value="2026">2026</option>
              <option value="2027">2027</option>
              <option value="2028">2028</option>
              <option value="2029">2029</option>
              <option value="2030">2030</option>
              <option value="2031">2031</option>
              <option value="null">Unscheduled</option>
            </select>

            <div className="text-sm font-bold text-slate-500 bg-slate-100 dark:bg-zinc-800 px-3 py-1.5 rounded-lg shrink-0">
              {filteredTests.length} Tests
            </div>
          </div>
        </div>

        <div className="bg-white dark:bg-zinc-900 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden flex flex-col">
          {loading ? (
            <div className="p-12 text-center text-slate-500">Loading tests...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
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
                    <th className="p-4 font-semibold text-slate-500 uppercase tracking-wider">Schedule</th>
                    <th className="p-4 font-semibold text-slate-500 uppercase tracking-wider">Assigned To</th>
                    <th
                      className="p-4 font-semibold text-slate-500 uppercase tracking-wider text-right cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
                      onClick={() => handleSort("status")}
                    >
                      <div className="flex items-center justify-end gap-2"><SortIcon column="status" /> Status</div>
                    </th>
                    <th className="p-4 w-12 text-center"></th> {/* Empty header for Lock icon */}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-zinc-700">
                  {paginatedTests.map((test) => (
                    <tr key={test.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors">
                      <td className="p-4">
                        <button
                          onClick={() => setHistoryTest(test)}
                          className="font-bold text-blue-600 dark:text-blue-400 hover:underline text-left"
                        >
                          {test.name}
                        </button>
                      </td>
                      <td className="p-4">
                        <span className="font-medium text-slate-700 dark:text-zinc-300">{test.service_lane_name || 'N/A'}</span>
                      </td>
                      <td className="p-4">
                        {test.start_week ? (
                          <div className="flex items-center gap-1.5 text-slate-700 dark:text-zinc-300 font-medium">
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
                      <td className="p-4 text-right">
                         {getStatusPill(test.status)}
                      </td>
                      <td className="p-4 text-center">
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
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {filteredTests.length === 0 && !loading && (
            <div className="p-12 text-center text-slate-500">No tests match your search.</div>
          )}

          {/* Pagination Footer */}
          {!loading && filteredTests.length > 0 && (
            <div className="px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex justify-between items-center bg-slate-50 dark:bg-zinc-950/50 mt-auto">
              <span className="text-sm text-slate-500">Page {page} of {totalPages || 1}</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-4 py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors"
                >
                  Prev
                </button>
                <button
                  onClick={() => setPage(p => p + 1)}
                  disabled={page >= totalPages}
                  className="px-4 py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors"
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