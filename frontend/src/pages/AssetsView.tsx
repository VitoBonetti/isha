import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import TopNav from "../components/TopNav";
import ConfirmModal from "../components/Modals/ConfirmModal";
import toast, { Toaster } from "react-hot-toast";
import { Search, Filter, MoveRight, Server, ChevronDown, Activity } from "lucide-react";

interface PoolAsset {
  id: string;
  raw_asset_id: string;
  name: string;
  asset_type_name?: string;
  country?: string;
  service_name?: string;
  is_assigned: boolean;
}

export default function AssetsView() {
  const [assets, setAssets] = useState<PoolAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterStatus, setFilterStatus] = useState<"all" | "assigned" | "unassigned">("unassigned");

  // Selection & Bulk Actions
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [showBulkActions, setShowBulkActions] = useState(false);
  const bulkActionsRef = useRef<HTMLDivElement>(null);

  const [confirmModal, setConfirmModal] = useState<{isOpen: boolean, title: string, message: string, action: 'generate'|null}>({
    isOpen: false, title: "", message: "", action: null
  });

  useEffect(() => {
    fetchPoolAssets();

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
      console.error("Failed to fetch pool assets:", error);
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
      fetchPoolAssets(); // Refresh to show them as assigned
    } catch (error) {
      toast.error("Failed to process bulk action");
    } finally {
      setConfirmModal({ ...confirmModal, isOpen: false });
    }
  };

  const toggleAssetSelection = (assetId: string) => {
    setSelectedAssets(prev => prev.includes(assetId) ? prev.filter(id => id !== assetId) : [...prev, assetId]);
  };

  const filteredAssets = assets.filter(asset => {
    const matchesSearch = !searchTerm ||
      asset.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (asset.country && asset.country.toLowerCase().includes(searchTerm.toLowerCase()));

    if (filterStatus === "assigned") return matchesSearch && asset.is_assigned;
    if (filterStatus === "unassigned") return matchesSearch && !asset.is_assigned;
    return matchesSearch;
  });

  const stats = {
    total: assets.length,
    assigned: assets.filter(a => a.is_assigned).length,
    unassigned: assets.filter(a => !a.is_assigned).length
  };

  // Only allow unassigned assets to be checked for test generation
  const unassignedFiltered = filteredAssets.filter(a => !a.is_assigned);

  // Only allow unassigned assets WITH a Service Lane to be checked for test generation
  const validUnassigned = filteredAssets.filter(a => !a.is_assigned && a.service_name);

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

      {/* Header */}
      <div className="pt-32 pb-8 px-6 max-w-7xl mx-auto">
        <h1 className="text-2xl font-extrabold flex items-center gap-2">
          <Server size={28} className="text-emerald-500" />
          Active Asset Pool
        </h1>
        <p className="text-slate-500 dark:text-zinc-400 mb-8">
          Select unassigned assets to generate tests for the Planner Backlog.
        </p>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm">
            <p className="text-sm text-slate-500 dark:text-zinc-400 mb-1">Total Assets</p>
            <p className="text-3xl font-bold text-emerald-600">{stats.total}</p>
          </div>

          <div className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm">
            <p className="text-sm text-slate-500 dark:text-zinc-400 mb-1">Tests Generated</p>
            <p className="text-3xl font-bold text-blue-600">{stats.assigned}</p>
          </div>

          <div className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm">
            <p className="text-sm text-slate-500 dark:text-zinc-400 mb-1">Unassigned (Ready)</p>
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
              {filterStatus === "all" ? "All Statuses" : filterStatus === "assigned" ? "Tests Generated" : "Unassigned Only"}
            </button>
          </div>

          <div className="flex items-center gap-3">
            {selectedAssets.length > 0 && (
              <div className="relative" ref={bulkActionsRef}>
                <button onClick={() => setShowBulkActions(!showBulkActions)} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium">
                  Actions ({selectedAssets.length}) <ChevronDown size={16}/>
                </button>
                {showBulkActions && (
                  <div className="absolute top-full right-0 mt-2 w-56 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl py-2 z-30 animate-in fade-in zoom-in-95">
                    <button
                      onClick={() => { setShowBulkActions(false); setConfirmModal({isOpen: true, action: 'generate', title: "Generate Tests", message: `Are you sure you want to generate Planner Tests for these ${selectedAssets.length} assets? This will move them to the Planner Backlog.`}); }}
                      className="w-full flex items-center gap-2 px-4 py-2 text-sm font-bold hover:bg-slate-50 dark:hover:bg-zinc-800 text-slate-700 dark:text-zinc-300"
                    >
                      <Activity size={16} className="text-blue-500" /> Generate Tests
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
                <thead className="bg-slate-50 dark:bg-zinc-800/50 border-b border-slate-200 dark:border-zinc-700">
                  <tr>
                    <th className="p-4 w-12 text-center">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded text-blue-600 border-slate-300 disabled:opacity-50"
                        onChange={(e) => {
                          if(e.target.checked) setSelectedAssets(validUnassigned.map(a => a.id));
                          else setSelectedAssets([]);
                        }}
                        checked={selectedAssets.length === validUnassigned.length && validUnassigned.length > 0}
                        disabled={validUnassigned.length === 0}
                      />
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Asset Name</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Type</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Country</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Service Lane</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-4 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-zinc-700">
                  {filteredAssets.map((asset) => {
                    const isSelected = selectedAssets.includes(asset.id);
                    return (
                      <tr key={asset.id} className={`hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors ${isSelected ? 'bg-blue-50 dark:bg-blue-900/10' : ''}`}>
                        <td className="p-4 text-center">
                          <input
                            type="checkbox"
                            disabled={asset.is_assigned || !asset.service_name} // <-- Lock if missing lane
                            checked={isSelected}
                            onChange={() => toggleAssetSelection(asset.id)}
                            className="h-4 w-4 text-blue-600 rounded border-slate-300 disabled:opacity-40"
                          />
                        </td>
                        <td className="px-6 py-4">
                          <div>
                            <Link
                              to={`/raw/${asset.raw_asset_id}`}
                              state={{ from: '/assets', label: 'Active Pool' }}
                              className="text-sm font-bold text-blue-600 dark:text-blue-400 hover:underline"
                            >
                              {asset.name}
                            </Link>
                            <div className="text-xs text-slate-500 dark:text-zinc-400 mt-1">Pool ID: {asset.id.substring(0, 8)}...</div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-sm font-medium text-slate-700 dark:text-zinc-300">{asset.asset_type_name || 'Unknown'}</div>
                        </td>
                        <td className="px-6 py-4">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-50 dark:bg-indigo-900/30 text-indigo-800 dark:text-indigo-400">
                            {asset.country || 'N/A'}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          {asset.service_name ? (
                            <div className="text-sm font-medium">{asset.service_name}</div>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800 dark:bg-red-500/10 dark:text-red-400 border border-red-200 dark:border-red-500/20">
                              MISSING SERVICE LANE
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          {asset.is_assigned ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-200">
                              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
                              Test Generated
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-400">
                              <div className="w-1.5 h-1.5 rounded-full bg-amber-500"></div>
                              Ready
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <button
                            onClick={() => handleRemoveFromPool(asset.id, asset.name)}
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-500 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors text-sm"
                          >
                            <MoveRight className="h-3.5 w-3.5" />
                            Return
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

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