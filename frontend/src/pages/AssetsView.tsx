import { useState, useEffect } from "react";
import axios from "axios";
import TopNav from "../components/TopNav";
import { Search, Filter, MoveRight, AlertCircle } from "lucide-react";

interface PoolAsset {
  id: string;
  name: string;
  country?: string;
  service_forecast?: string;
  is_assigned: boolean;
}

export default function AssetsView() {
  const [assets, setAssets] = useState<PoolAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterStatus, setFilterStatus] = useState<"all" | "assigned" | "unassigned">("all");

  useEffect(() => {
    fetchPoolAssets();
  }, []);

  const fetchPoolAssets = async () => {
    try {
      setLoading(true);
      const res = await axios.get("/api/assets/");
      setAssets(res.data);
    } catch (error) {
      console.error("Failed to fetch pool assets:", error);
      if (axios.isAxiosError(error) && error.response?.status === 403) {
        alert("You don't have permission to view the asset pool");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveFromPool = async (assetId: string, assetName: string) => {
    if (!confirm(`Are you sure you want to remove "${assetName}" from the active pool?`)) {
      return;
    }

    try {
      await axios.delete(`/api/assets/${assetId}`);
      setAssets(prev => prev.filter(asset => asset.id !== assetId));
      alert("Asset removed from pool");
    } catch (error) {
      console.error("Failed to remove asset:", error);
      alert("Failed to remove asset");
    }
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

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100">
      <TopNav />
      
      {/* Header */}
      <div className="pt-24 pb-8 px-6 max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">Active Asset Pool</h1>
        <p className="text-slate-500 dark:text-zinc-400 mb-8">
          Assets currently in the pool and ready for testing assignments.
        </p>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm">
            <p className="text-sm text-slate-500 dark:text-zinc-400 mb-1">Total Assets</p>
            <p className="text-3xl font-bold text-emerald-600">{stats.total}</p>
          </div>
          
          <div className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm">
            <p className="text-sm text-slate-500 dark:text-zinc-400 mb-1">Assigned</p>
            <p className="text-3xl font-bold text-blue-600">{stats.assigned}</p>
          </div>
          
          <div className="bg-white dark:bg-zinc-900 p-6 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm">
            <p className="text-sm text-slate-500 dark:text-zinc-400 mb-1">Unassigned</p>
            <p className="text-3xl font-bold text-amber-600">{stats.unassigned}</p>
          </div>
        </div>

        {/* Actions Bar */}
        <div className="flex flex-wrap gap-4 items-center justify-between bg-white dark:bg-zinc-900 p-4 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm">
          <div className="flex items-center gap-3 flex-1 min-w-[300px]">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search assets..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
              />
            </div>
            
            <button 
              onClick={() => setFilterStatus(filterStatus === "all" ? "assigned" : filterStatus === "assigned" ? "unassigned" : "all")}
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-300 dark:border-zinc-700 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
            >
              <Filter className="h-4 w-4" />
              {filterStatus === "all" ? "All Statuses" : filterStatus === "assigned" ? "Assigned Only" : "Unassigned Only"}
            </button>
          </div>

          <div className="flex items-center gap-3">
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
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      Asset Name
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      Country
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      Service Lane
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-4 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-zinc-700">
                  {filteredAssets.map((asset) => (
                    <tr key={asset.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors">
                      <td className="px-6 py-4">
                        <div>
                          <div className="text-sm font-medium">{asset.name}</div>
                          <div className="text-xs text-slate-500 dark:text-zinc-400 mt-1">ID: {asset.id.substring(0, 8)}...</div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200">
                          {asset.country || 'N/A'}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm">{asset.service_forecast || 'Unassigned'}</div>
                      </td>
                      <td className="px-6 py-4">
                        {asset.is_assigned ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-200">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
                            Assigned
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 dark:bg-zinc-700/30 text-slate-600 dark:text-zinc-400">
                            <div className="w-1.5 h-1.5 rounded-full bg-slate-400"></div>
                            Unassigned
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => handleRemoveFromPool(asset.id, asset.name)}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors text-sm"
                        >
                          <MoveRight className="h-3.5 w-3.5" />
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
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