import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import TopNav from "../components/TopNav";
import AddRawAssetModal from "../components/Modals/AddRawAssetModal";
import { Search, Upload, Plus, Filter, ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import toast, { Toaster } from 'react-hot-toast';

interface RawAsset {
  id: string;
  name: string;
  country_name?: string;
  service_name?: string;
  category_name?: string;
  is_promoted: boolean;
}

export default function RawAssetsView() {
  const [assets, setAssets] = useState<RawAsset[]>([]);
  const [loading, setLoading] = useState(true);

  // Data Params
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Sorting State
  const [sortBy, setSortBy] = useState("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  // Filtering State
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({ country: "", service: "", category: "", status: "" });

  // Modal & Selection State
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);

  // Dropdown Data
  const [countries, setCountries] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);

  // Debounce the search input
  useEffect(() => {
    const timer = setTimeout(() => { setDebouncedSearch(searchTerm); setPage(1); }, 500);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Fetch logic dependent on all parameters
  useEffect(() => {
    fetchRawAssets();
  }, [page, debouncedSearch, sortBy, sortDir, filters]);

  useEffect(() => {
    axios.get('/api/countries/').then(res => setCountries(res.data)).catch(() => {});
    axios.get('/api/services/').then(res => setServices(res.data)).catch(() => {});
    axios.get('/api/board/categories/').then(res => setCategories(res.data)).catch(() => {});
  }, []);

  const fetchRawAssets = async () => {
    try {
      setLoading(true);
      const params: any = {
        page, limit: 50, sort_by: sortBy, sort_dir: sortDir
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (filters.country) params.country_id = filters.country;
      if (filters.service) params.service_id = filters.service;
      if (filters.category) params.category_id = filters.category;
      if (filters.status) params.status = filters.status;

      const res = await axios.get("/api/assets/raw", { params });
      setAssets(res.data);
    } catch (error) {
      toast.error("Failed to fetch raw assets");
    } finally {
      setLoading(false);
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
    if (sortBy !== column) return <ChevronsUpDown size={14} className="opacity-30" />;
    return sortDir === "asc" ? <ChevronUp size={14} className="text-emerald-500" /> : <ChevronDown size={14} className="text-emerald-500" />;
  };

  const toggleAssetSelection = (assetId: string) => {
    setSelectedAssets(prev => prev.includes(assetId) ? prev.filter(id => id !== assetId) : [...prev, assetId]);
  };

  const handlePromoteSelected = async () => {
    if (selectedAssets.length === 0) return;
    try {
      await axios.post("/api/assets/promote", { raw_asset_ids: selectedAssets });
      setSelectedAssets([]);
      fetchRawAssets();
      toast.success(`Promoted ${selectedAssets.length} assets!`);
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
        await axios.post('/api/assets/raw/import', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
        toast.success("Import started!");
        fetchRawAssets();
      } catch (error) {
        toast.error("Import failed");
      }
    };
    fileInput.click();
  };

  const filteredCategories = categories.filter(c => !filters.service || c.service_lane_id === filters.service);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 pb-12">
      <TopNav />
      <Toaster position="bottom-right" />

      <AddRawAssetModal isOpen={showAddModal} onClose={() => setShowAddModal(false)} onSuccess={fetchRawAssets} countries={countries} services={services} categories={categories} />

      <div className="pt-24 px-6 max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">Raw Assets</h1>
        <p className="text-slate-500 dark:text-zinc-400 mb-8">Unprocessed assets ready for review and promotion.</p>

        {/* Toolbar */}
        <div className="flex flex-wrap gap-4 items-center justify-between bg-white dark:bg-zinc-900 p-4 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm relative">
          <div className="flex items-center gap-3 flex-1 min-w-[300px]">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input type="text" placeholder="Search assets..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 focus:ring-2 focus:ring-emerald-500 outline-none" />
            </div>

            <button onClick={() => setShowFilters(!showFilters)} className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors ${showFilters || Object.values(filters).some(v => v !== "") ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 font-bold' : 'border-slate-300 dark:border-zinc-700 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}>
              <Filter className="h-4 w-4" /> Filters
            </button>
          </div>

          <div className="flex items-center gap-3">
            {selectedAssets.length > 0 && (
              <button onClick={handlePromoteSelected} className="px-4 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors font-medium">Promote ({selectedAssets.length})</button>
            )}
            <button onClick={handleImportExcel} className="flex items-center gap-2 px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 transition-colors font-medium"><Upload className="h-4 w-4" /> Import Excel</button>
            <button onClick={() => setShowAddModal(true)} className="flex items-center gap-2 px-4 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors font-medium"><Plus className="h-4 w-4" /> Add Asset</button>
          </div>

          {/* Filter Popover */}
          {showFilters && (
            <div className="absolute top-full left-0 mt-2 w-full max-w-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl p-6 z-20 grid grid-cols-2 gap-4">
              <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Status</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.status} onChange={e => {setFilters({...filters, status: e.target.value}); setPage(1);}}><option value="">All</option><option value="raw">Raw Only</option><option value="pool">In Active Pool</option></select></div>
              <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Country</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.country} onChange={e => {setFilters({...filters, country: e.target.value}); setPage(1);}}><option value="">All Countries</option>{countries.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
              <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Service Lane</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.service} onChange={e => {setFilters({...filters, service: e.target.value, category: ""}); setPage(1);}}><option value="">All Services</option>{services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
              <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Category</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 disabled:opacity-50" value={filters.category} onChange={e => {setFilters({...filters, category: e.target.value}); setPage(1);}} disabled={!filters.service}><option value="">All Categories</option>{filteredCategories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
              <div className="col-span-2 flex justify-end mt-2"><button onClick={() => {setFilters({country: "", service: "", category: "", status: ""}); setPage(1);}} className="text-sm text-blue-500 font-bold hover:text-blue-600">Clear All Filters</button></div>
            </div>
          )}
        </div>

        {/* Table */}
        <div className="mt-6 bg-white dark:bg-zinc-900 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-12 text-center"><div className="animate-spin h-8 w-8 border-4 border-emerald-500 border-t-transparent rounded-full mx-auto"></div><p className="mt-4 text-slate-500">Loading...</p></div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 dark:bg-zinc-800/50 border-b border-slate-200 dark:border-zinc-700">
                <tr>
                  <th className="p-4 w-12"><input type="checkbox" className="h-4 w-4 rounded text-emerald-500" onChange={(e) => { if(e.target.checked) { setSelectedAssets(assets.map(a => a.id)); } else { setSelectedAssets([]); } }} checked={selectedAssets.length === assets.length && assets.length > 0} /></th>
                  <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("name")}><div className="flex items-center gap-2">Name <SortIcon column="name" /></div></th>
                  <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("country")}><div className="flex items-center gap-2">Country <SortIcon column="country" /></div></th>
                  <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("service")}><div className="flex items-center gap-2">Service Lane <SortIcon column="service" /></div></th>
                  <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("category")}><div className="flex items-center gap-2">Category <SortIcon column="category" /></div></th>
                  <th className="p-4 font-semibold text-slate-500 uppercase text-right cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("status")}><div className="flex items-center justify-end gap-2"><SortIcon column="status" /> Status</div></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-zinc-700">
                {assets.map((asset) => (
                  <tr key={asset.id} className={`hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors ${selectedAssets.includes(asset.id) ? 'bg-emerald-50 dark:bg-emerald-900/20' : ''}`}>
                    <td className="p-4"><input type="checkbox" checked={selectedAssets.includes(asset.id)} onChange={() => toggleAssetSelection(asset.id)} className="h-4 w-4 text-emerald-500 rounded border-slate-300" /></td>
                    <td className="p-4">
                      <Link to={`/raw/${asset.id}`} className="font-bold text-blue-600 dark:text-blue-400 hover:underline">{asset.name}</Link>
                      <div className="text-xs text-slate-500 mt-1">{asset.id.substring(0, 8)}</div>
                    </td>
                    <td className="p-4"><span className="inline-flex px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300">{asset.country_name || 'N/A'}</span></td>
                    <td className="p-4 font-medium">{asset.service_name || '-'}</td>
                    <td className="p-4 text-slate-500">{asset.category_name || '-'}</td>
                    <td className="p-4 text-right">
                      {asset.is_promoted ? <span className="inline-flex px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-400">In Pool</span> : <span className="inline-flex px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 dark:bg-zinc-800 text-slate-500 dark:text-zinc-400">Raw</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* Pagination */}
          <div className="px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex justify-between items-center bg-slate-50 dark:bg-zinc-950/50">
            <span className="text-sm text-slate-500">Page {page}</span>
            <div className="flex gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-4 py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium">Prev</button>
              <button onClick={() => setPage(p => p + 1)} disabled={assets.length < 50} className="px-4 py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium">Next</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}