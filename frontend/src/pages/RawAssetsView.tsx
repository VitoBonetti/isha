import { useState, useEffect } from "react";
import axios from "axios";
import TopNav from "../components/TopNav";
import AddRawAssetModal from "../components/Modals/AddRawAssetModal";
import { Search, Upload, Plus, Filter } from "lucide-react";
import toast, { Toaster } from 'react-hot-toast';

interface RawAsset {
  id: string;
  name: string;
  country_name?: string;
  service_name?: string;
  is_promoted: boolean;
}

export default function RawAssetsView() {
  const [assets, setAssets] = useState<RawAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [page, setPage] = useState(1);

  // Modal & Form State
  const [showAddModal, setShowAddModal] = useState(false);
  const [countries, setCountries] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);

  useEffect(() => {
    fetchRawAssets();
    axios.get('/api/countries/').then(res => setCountries(res.data)).catch(() => {});
    axios.get('/api/services/').then(res => setServices(res.data)).catch(() => {});
    axios.get('/api/board/categories/').then(res => setCategories(res.data)).catch(() => {});
  }, [page]);

  const fetchRawAssets = async () => {
    try {
      setLoading(true);
      const params: any = { page, limit: 50 };
      if (searchTerm) params.search = searchTerm;

      const res = await axios.get("/api/assets/raw", { params });
      setAssets(res.data);
    } catch (error) {
      console.error("Failed to fetch raw assets:", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleAssetSelection = (assetId: string) => {
    setSelectedAssets(prev =>
      prev.includes(assetId)
        ? prev.filter(id => id !== assetId)
        : [...prev, assetId]
    );
  };

  const handlePromoteSelected = async () => {
    if (selectedAssets.length === 0) return;

    try {
      await axios.post("/api/assets/promote", { raw_asset_ids: selectedAssets });
      setSelectedAssets([]);
      fetchRawAssets();
      toast.success(`Successfully promoted ${selectedAssets.length} assets to pool!`);
    } catch (error) {
      toast.error("Failed to promote assets");
    }
  };

  const handleImportExcel = async () => {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.xlsx,.xls';
    fileInput.onchange = async (e: any) => {
      const file = e.target.files[0];
      if (!file) return;

      try {
        const formData = new FormData();
        formData.append('file', file);
        await axios.post('/api/assets/raw/import', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        toast.success("Import started successfully!");
        fetchRawAssets();
      } catch (error) {
        toast.error("Failed to start import");
      }
    };
    fileInput.click();
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100">
      <TopNav />
      <Toaster position="bottom-right" />

      <AddRawAssetModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onSuccess={fetchRawAssets}
        countries={countries}
        services={services}
        categories={categories}
      />

      {/* Header */}
      <div className="pt-24 pb-8 px-6 max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">Raw Assets</h1>
        <p className="text-slate-500 dark:text-zinc-400 mb-8">
          Unprocessed assets ready for review and promotion to the active pool.
        </p>

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
            <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-300 dark:border-zinc-700 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">
              <Filter className="h-4 w-4" />
              Filter
            </button>
          </div>

          <div className="flex items-center gap-3">
            {selectedAssets.length > 0 && (
              <button onClick={handlePromoteSelected} className="px-4 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors font-medium">
                Promote Selected ({selectedAssets.length})
              </button>
            )}
            <button onClick={handleImportExcel} className="flex items-center gap-2 px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 transition-colors font-medium">
              <Upload className="h-4 w-4" />
              Import Excel
            </button>
            <button onClick={() => setShowAddModal(true)} className="flex items-center gap-2 px-4 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors font-medium">
              <Plus className="h-4 w-4" />
              Add Asset
            </button>
          </div>
        </div>

        {/* Assets Table */}
        <div className="mt-8 bg-white dark:bg-zinc-900 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-12 text-center">
              <div className="animate-spin h-8 w-8 border-4 border-emerald-500 border-t-transparent rounded-full mx-auto"></div>
              <p className="mt-4 text-slate-500">Loading raw assets...</p>
            </div>
          ) : (
            <>
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-zinc-800/50 border-b border-slate-200 dark:border-zinc-700">
                  <tr>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Select</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Name</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Country</th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Service Lane</th>
                    <th className="px-6 py-4 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-zinc-700">
                  {assets.map((asset) => (
                    <tr key={asset.id} className={`hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors ${selectedAssets.includes(asset.id) ? 'bg-emerald-50 dark:bg-emerald-900/20' : ''}`}>
                      <td className="px-6 py-4">
                        <input type="checkbox" checked={selectedAssets.includes(asset.id)} onChange={() => toggleAssetSelection(asset.id)} className="h-4 w-4 text-emerald-500 rounded border-slate-300 focus:ring-emerald-500" />
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm font-medium">{asset.name}</div>
                        <div className="text-xs text-slate-500 dark:text-zinc-400 mt-1">ID: {asset.id.substring(0, 8)}...</div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200">
                          {asset.country_name || 'N/A'}
                        </span>
                      </td>
                      <td className="px-6 py-4"><div className="text-sm">{asset.service_name || 'Unassigned'}</div></td>
                      <td className="px-6 py-4 text-right">
                        {asset.is_promoted ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-200">In Pool</span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 dark:bg-zinc-700/30 text-slate-600 dark:text-zinc-400">Raw</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {assets.length > 0 && (
                <div className="px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex items-center justify-between">
                  <p className="text-sm text-slate-500">Showing page {page} of assets</p>
                  <div className="flex gap-2">
                    <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1 rounded-lg border border-slate-300 dark:border-zinc-700 hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed">Previous</button>
                    <button onClick={() => setPage(p => p + 1)} className="px-3 py-1 rounded-lg border border-slate-300 dark:border-zinc-700 hover:bg-slate-100 dark:hover:bg-zinc-800">Next</button>
                  </div>
                </div>
              )}

              {assets.length === 0 && !loading && (
                <div className="p-12 text-center">
                  <p className="text-slate-500 mb-4">No raw assets found</p>
                  <button onClick={handleImportExcel} className="px-4 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors">
                    Import Assets
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}