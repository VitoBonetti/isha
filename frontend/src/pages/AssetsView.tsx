// frontend/src/pages/AssetsView.tsx
import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import TopNav from "../components/TopNav";
import ConfirmModal from "../components/Modals/ConfirmModal";
import toast, { Toaster } from "react-hot-toast";
import { Search, Filter, MoveRight, Server, ChevronDown as ChevronDownIcon, Activity, Layers, ChevronsUpDown, ChevronUp } from "lucide-react";

interface PoolAsset {
  id: string;
  raw_asset_id: string;
  name: string;
  asset_type_name?: string;
  country?: string;
  service_name?: string;
  is_assigned: boolean;
  duplicate_allowed: boolean;
  completed_count: number;
}

export default function AssetsView() {
  const [assets, setAssets] = useState<PoolAsset[]>([]);
  const [services, setServices] = useState<any[]>([]); // NEW: Fetch services for the dropdown
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterStatus, setFilterStatus] = useState<"all" | "assigned" | "unassigned">("unassigned");

  // Pagination & Sorting
  const [page, setPage] = useState(1);
  const ITEMS_PER_PAGE = 20;
  const [sortBy, setSortBy] = useState("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  useEffect(() => {
    setPage(1);
  }, [searchTerm, filterStatus, sortBy, sortDir]);

  const handleSort = (column: string) => {
    if (sortBy === column) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortBy(column); setSortDir("asc"); }
  };

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return <ChevronsUpDown className="opacity-30 inline-block" size="{14}"/>;
    return sortDir === "asc" ? <ChevronUp className="text-emerald-500 inline-block" size="{14}"/> : <ChevronDownIcon className="text-emerald-500 inline-block" size="{14}"/>;
  };

  // Selection & Bulk Actions
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [showBulkActions, setShowBulkActions] = useState(false);
  const bulkActionsRef = useRef<HTMLDivElement>(null);

  const [confirmModal, setConfirmModal] = useState<{isOpen: boolean, title: string, message: string, action: 'generate'|null}>({
    isOpen: false, title: "", message: "", action: null
  });

  // NEW: Bulk Service Lane Modal State
  const [serviceModal, setServiceModal] = useState({ isOpen: false, selectedServiceId: "" });

  useEffect(() => {
    fetchPoolAssets();
    // Fetch Services for the new Bulk Update Modal
    axios.get('/api/services/').then(res => setServices(res.data)).catch(console.error);

    const handleClickOutside = (e: MouseEvent) => {
      if (bulkActionsRef.current && !bulkActionsRef.current.contains(e.target as Node)) {
        setShowBulkActions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const fetchPoolAssets = async () => {
    try {
      setLoading(true);
      const res = await axios.get("/api/assets/");
      setAssets(res.data);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 403) {
        toast.error("You don't have permission to view the asset pool");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveFromPool = async (assetId: string, assetName: string) => {
    if (!confirm(`Are you sure you want to return "${assetName}" to the raw data pool?`)) return;

    try {
      await axios.delete(`/api/assets/${assetId}`);
      setAssets(prev => prev.filter(asset => asset.id !== assetId));
      setSelectedAssets(prev => prev.filter(id => id !== assetId));
      toast.success("Asset returned to Raw Pool");
    } catch (error) {
      toast.error("Failed to remove asset");
    }
  };

  const executeBulkAction = async () => {
    if (selectedAssets.length === 0 || !confirmModal.action) return;

    try {
      if (confirmModal.action === 'generate') {
        const toastId = toast.loading("Generating tests...");
        await axios.post("/api/tests/bulk", { asset_ids: selectedAssets });
        toast.dismiss(toastId);
        toast.success(`Generated tests for ${selectedAssets.length} assets! Check the Planner Backlog.`);
      }
      setSelectedAssets([]);
      fetchPoolAssets();
    } catch (error) {
      toast.error("Failed to process bulk action");
    } finally {
      setConfirmModal({ ...confirmModal, isOpen: false });
    }
  };

  // NEW: Handle Bulk Service Lane Update
  const handleBulkServiceUpdate = async () => {
    if (!serviceModal.selectedServiceId || selectedAssets.length === 0) return;
    const toastId = toast.loading("Updating service lanes...");

    try {
      await axios.put('/api/assets/bulk-service', {
        asset_ids: selectedAssets,
        service_lane_id: serviceModal.selectedServiceId
      });
      toast.dismiss(toastId);
      toast.success("Service lanes updated successfully!");
      setServiceModal({ isOpen: false, selectedServiceId: "" });
      setSelectedAssets([]);
      fetchPoolAssets();
    } catch (err) {
      toast.dismiss(toastId);
      toast.error("Failed to update service lanes.");
    }
  };

  const handleGenerateSingleTest = async (assetId: string) => {
    const toastId = toast.loading("Generating test...");
    try {
      await axios.post("/api/tests/bulk", { asset_ids: [assetId] });
      toast.dismiss(toastId);
      toast.success("Test generated! Check the Planner Backlog.");
      fetchPoolAssets();
    } catch (error) {
      toast.dismiss(toastId);
      toast.error("Failed to generate test");
    }
  };

  const toggleAssetSelection = (assetId: string) => {
    setSelectedAssets(prev => prev.includes(assetId) ? prev.filter(id => id !== assetId) : [...prev, assetId]);
  };

  const filteredAssets = assets.filter(asset => {
    const matchesSearch = !searchTerm ||
      asset.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (asset.country && asset.country.toLowerCase().includes(searchTerm.toLowerCase()));

    const isAvailableForTest = !asset.is_assigned || asset.duplicate_allowed;

    if (filterStatus === "assigned") return matchesSearch && asset.is_assigned;
    if (filterStatus === "unassigned") return matchesSearch && isAvailableForTest;
    return matchesSearch;
  });

  const sortedAssets = [...filteredAssets].sort((a, b) => {
    let aVal = "";
    let bVal = "";
    if (sortBy === "name") { aVal = a.name; bVal = b.name; }
    else if (sortBy === "type") { aVal = a.asset_type_name || ""; bVal = b.asset_type_name || ""; }
    else if (sortBy === "country") { aVal = a.country || ""; bVal = b.country || ""; }
    else if (sortBy === "service") { aVal = a.service_name || ""; bVal = b.service_name || ""; }
    else if (sortBy === "status") {
      aVal = a.is_assigned ? (a.duplicate_allowed ? "active (multi)" : "active test") : "ready";
      bVal = b.is_assigned ? (b.duplicate_allowed ? "active (multi)" : "active test") : "ready";
    }

    if (aVal.toLowerCase() < bVal.toLowerCase()) return sortDir === "asc" ? -1 : 1;
    if (aVal.toLowerCase() > bVal.toLowerCase()) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  const totalPages = Math.ceil(sortedAssets.length / ITEMS_PER_PAGE);
  const paginatedAssets = sortedAssets.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

  const stats = {
    total: assets.length,
    assigned: assets.filter(a => a.is_assigned).length,
    unassigned: assets.filter(a => !a.is_assigned || a.duplicate_allowed).length
  };

  // UNLOCKED: Users can now select unassigned assets even if they are missing a Service Lane!
  const validForSelection = filteredAssets.filter(a => !a.is_assigned || a.duplicate_allowed);

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100">
      <TopNav />
      <Toaster position="bottom-right" />

      <ConfirmModal
        isOpen={confirmModal.isOpen}
        title={confirmModal.title}
        message={confirmModal.message}
        confirmText="Confirm"
        onConfirm={executeBulkAction}
        onCancel={() => setConfirmModal({ ...confirmModal, isOpen: false })}
      />

      {/* NEW: Bulk Service Lane Modal */}
      {serviceModal.isOpen && (
        <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 w-full max-w-sm shadow-2xl animate-in zoom-in-95">
            <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
              <Layers size={20} className="text-purple-500" /> Set Service Lane
            </h3>
            <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1">Assign a service lane to {selectedAssets.length} selected assets.</p>
            <select
              className="w-full mt-4 p-2.5 border border-slate-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none"
              value={serviceModal.selectedServiceId}
              onChange={e => setServiceModal({...serviceModal, selectedServiceId: e.target.value})}
            >
              <option value="" disabled>-- Select Lane --</option>
              {services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setServiceModal({isOpen: false, selectedServiceId: ""})} className="px-4 py-2 text-sm font-medium bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors">Cancel</button>
              <button
                onClick={handleBulkServiceUpdate}
                disabled={!serviceModal.selectedServiceId}
                className="px-4 py-2 text-sm font-medium bg-purple-600 hover:bg-purple-700 disabled:bg-slate-300 dark:disabled:bg-zinc-800 text-white rounded-lg shadow-sm transition-colors"
              >
                Apply
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="pt-32 pb-8 px-6 max-w-7xl mx-auto">
        <h1 className="text-2xl font-extrabold flex items-center gap-2">
          <Server size={28} className="text-emerald-500" />
          Active Asset Pool
        </h1>
        <p className="text-slate-500 dark:text-zinc-400 mb-8">
          Select unassigned (or multi-test) assets to generate tests for the Planner Backlog.
        </p>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm">
            <p className="text-sm text-slate-500 dark:text-zinc-400 mb-1">Total Assets</p>
            <p className="text-3xl font-bold text-emerald-600">{stats.total}</p>
          </div>

          <div className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm">
            <p className="text-sm text-slate-500 dark:text-zinc-400 mb-1">Actively Testing</p>
            <p className="text-3xl font-bold text-blue-600">{stats.assigned}</p>
          </div>

          <div className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm">
            <p className="text-sm text-slate-500 dark:text-zinc-400 mb-1">Ready for Generation</p>
            <p className="text-3xl font-bold text-amber-600">{stats.unassigned}</p>
          </div>
        </div>

        {/* Actions Bar */}
        <div className="flex flex-wrap gap-4 items-center justify-between bg-white dark:bg-zinc-900 p-4 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm">
          <div className="flex items-center gap-3 flex-1 min-w-[300px]">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search assets..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none"
              />
            </div>

            <button
              onClick={() => setFilterStatus(filterStatus === "all" ? "assigned" : filterStatus === "assigned" ? "unassigned" : "all")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors text-sm font-medium ${filterStatus !== 'all' ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400' : 'border-slate-300 dark:border-zinc-700 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}
            >
              <Filter className="h-4 w-4" />
              {filterStatus === "all" ? "All Statuses" : filterStatus === "assigned" ? "Active Tests Only" : "Ready Only"}
            </button>
          </div>

          <div className="flex items-center gap-3">
            {selectedAssets.length > 0 && (
              <div className="relative" ref={bulkActionsRef}>
                <button onClick={() => setShowBulkActions(!showBulkActions)} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium">
                  Actions ({selectedAssets.length}) <ChevronDown size={16}/>
                </button>
                {showBulkActions && (
                  <div className="absolute top-full right-0 mt-2 w-56 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl py-2 z-30 animate-in fade-in zoom-in-95 overflow-hidden">
                    <button
                      onClick={() => {
                        setShowBulkActions(false);
                        // PROTECTION: Check if any selected asset is missing a lane!
                        const missingLanes = selectedAssets.filter(id => !assets.find(a => a.id === id)?.service_name);
                        if (missingLanes.length > 0) {
                          toast.error(`${missingLanes.length} selected assets are missing a Service Lane! Please assign one first.`);
                          return;
                        }
                        setConfirmModal({isOpen: true, action: 'generate', title: "Generate Tests", message: `Are you sure you want to generate Planner Tests for these ${selectedAssets.length} assets? This will move them to the Planner Backlog.`});
                      }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-bold hover:bg-slate-50 dark:hover:bg-zinc-800 text-slate-700 dark:text-zinc-300 transition-colors"
                    >
                      <Activity size={16} className="text-blue-500" /> Generate Tests
                    </button>
                    <div className="h-px bg-slate-100 dark:bg-zinc-800 my-0.5"></div>
                    <button
                      onClick={() => {
                        setShowBulkActions(false);
                        setServiceModal({ isOpen: true, selectedServiceId: "" });
                      }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-bold hover:bg-slate-50 dark:hover:bg-zinc-800 text-slate-700 dark:text-zinc-300 transition-colors"
                    >
                      <Layers size={16} className="text-purple-500" /> Set Service Lane
                    </button>
                  </div>
                )}
              </div>
            )}
            <span className="text-sm text-slate-500 dark:text-zinc-400">
              {filteredAssets.length} results
            </span>
          </div>
        </div>

        {/* Assets List */}
        <div className="mt-8 bg-white dark:bg-zinc-900 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-12 text-center">
              <div className="animate-spin h-8 w-8 border-4 border-emerald-500 border-t-transparent rounded-full mx-auto"></div>
              <p className="mt-4 text-slate-500">Loading pool assets...</p>
            </div>
          ) : (
            <>
              <table className="w-full">
                <thead
                    className="bg-slate-50 dark:bg-zinc-800/50 border-b border-slate-200 dark:border-zinc-700 select-none">
                <tr>
                  <th className="p-4 w-12 text-center">
                    <input type="checkbox" ... />
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors"
                      onClick={() => handleSort("name")}>
                    <div className="flex items-center gap-1.5">Asset Name <SortIcon column="name"/></div>
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors"
                      onClick={() => handleSort("type")}>
                    <div className="flex items-center gap-1.5">Type <SortIcon column="type"/></div>
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors"
                      onClick={() => handleSort("country")}>
                    <div className="flex items-center gap-1.5">Country <SortIcon column="country"/></div>
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors"
                      onClick={() => handleSort("service")}>
                    <div className="flex items-center gap-1.5">Service Lane <SortIcon column="service"/></div>
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors"
                      onClick={() => handleSort("status")}>
                    <div className="flex items-center gap-1.5">Status <SortIcon column="status"/></div>
                  </th>
                  <th className="px-6 py-4 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Actions</th>
                </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-zinc-700">
                {paginatedAssets.map((asset) => {
                  const isSelected = selectedAssets.includes(asset.id);
                  return (
                      <tr key={asset.id}
                          className={`hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors ${isSelected ? 'bg-blue-50 dark:bg-blue-900/10' : ''}`}>
                        <td className="p-4 text-center">
                          <input
                              type="checkbox"
                              disabled={(asset.is_assigned && !asset.duplicate_allowed)}
                              checked={isSelected}
                              onChange={() => toggleAssetSelection(asset.id)}
                              className="h-4 w-4 text-blue-600 rounded border-slate-300 disabled:opacity-40"
                          />
                        </td>
                        <td className="px-6 py-4">
                          <div>
                            <Link
                                to={`/raw/${asset.raw_asset_id}`}
                                state={{from: '/assets', label: 'Active Pool'}}
                                className="text-sm font-bold text-blue-600 dark:text-blue-400 hover:underline"
                            >
                              {asset.name}
                            </Link>
                            <div className="text-xs text-slate-500 dark:text-zinc-400 mt-1">Pool
                              ID: {asset.id.substring(0, 8)}...
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div
                              className="text-sm font-medium text-slate-700 dark:text-zinc-300">{asset.asset_type_name || 'Unknown'}</div>
                        </td>
                        <td className="px-6 py-4">
                          <span
                              className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-50 dark:bg-indigo-900/30 text-indigo-800 dark:text-indigo-400">
                            {asset.country || 'N/A'}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          {asset.service_name ? (
                              <div className="text-sm font-medium">{asset.service_name}</div>
                          ) : (
                              <span
                                  className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800 dark:bg-red-500/10 dark:text-red-400 border border-red-200 dark:border-red-500/20">
                              MISSING SERVICE LANE
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex flex-col gap-1.5 items-start">
                            {asset.is_assigned ? (
                                asset.duplicate_allowed ? (
                                    <span
                                        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-200">
                                  <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse"></div> Active (Multi)
                                </span>
                                ) : (
                                    <span
                                        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200">
                                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></div> Active Test
                                </span>
                                )
                            ) : (
                                <span
                                    className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-200 shadow-sm border border-emerald-200 dark:border-emerald-800">
                                Ready
                              </span>
                            )}

                            {asset.completed_count > 0 && (
                                <span
                                    className="text-[10px] font-bold text-slate-500 dark:text-zinc-400 bg-slate-100 dark:bg-zinc-800 px-2 py-0.5 rounded-md">
                                Tested {asset.completed_count} {asset.completed_count === 1 ? 'time' : 'times'}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {((!asset.is_assigned || asset.duplicate_allowed) && asset.service_name) && (
                                <button
                                    onClick={() => handleGenerateSingleTest(asset.id)}
                                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-blue-200 dark:border-blue-900/50 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors text-sm font-bold shadow-sm"
                                    title="Generate new test in Backlog"
                                >
                                  <Activity className="h-3.5 w-3.5"/>
                                  Generate
                                </button>
                            )}
                            <button
                                onClick={() => handleRemoveFromPool(asset.id, asset.name)}
                                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-500 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors text-sm"
                                title="Return to Raw Pool"
                            >
                              <MoveRight className="h-3.5 w-3.5"/>
                            </button>
                          </div>
                        </td>
                      </tr>
                  );
                })}
                </tbody>
              </table>
              {sortedAssets.length === 0 && !loading && (
                <div className="p-12 text-center">
                  <p className="text-slate-500 mb-4">No assets found</p>
                  <p className="text-sm text-slate-400">{searchTerm ? "Try adjusting your search" : "No assets in the pool yet"}</p>
                </div>
              )}
              {sortedAssets.length > 0 && !loading && (
                <div className="px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex justify-between items-center bg-slate-50 dark:bg-zinc-950/50">
                  <span className="text-sm text-slate-500">Page {page} of {totalPages || 1}</span>
                  <div className="flex gap-2">
                    <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-4 py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors">Prev</button>
                    <button onClick={() => setPage(p => p + 1)} disabled={page >= totalPages} className="px-4 py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors">Next</button>
                  </div>
                </div>
              )}
              {filteredAssets.length === 0 && !loading && (
                  <div className="p-12 text-center">
                    <p className="text-slate-500 mb-4">No assets found</p>
                    <p className="text-sm text-slate-400">
                      {searchTerm ? "Try adjusting your search" : "No assets in the pool yet"}
                    </p>
                  </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}