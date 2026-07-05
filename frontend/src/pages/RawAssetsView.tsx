import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import TopNav from "../components/TopNav";
import AddRawAssetModal from "../components/Modals/AddRawAssetModal";
import ConfirmModal from "../components/Modals/ConfirmModal";
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
  business_critical: number;
  is_promoted: boolean;
}

export default function RawAssetsView() {
  const [assets, setAssets] = useState<RawAsset[]>([]);
  const [loading, setLoading] = useState(true);

  // Data Params
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Sorting & Filtering
  const [sortBy, setSortBy] = useState("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    country: "", service: "", category: "", status: "",
    asset_type: "", facing_internet: "", business_critical: ""
  });

  // Modal & Selection State
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);

  // Bulk Actions
  const [showBulkActions, setShowBulkActions] = useState(false);
  const bulkActionsRef = useRef<HTMLDivElement>(null);
  const [confirmModal, setConfirmModal] = useState<{isOpen: boolean, title: string, message: string, action: 'promote'|'delete'|null}>({
    isOpen: false, title: "", message: "", action: null
  });

  // Dropdown Data
  const [countries, setCountries] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [assetTypes, setAssetTypes] = useState<any[]>([]);

  useEffect(() => {
    const timer = setTimeout(() => { setDebouncedSearch(searchTerm); setPage(1); }, 500);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => { fetchRawAssets(); }, [page, debouncedSearch, sortBy, sortDir, filters]);

  useEffect(() => {
    axios.get('/api/countries/').then(res => setCountries(res.data)).catch(() => {});
    axios.get('/api/services/').then(res => setServices(res.data)).catch(() => {});
    axios.get('/api/board/categories/').then(res => setCategories(res.data)).catch(() => {});
    axios.get('/api/assets/types').then(res => setAssetTypes(res.data)).catch(() => {});

    const handleClickOutside = (e: MouseEvent) => {
      if (bulkActionsRef.current && !bulkActionsRef.current.contains(e.target as Node)) {
        setShowBulkActions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
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
      if (filters.business_critical) params.business_critical = filters.business_critical;

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

  const executeBulkAction = async () => {
    if (selectedAssets.length === 0 || !confirmModal.action) return;

    const isPromote = confirmModal.action === 'promote';
    const endpoint = isPromote ? "/api/assets/promote" : "/api/assets/raw/bulk-delete";

    try {
      await axios.post(endpoint, { raw_asset_ids: selectedAssets });
      toast.success(isPromote ? `Promoted ${selectedAssets.length} assets!` : `Deleted ${selectedAssets.length} assets.`);
      setSelectedAssets([]);
      fetchRawAssets();
    } catch (error) {
      toast.error(`Failed to ${isPromote ? 'promote' : 'delete'} assets`);
    } finally {
      setConfirmModal({ ...confirmModal, isOpen: false });
    }
  };

  const handleDownloadTemplate = () => {
    const csvContent = "Name,Description,Asset Type,Country,Service Lane,Category,Facing Internet,Confidentiality,Integrity,Availability\n" +
                       "Primary Banking API,Handles routing.,API,United States,,,TRUE,4,4,1\n" +
                       "Internal HR Portal,Employee management system.,Web Application/Website,GB,,,FALSE,3,2,1";
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

      const toastId = toast.loading("Processing import in background...");

      try {
        const formData = new FormData();
        formData.append('file', file);
        const res = await axios.post('/api/assets/raw/import', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

        toast.dismiss(toastId);

        if (res.data.failed && res.data.failed.length > 0) {
          toast.success(`Imported/Updated ${res.data.success} assets.`);
          toast.error(`Failed to import ${res.data.failed.length} assets (e.g. ${res.data.failed[0]}). Check system logs for details.`, { duration: 6000 });
        } else {
          toast.success(`Successfully imported/updated all ${res.data.success} assets!`);
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

  const getCriticalityPill = (score: number) => {
    if (score >= 8) return <span className="px-2 py-0.5 rounded-md font-bold bg-red-100 text-red-800 dark:bg-red-500/10 dark:text-red-400">Critical ({score})</span>;
    if (score >= 5) return <span className="px-2 py-0.5 rounded-md font-bold bg-amber-100 text-amber-800 dark:bg-amber-500/10 dark:text-amber-400">High ({score})</span>;
    return <span className="px-2 py-0.5 rounded-md font-bold bg-blue-100 text-blue-800 dark:bg-blue-500/10 dark:text-blue-400">Med/Low ({score || 0})</span>;
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 pb-12">
      <TopNav />
      <Toaster position="bottom-right" />

      <AddRawAssetModal isOpen={showAddModal} onClose={() => setShowAddModal(false)} onSuccess={fetchRawAssets} countries={countries} services={services} categories={categories} assetTypes={assetTypes} />

      <ConfirmModal
        isOpen={confirmModal.isOpen}
        title={confirmModal.title}
        message={confirmModal.message}
        onConfirm={executeBulkAction}
        onCancel={() => setConfirmModal({ ...confirmModal, isOpen: false })}
      />

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
              <div className="relative" ref={bulkActionsRef}>
                <button onClick={() => setShowBulkActions(!showBulkActions)} className="flex items-center gap-2 px-4 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors font-medium">
                  Actions ({selectedAssets.length}) <ChevronDown size={16}/>
                </button>
                {showBulkActions && (
                  <div className="absolute top-full right-0 mt-2 w-48 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl py-2 z-30 animate-in fade-in zoom-in-95">
                    <button onClick={() => { setShowBulkActions(false); setConfirmModal({isOpen: true, action: 'promote', title: "Promote Assets", message: `Are you sure you want to promote ${selectedAssets.length} assets to the Active Pool?`}); }} className="w-full text-left px-4 py-2 text-sm font-medium hover:bg-slate-50 dark:hover:bg-zinc-800 text-slate-700 dark:text-zinc-300">Promote Selected</button>
                    <div className="h-px bg-slate-100 dark:bg-zinc-800 my-1"></div>
                    <button onClick={() => { setShowBulkActions(false); setConfirmModal({isOpen: true, action: 'delete', title: "Delete Assets", message: `Are you sure you want to permanently delete ${selectedAssets.length} raw assets?`}); }} className="w-full text-left px-4 py-2 text-sm font-medium hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600 dark:text-red-400">Delete Selected</button>
                  </div>
                )}
              </div>
            )}
            <button onClick={handleDownloadTemplate} className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 rounded-lg hover:bg-slate-200 dark:hover:bg-zinc-700 transition-colors font-medium"><Download className="h-4 w-4" /> Template</button>
            <button onClick={handleImportExcel} className="flex items-center gap-2 px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 transition-colors font-medium"><Upload className="h-4 w-4" /> Import Data</button>
            <button onClick={() => setShowAddModal(true)} className="flex items-center gap-2 px-4 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors font-medium"><Plus className="h-4 w-4" /> Add Asset</button>
          </div>

          {/* Filter Popover */}
          {showFilters && (
            <div className="absolute top-full left-0 mt-2 w-full max-w-4xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl p-6 z-20 grid grid-cols-3 gap-6">
              <div className="space-y-4">
                <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Status</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.status} onChange={e => {setFilters({...filters, status: e.target.value}); setPage(1);}}><option value="">All</option><option value="raw">Raw Only</option><option value="pool">In Active Pool</option></select></div>
                <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Country</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.country} onChange={e => {setFilters({...filters, country: e.target.value}); setPage(1);}}><option value="">All Countries</option>{countries.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
                <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Asset Type</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.asset_type} onChange={e => {setFilters({...filters, asset_type: e.target.value}); setPage(1);}}><option value="">All Types</option>{assetTypes.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
              </div>

              <div className="space-y-4">
                <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Service Lane</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.service} onChange={e => {setFilters({...filters, service: e.target.value, category: ""}); setPage(1);}}><option value="">All Services</option>{services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
                <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Category</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 disabled:opacity-50" value={filters.category} onChange={e => {setFilters({...filters, category: e.target.value}); setPage(1);}} disabled={!filters.service}><option value="">All Categories</option>{filteredCategories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
              </div>

              <div className="space-y-4">
                <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Internet Facing</label><select className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.facing_internet} onChange={e => {setFilters({...filters, facing_internet: e.target.value}); setPage(1);}}><option value="">Any</option><option value="true">Yes</option><option value="false">No</option></select></div>
                <div><label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Min. Business Criticality (≥)</label><input type="number" min="0" max="9" placeholder="0-9" className="w-full p-2 border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800" value={filters.business_critical} onChange={e => {setFilters({...filters, business_critical: e.target.value}); setPage(1);}} /></div>
              </div>

              <div className="col-span-3 flex justify-end mt-2 pt-4 border-t border-slate-100 dark:border-zinc-800">
                <button onClick={() => {setFilters({country: "", service: "", category: "", status: "", asset_type: "", facing_internet: "", business_critical: ""}); setPage(1);}} className="text-sm text-blue-500 font-bold hover:text-blue-600">Clear All Filters</button>
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
                  <th className="p-4 font-semibold text-slate-500 uppercase">Criticality</th>
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
                        <Link to={`/raw/${asset.id}`} state={{ from: '/raw', label: 'Raw Assets' }} className="font-bold text-blue-600 dark:text-blue-400 hover:underline">{asset.name}</Link>
                        {asset.facing_internet && <Globe size={14} className="text-blue-500" title="Internet Facing" />}
                      </div>
                      <div className="text-xs text-slate-500 mt-1 flex gap-2 items-center">
                        <span className="font-medium text-slate-700 dark:text-zinc-300">{asset.asset_type_name || 'Unknown Type'}</span>
                        <span>•</span>
                        <span>{asset.id.substring(0, 8)}</span>
                      </div>
                    </td>
                    <td className="p-4"><span className="font-mono font-bold text-slate-500 dark:text-zinc-400">{asset.country_code || '--'}</span></td>
                    <td className="p-4 font-mono text-[10px]">
                      {getCriticalityPill(asset.business_critical)}
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