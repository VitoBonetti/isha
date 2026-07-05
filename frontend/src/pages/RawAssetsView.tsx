import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import TopNav from "../components/TopNav";
import AddRawAssetModal from "../components/Modals/AddRawAssetModal";
import { Search, Upload, Plus, Filter, ChevronUp, ChevronDown, ChevronsUpDown, Download, Globe, Database } from "lucide-react";
import toast, { Toaster } from 'react-hot-toast';

interface RawAsset {
  id: string;
  name: string;
  asset_type_name?: string;
  facing_internet: boolean;
  country_code?: string;
  service_name?: string;
  category_name?: string;
  confidentiality_rating: number;
  integrity_rating: number;
  availability_rating: number;
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
  const [filters, setFilters] = useState({
    country: "", service: "", category: "", status: "",
    asset_type: "", facing_internet: "",
    cia_c: "", cia_i: "", cia_a: ""
  });

  // Modal & Selection State
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);

  // Dropdown Data
  const [countries, setCountries] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [assetTypes, setAssetTypes] = useState<any[]>([]);

  useEffect(() => {
    const timer = setTimeout(() => { setDebouncedSearch(searchTerm); setPage(1); }, 500);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => {
    fetchRawAssets();
  }, [page, debouncedSearch, sortBy, sortDir, filters]);

  useEffect(() => {
    axios.get('/api/countries/').then(res => setCountries(res.data)).catch(() => {});
    axios.get('/api/services/').then(res => setServices(res.data)).catch(() => {});
    axios.get('/api/board/categories/').then(res => setCategories(res.data)).catch(() => {});
    axios.get('/api/assets/types').then(res => setAssetTypes(res.data)).catch(() => {});
  }, []);

  const fetchRawAssets = async () => {
    try {
      setLoading(true);
      const params: any = { page, limit: 50, sort_by: sortBy, sort_dir: sortDir };

      if (debouncedSearch) params.search = debouncedSearch;
      if (filters.country) params.country_id = filters.country;
      if (filters.service) params.service_id = filters.service;
      if (filters.category) params.category_id = filters.category;
      if (filters.status) params.status = filters.status;
      if (filters.asset_type) params.asset_type_id = filters.asset_type;
      if (filters.facing_internet !== "") params.facing_internet = filters.facing_internet;
      if (filters.cia_c) params.cia_c = filters.cia_c;
      if (filters.cia_i) params.cia_i = filters.cia_i;
      if (filters.cia_a) params.cia_a = filters.cia_a;

      const res = await axios.get("/api/assets/raw", { params });
      setAssets(res.data);
    } catch (error) {
      toast.error("Failed to fetch raw assets");
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (column: string) => {
    if (sortBy === column) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortBy(column); setSortDir("asc"); }
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

  const handleDownloadTemplate = () => {
    const csvContent = "Name,Description,Asset Type,Country,Service Lane,Category,Facing Internet,Confidentiality,Integrity,Availability\n" +
                       "Primary Banking API,Handles routing.,API,United States,,,TRUE,4,4,4\n" +
                       "Internal HR Portal,Employee management system.,Web Application/Website,United Kingdom,,,FALSE,3,2,1";
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "isha_asset_import_template.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success("Template downloaded!");
  };

  const handleImportExcel = async () => {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.csv,.xlsx,.xls';
    fileInput.onchange = async (e: any) => {
      const file = e.target.files[0];
      if (!file) return;

      const toastId = toast.loading("Processing import...");

      try {
        const formData = new FormData();
        formData.append('file', file);
        const res = await axios.post('/api/assets/raw/import', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

        toast.dismiss(toastId);

        if (res.data.failed && res.data.failed.length > 0) {
          toast.success(`Imported ${res.data.success} assets.`);
          toast.error(`Failed to import ${res.data.failed.length} assets (e.g. ${res.data.failed[0]}). Check system logs for full details.`, { duration: 6000 });
        } else {
          toast.success(`Successfully imported all ${res.data.success} assets!`);
        }
        fetchRawAssets();
      } catch (error) {
        toast.dismiss(toastId);
        toast.error("Import failed entirely. Please check file format.");
      }
    };
    fileInput.click();
  };

  const filteredCategories = categories.filter(c => !filters.service || c.service_lane_id === filters.service);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 pb-12">
      <TopNav />
      <Toaster position="bottom-right" />

      <AddRawAssetModal isOpen={showAddModal} onClose={() => setShowAddModal(false)} onSuccess={fetchRawAssets} countries={countries} services={services} categories={categories} assetTypes={assetTypes} />

      <div className="pt-32 px-6 max-w-7xl mx-auto">
        <h1 className="text-2xl font-extrabold flex items-center gap-2">
          <Database size={28} className="text-slate-500" />
          Raw Assets
        </h1>
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
            <button onClick={handleDownloadTemplate} className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 rounded-lg hover:bg-slate-200 dark:hover:bg-zinc-700 transition-colors font-medium"><Download className="h-4 w-4" /> Template</button>
            <button onClick={handleImportExcel} className="flex items-center gap-2 px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 transition-colors font-medium"><Upload className="h-4 w-4" /> Import Data</button>
            <button onClick={() => setShowAddModal(true)} className="flex items-center gap-2 px-4 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors font-medium"><Plus className="h-4 w-4" /> Add Asset</button>
          </div>

          {/* Filter Popover - Updated to include CIA, Type, Internet */}
          {showFilters && (
            <div className="absolute top-full left-0 mt-2 w-full max-w-4xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl p-6 z-20 grid grid-cols-3 gap-6">
              {/* Column 1: Core Mappings */}
              <div className="space-y-4">
                <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Status</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.status} onChange={e => {setFilters({...filters, status: e.target.value}); setPage(1);}}><option value="">All</option><option value="raw">Raw Only</option><option value="pool">In Active Pool</option></select></div>
                <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Country</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.country} onChange={e => {setFilters({...filters, country: e.target.value}); setPage(1);}}><option value="">All Countries</option>{countries.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
                <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Asset Type</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.asset_type} onChange={e => {setFilters({...filters, asset_type: e.target.value}); setPage(1);}}><option value="">All Types</option>{assetTypes.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
              </div>

              {/* Column 2: Service Mappings & Internet */}
              <div className="space-y-4">
                <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Service Lane</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.service} onChange={e => {setFilters({...filters, service: e.target.value, category: ""}); setPage(1);}}><option value="">All Services</option>{services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
                <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Category</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 disabled:opacity-50" value={filters.category} onChange={e => {setFilters({...filters, category: e.target.value}); setPage(1);}} disabled={!filters.service}><option value="">All Categories</option>{filteredCategories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
                <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Internet Facing</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.facing_internet} onChange={e => {setFilters({...filters, facing_internet: e.target.value}); setPage(1);}}><option value="">Any</option><option value="true">Yes</option><option value="false">No</option></select></div>
              </div>

              {/* Column 3: CIA Ratings (Greater than or equal to) */}
              <div className="space-y-4 bg-slate-50 dark:bg-zinc-950/50 p-4 rounded-xl border border-slate-200 dark:border-zinc-800">
                <h4 className="text-xs font-bold text-slate-500 uppercase mb-2">Min. Risk Ratings (≥)</h4>
                <div><label className="text-xs font-bold text-slate-700 dark:text-zinc-300 block mb-1">Confidentiality</label><input type="number" min="0" max="5" className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.cia_c} onChange={e => {setFilters({...filters, cia_c: e.target.value}); setPage(1);}} /></div>
                <div><label className="text-xs font-bold text-slate-700 dark:text-zinc-300 block mb-1">Integrity</label><input type="number" min="0" max="5" className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.cia_i} onChange={e => {setFilters({...filters, cia_i: e.target.value}); setPage(1);}} /></div>
                <div><label className="text-xs font-bold text-slate-700 dark:text-zinc-300 block mb-1">Availability</label><input type="number" min="0" max="5" className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.cia_a} onChange={e => {setFilters({...filters, cia_a: e.target.value}); setPage(1);}} /></div>
              </div>

              <div className="col-span-3 flex justify-end mt-2 pt-4 border-t border-slate-100 dark:border-zinc-800">
                <button onClick={() => {setFilters({country: "", service: "", category: "", status: "", asset_type: "", facing_internet: "", cia_c: "", cia_i: "", cia_a: ""}); setPage(1);}} className="text-sm text-blue-500 font-bold hover:text-blue-600">Clear All Filters</button>
              </div>
            </div>
          )}
        </div>

        {/* Clean & Compact Table */}
        <div className="mt-6 bg-white dark:bg-zinc-900 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-12 text-center"><div className="animate-spin h-8 w-8 border-4 border-emerald-500 border-t-transparent rounded-full mx-auto"></div><p className="mt-4 text-slate-500">Loading...</p></div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 dark:bg-zinc-800/50 border-b border-slate-200 dark:border-zinc-700">
                <tr>
                  <th className="p-4 w-12"><input type="checkbox" className="h-4 w-4 rounded text-emerald-500" onChange={(e) => { if(e.target.checked) { setSelectedAssets(assets.map(a => a.id)); } else { setSelectedAssets([]); } }} checked={selectedAssets.length === assets.length && assets.length > 0} /></th>
                  <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("name")}><div className="flex items-center gap-2">Asset Details <SortIcon column="name" /></div></th>
                  <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("country")}><div className="flex items-center gap-2">Loc. <SortIcon column="country" /></div></th>
                  <th className="p-4 font-semibold text-slate-500 uppercase">CIA Ratings</th>
                  <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("service")}><div className="flex items-center gap-2">Forecast Lane <SortIcon column="service" /></div></th>
                  <th className="p-4 font-semibold text-slate-500 uppercase text-right cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("status")}><div className="flex items-center justify-end gap-2"><SortIcon column="status" /> Status</div></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-zinc-700">
                {assets.map((asset) => (
                  <tr key={asset.id} className={`hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors ${selectedAssets.includes(asset.id) ? 'bg-emerald-50 dark:bg-emerald-900/20' : ''}`}>
                    <td className="p-4"><input type="checkbox" checked={selectedAssets.includes(asset.id)} onChange={() => toggleAssetSelection(asset.id)} className="h-4 w-4 text-emerald-500 rounded border-slate-300" /></td>
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <Link to={`/raw/${asset.id}`} className="font-bold text-blue-600 dark:text-blue-400 hover:underline">{asset.name}</Link>
                        {asset.facing_internet && <Globe size={14} className="text-blue-500" title="Internet Facing" />}
                      </div>
                      <div className="text-xs text-slate-500 mt-1 flex gap-2 items-center">
                        <span className="font-medium text-slate-700 dark:text-zinc-300">{asset.asset_type_name || 'Unknown Type'}</span>
                        <span>•</span>
                        <span>{asset.id.substring(0, 8)}</span>
                      </div>
                    </td>
                    <td className="p-4"><span className="font-mono font-bold text-slate-500 dark:text-zinc-400">{asset.country_code || '--'}</span></td>
                    <td className="p-4">
                      <div className="flex gap-1.5 text-[10px] font-extrabold font-mono">
                        <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-800 dark:bg-red-500/10 dark:text-red-400">C:{asset.confidentiality_rating || 0}</span>
                        <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 dark:bg-blue-500/10 dark:text-blue-400">I:{asset.integrity_rating || 0}</span>
                        <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-500/10 dark:text-amber-400">A:{asset.availability_rating || 0}</span>
                      </div>
                    </td>
                    <td className="p-4">
                      <div className="font-medium">{asset.service_name || '-'}</div>
                      <div className="text-xs text-slate-500">{asset.category_name || '-'}</div>
                    </td>
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