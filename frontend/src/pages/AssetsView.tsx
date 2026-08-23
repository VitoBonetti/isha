import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import TopNav from "../components/TopNav";
import ConfirmModal from "../components/Modals/ConfirmModal";
import toast, { Toaster } from "react-hot-toast";
import { Search, Filter, ArrowBigRightDash, Server, ChevronDown, Activity, Layers, ChevronsUpDown, ChevronUp, RefreshCw, Link2 } from "lucide-react";

interface PoolAsset {
  id: string;
  raw_asset_id: string;
  name: string;
  asset_type_name?: string;
  country?: string;
  service_name?: string;
  is_assigned: boolean;
  in_backlog: boolean;
  duplicate_allowed: boolean;
  completed_count: number;
  is_archived_this_year: boolean;
}

export default function AssetsView() {
  const [assets, setAssets] = useState<PoolAsset[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Filtering States
  const [searchTerm, setSearchTerm] = useState("");
  const [filterStatus, setFilterStatus] = useState<"all" | "assigned" | "ready_untested" | "ready_tested" | "archived">("all");
  const [filterService, setFilterService] = useState<string>("all");
  const [filterCountry, setFilterCountry] = useState<string>("all");
  const [targetYear, setTargetYear] = useState(new Date().getFullYear());

  const availableYears = Array.from(
    { length: 7 },
    (_, i) => new Date().getFullYear() - 1 + i
  );

  // Pagination & Sorting
  const [page, setPage] = useState(1);
  const ITEMS_PER_PAGE = 20;
  const [sortBy, setSortBy] = useState("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  // Reset pagination when any filter changes
  useEffect(() => {
    setPage(1);
  }, [searchTerm, filterStatus, filterService, filterCountry, sortBy, sortDir]);

  const handleSort = (column: string) => {
    if (sortBy === column) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortBy(column); setSortDir("asc"); }
  };

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return <ChevronsUpDown size={14} className="opacity-30" />;
    return sortDir === "asc" ? <ChevronUp size={14} className="text-emerald-500" /> : <ChevronDown size={14} className="text-emerald-500" />;
  };

  // Selection & Bulk Actions
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [showBulkActions, setShowBulkActions] = useState(false);
  const bulkActionsRef = useRef<HTMLDivElement>(null);

  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    action: 'generate' | 'remove' | 'combine' | null;
    targetId?: string;
    confirmText?: string;
    variant?: 'danger' | 'warning' | 'info' | 'secure';
  }>({
    isOpen: false, title: "", message: "", action: null
  });

  const [serviceModal, setServiceModal] = useState({ isOpen: false, selectedServiceId: "" });

  useEffect(() => {
    fetchPoolAssets();
    axios.get('/api/services/').then(res => setServices(res.data)).catch(console.error);

    const handleClickOutside = (e: MouseEvent) => {
      if (bulkActionsRef.current && !bulkActionsRef.current.contains(e.target as Node)) {
        setShowBulkActions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    fetchPoolAssets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetYear]);

  const fetchPoolAssets = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`/api/assets/?year=${targetYear}`);
      setAssets(res.data);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 403) {
        toast.error("You don't have permission to view the asset pool");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveFromPool = (assetId: string, assetName: string) => {
    setConfirmModal({
      isOpen: true,
      title: "Return to Raw Pool",
      message: `Are you sure you want to return "${assetName}" to the raw data pool?`,
      action: 'remove',
      targetId: assetId,
      confirmText: "Return to Pool",
      variant: "warning"
    });
  };

  const handleConfirmAction = async () => {
    if (!confirmModal.action) return;

    if (confirmModal.action === 'generate') {
      if (selectedAssets.length === 0) return;
      try {
        const toastId = toast.loading("Generating tests...");
        await axios.post("/api/tests/bulk", { asset_ids: selectedAssets });
        toast.dismiss(toastId);
        toast.success(`Generated tests for ${selectedAssets.length} assets! Check the Planner Backlog.`);
        setSelectedAssets([]);
        fetchPoolAssets();
      } catch (error) {
        toast.error("Failed to process bulk action");
      }
    } else if (confirmModal.action === 'remove' && confirmModal.targetId) {
      try {
        await axios.delete(`/api/assets/${confirmModal.targetId}?year=${targetYear}`);
        setAssets(prev => prev.filter(asset => asset.id !== confirmModal.targetId));
        setSelectedAssets(prev => prev.filter(id => id !== confirmModal.targetId));
        toast.success("Asset successfully processed.");
      } catch (error) {
        toast.error("Failed to remove asset");
      }
    } else if (confirmModal.action === 'combine') {
      if (selectedAssets.length === 0) return;

      // 1. Get all selected asset objects
      const selectedAssetObjects = assets.filter(a => selectedAssets.includes(a.id));

      // 2. Extract Service Lane info (Validation guarantees they are all the same)
      const serviceName = selectedAssetObjects[0].service_name;
      const serviceObj = services.find(s => s.name === serviceName);

      // 3. Construct the merged Test Name
      const testName = selectedAssetObjects.map(a => a.name).join(" & ");

      // 4. Build the payload for the existing single-test endpoint
      const payload = {
        name: testName,
        service_lane_id: serviceObj.id,
        credits_per_week: serviceObj.default_credits || 2.0,
        duration_weeks: serviceObj.default_duration_weeks || 1,
        asset_ids: selectedAssets
      };

      const toastId = toast.loading("Combining assets into a single test...");
      try {
        await axios.post("/api/tests/", payload);
        toast.dismiss(toastId);
        toast.success(`Successfully combined ${selectedAssets.length} assets into one test!`);
        setSelectedAssets([]);
        fetchPoolAssets();
      } catch (error) {
        toast.dismiss(toastId);
        toast.error("Failed to combine assets into a single test.");
      }
    }

    setConfirmModal({ ...confirmModal, isOpen: false });
  };

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

  const handleRestore = async (rawAssetId: string) => {
    try {
      await axios.put(`/api/assets/raw/${rawAssetId}/restore?year=${targetYear}`);
      toast.success(`Asset restored for ${targetYear}!`);
      fetchPoolAssets();
    } catch (error) {
      toast.error("Failed to restore asset");
    }
  };

  const toggleAssetSelection = (assetId: string) => {
    setSelectedAssets(prev => prev.includes(assetId) ? prev.filter(id => id !== assetId) : [...prev, assetId]);
  };

  // Extract unique countries dynamically from the assets data
  const uniqueCountries = Array.from(new Set(assets.map(a => a.country).filter(Boolean))).sort();

  // Advanced Filtering Logic
  const filteredAssets = assets.filter(asset => {
    // 1. Search Term
    const matchesSearch = !searchTerm ||
      asset.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (asset.country && asset.country.toLowerCase().includes(searchTerm.toLowerCase()));

    // 2. Service Lane & Country
    const matchesService = filterService === "all" ||
      (filterService === "none" ? !asset.service_name : asset.service_name === filterService);
    const matchesCountry = filterCountry === "all" || asset.country === filterCountry;

    // 3. Status Check
    const isAvailableForTest = !asset.is_assigned || asset.duplicate_allowed;
    let matchesStatus = true;
    if (filterStatus === "archived") {
      matchesStatus = asset.is_archived_this_year;
    } else {
      if (asset.is_archived_this_year) return false; // HIDE archived assets from other views

      const isAvailableForTest = !asset.is_assigned || asset.duplicate_allowed;
      if (filterStatus === "assigned") {
        matchesStatus = asset.is_assigned;
      } else if (filterStatus === "ready_untested") {
        matchesStatus = isAvailableForTest && asset.completed_count === 0;
      } else if (filterStatus === "ready_tested") {
        matchesStatus = isAvailableForTest && asset.completed_count > 0;
      }
    }
    return matchesSearch && matchesService && matchesCountry && matchesStatus;
  });

  const sortedAssets = [...filteredAssets].sort((a, b) => {
    let aVal = "";
    let bVal = "";
    if (sortBy === "name") { aVal = a.name; bVal = b.name; }
    else if (sortBy === "type") { aVal = a.asset_type_name || ""; bVal = b.asset_type_name || ""; }
    else if (sortBy === "country") { aVal = a.country || ""; bVal = b.country || ""; }
    else if (sortBy === "service") { aVal = a.service_name || ""; bVal = b.service_name || ""; }
    else if (sortBy === "status") {
      if (!a.is_assigned) aVal = "ready";
      else if (a.in_backlog) aVal = "backlog";
      else aVal = a.duplicate_allowed ? "active (multi)" : "active test";
      if (!b.is_assigned) bVal = "ready";
      else if (b.in_backlog) bVal = "backlog";
      else bVal = b.duplicate_allowed ? "active (multi)" : "active test";
    }

    if (aVal.toLowerCase() < bVal.toLowerCase()) return sortDir === "asc" ? -1 : 1;
    if (aVal.toLowerCase() > bVal.toLowerCase()) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  const totalPages = Math.ceil(sortedAssets.length / ITEMS_PER_PAGE);
  const paginatedAssets = sortedAssets.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

  const stats = {
    total: assets.length,
    assigned: assets.filter(a => a.is_assigned && !a.in_backlog).length,
    unassigned: assets.filter(a => !a.is_assigned || a.in_backlog || a.duplicate_allowed).length,
    completed: assets.filter(a => a.completed_count > 0).length
  };

  const validForSelection = filteredAssets.filter(a => !a.is_assigned || a.duplicate_allowed);

  const selectStyles = "px-3 py-2 w-full sm:w-auto rounded-lg border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm text-slate-700 dark:text-zinc-300 focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none cursor-pointer";

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100">
      <TopNav />
      <Toaster position="bottom-right" />

      <ConfirmModal
        isOpen={confirmModal.isOpen}
        title={confirmModal.title}
        message={confirmModal.message}
        confirmText={confirmModal.confirmText || "Confirm"}
        variant={confirmModal.variant || "danger"}
        onConfirm={handleConfirmAction}
        onCancel={() => setConfirmModal({ ...confirmModal, isOpen: false })}
      />

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
      <div className="pt-28 md:pt-32 pb-8 px-4 md:px-6 max-w-7xl mx-auto">
        <h1 className="text-2xl font-extrabold flex items-center gap-2">
          <Server size={28} className="text-emerald-500" />
          Active Asset Pool
        </h1>
        <p className="text-slate-500 dark:text-zinc-400 mb-6 md:mb-8 text-sm md:text-base">
          Select unassigned (or multi-test) assets to generate tests for the Planner Backlog.
        </p>

        {/* Stats Cards - Responsive Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6 mb-6 md:mb-8">
          <div className="bg-white dark:bg-zinc-900 p-4 md:p-6 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm flex flex-col justify-between">
            <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mb-1">Total Assets</p>
            <p className="text-2xl md:text-3xl font-bold text-emerald-600">{stats.total}</p>
          </div>
          <div className="bg-white dark:bg-zinc-900 p-4 md:p-6 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm flex flex-col justify-between">
            <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mb-1">Actively Testing</p>
            <p className="text-2xl md:text-3xl font-bold text-blue-600">{stats.assigned}</p>
          </div>
          <div className="bg-white dark:bg-zinc-900 p-4 md:p-6 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm flex flex-col justify-between">
            <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mb-1 leading-tight">Ready for Generation</p>
            <p className="text-2xl md:text-3xl font-bold text-amber-600 mt-1 md:mt-0">{stats.unassigned}</p>
          </div>
          <div className="bg-white dark:bg-zinc-900 p-4 md:p-6 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm flex flex-col justify-between">
            <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mb-1 leading-tight">Successfully Tested</p>
            <p className="text-2xl md:text-3xl font-bold text-emerald-600 mt-1 md:mt-0">{stats.completed}</p>
          </div>
        </div>

        {/* Actions Bar with Dropdown Filters - Fully Stackable */}
        <div className="flex flex-col xl:flex-row gap-4 xl:items-center justify-between bg-white dark:bg-zinc-900 p-4 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm">

          <div className="flex flex-col md:flex-row flex-wrap items-stretch md:items-center gap-3 flex-1 w-full xl:w-auto">
            {/* Search Input */}
            <div className="relative w-full md:max-w-xs md:min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search assets..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 md:py-2 rounded-lg border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none text-sm"
              />
            </div>

            {/* Filter Dropdowns Grid on Mobile */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 w-full md:w-auto items-center">
              <select
                value={targetYear}
                onChange={(e) => setTargetYear(parseInt(e.target.value))}
                className={selectStyles}
              >
                {availableYears.map(y => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value as any)}
                className={selectStyles}
              >
                <option value="all">All Statuses</option>
                <option value="assigned">Active Tests Only</option>
                <option value="ready_untested">Ready (Never Tested)</option>
                <option value="ready_tested">Ready (Previously Tested)</option>
                <option value="archived">Archived</option>
              </select>

              <select
                value={filterService}
                onChange={(e) => setFilterService(e.target.value)}
                className={selectStyles}
              >
                <option value="all">All Service Lanes</option>
                <option value="none">No Service Lane</option>
                {services.map(s => <option key={s.id} value={s.name}>{s.name}</option>)}
              </select>

              <select
                value={filterCountry}
                onChange={(e) => setFilterCountry(e.target.value)}
                className={selectStyles}
              >
                <option value="all">All Countries</option>
                {uniqueCountries.map(c => <option key={c as string} value={c as string}>{c as string}</option>)}
              </select>
            </div>
          </div>

          <div className="flex flex-row-reverse md:flex-row items-center justify-between md:justify-end gap-3 w-full xl:w-auto border-t border-slate-100 dark:border-zinc-800 pt-3 xl:border-0 xl:pt-0">
             <span className="text-sm font-medium text-slate-500 dark:text-zinc-400 order-1 md:order-2">
              {filteredAssets.length} results
            </span>
            {selectedAssets.length > 0 && (
              <div className="relative w-full md:w-auto order-2 md:order-1" ref={bulkActionsRef}>
                <button onClick={() => setShowBulkActions(!showBulkActions)} className="w-full md:w-auto flex justify-center items-center gap-2 px-4 py-2.5 md:py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium">
                  Actions ({selectedAssets.length}) <ChevronDown size={16}/>
                </button>
                {showBulkActions && (
                  <div className="absolute top-full left-0 md:left-auto md:right-0 mt-2 w-full md:w-56 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl py-2 z-30 animate-in fade-in zoom-in-95 overflow-hidden">
                    <button
                      onClick={() => {
                        setShowBulkActions(false);
                        const missingLanes = selectedAssets.filter(id => !assets.find(a => a.id === id)?.service_name);
                        if (missingLanes.length > 0) {
                          toast.error(`${missingLanes.length} selected assets are missing a Service Lane! Please assign one first.`);
                          return;
                        }
                        setConfirmModal({
                          isOpen: true,
                          action: 'generate',
                          title: "Generate Tests",
                          message: `Are you sure you want to generate Planner Tests for these ${selectedAssets.length} assets? This will move them to the Planner Backlog.`,
                          confirmText: "Generate",
                          variant: "info"
                        });
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
                    <div className="h-px bg-slate-100 dark:bg-zinc-800 my-0.5"></div>
                    <button
                      onClick={() => {
                        setShowBulkActions(false);
                        const selectedAssetObjects = assets.filter(a => selectedAssets.includes(a.id));

                        // Check 1: Missing Service Lanes
                        const missingLanes = selectedAssetObjects.filter(a => !a.service_name);
                        if (missingLanes.length > 0) {
                          toast.error(`${missingLanes.length} selected assets are missing a Service Lane!`);
                          return;
                        }

                        // Check 2: Mixed Service Lanes
                        const serviceNames = new Set(selectedAssetObjects.map(a => a.service_name));
                        if (serviceNames.size > 1) {
                          toast.error("All selected assets must belong to the SAME Service Lane to be combined.");
                          return;
                        }

                        // Validation passed: calculate the merged name for the prompt
                        const testName = selectedAssetObjects.map(a => a.name).join(" & ");

                        setConfirmModal({
                          isOpen: true,
                          action: 'combine',
                          title: "Combine into Single Test",
                          message: `Are you sure you want to combine these ${selectedAssets.length} assets into a single test named "${testName}"?`,
                          confirmText: "Combine Assets",
                          variant: "info"
                        });
                      }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-bold hover:bg-slate-50 dark:hover:bg-zinc-800 text-slate-700 dark:text-zinc-300 transition-colors"
                    >
                      <Link2 size={16} className="text-emerald-500" /> Combine into Single Test
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Assets List Container */}
        <div className="mt-6 md:mt-8 bg-white dark:bg-zinc-900 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden w-full">
          {loading ? (
            <div className="p-12 text-center">
              <div className="animate-spin h-8 w-8 border-4 border-emerald-500 border-t-transparent rounded-full mx-auto"></div>
              <p className="mt-4 text-slate-500 text-sm">Loading pool assets...</p>
            </div>
          ) : (
            <>
              {/* DESKTOP VIEW: Standard Table (Hidden on Mobile) */}
              <table className="hidden md:table w-full">
                <thead className="bg-slate-50 dark:bg-zinc-800/50 border-b border-slate-200 dark:border-zinc-700">
                  <tr>
                    <th className="p-4 w-12 text-center">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded text-blue-600 border-slate-300 disabled:opacity-50"
                        onChange={(e) => {
                          if(e.target.checked) setSelectedAssets(validForSelection.map(a => a.id));
                          else setSelectedAssets([]);
                        }}
                        checked={selectedAssets.length === validForSelection.length && validForSelection.length > 0}
                        disabled={validForSelection.length === 0}
                      />
                    </th>
                    <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"  onClick={() => handleSort("name")}>
                      <div className="flex items-center gap-2">Asset Name <SortIcon column="name"/></div>
                    </th>
                    <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"  onClick={() => handleSort("type")}>
                      <div className="flex items-center gap-2">Type <SortIcon column="type"/></div>
                    </th>
                    <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"  onClick={() => handleSort("country")}>
                      <div className="flex items-center gap-2">Country <SortIcon column="country"/></div>
                    </th>
                    <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"  onClick={() => handleSort("service")}>
                      <div className="flex items-center gap-2">Service Lane <SortIcon column="service"/></div>
                    </th>
                    <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"  onClick={() => handleSort("status")}>
                      <div className="flex items-center gap-2">Status <SortIcon column="status"/></div>
                    </th>
                    <th className="px-6 py-4 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-zinc-700">
                  {paginatedAssets.map((asset) => {
                    const isSelected = selectedAssets.includes(asset.id);
                    return (
                      <tr key={asset.id} className={`hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors ${isSelected ? 'bg-blue-50 dark:bg-blue-900/10' : ''}`}>
                        <td className="p-4 text-center">
                          <input
                            type="checkbox"
                            disabled={(asset.is_assigned && !asset.duplicate_allowed)}
                            checked={isSelected}
                            onChange={() => toggleAssetSelection(asset.id)}
                            className="h-4 w-4 text-blue-600 rounded border-slate-300 disabled:opacity-40"
                          />
                        </td>
                        <td className="px-6 py-4 max-w-[200px]">
                          <div>
                            <Link
                              to={`/raw/${asset.raw_asset_id}`}
                              state={{ from: '/assets', label: 'Active Pool' }}
                              className="text-sm font-bold text-blue-600 dark:text-blue-400 hover:underline truncate block"
                            >
                              {asset.name}
                            </Link>
                            <div className="text-xs text-slate-500 dark:text-zinc-400 mt-1">Pool ID: {asset.id.substring(0, 8)}...</div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-sm font-medium text-slate-700 dark:text-zinc-300 whitespace-nowrap">{asset.asset_type_name || 'Unknown'}</div>
                        </td>
                        <td className="px-6 py-4">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-50 dark:bg-indigo-900/30 text-indigo-800 dark:text-indigo-400">
                            {asset.country || 'N/A'}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          {asset.service_name ? (
                            <div className="text-sm font-medium whitespace-nowrap">{asset.service_name}</div>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800 dark:bg-red-500/10 dark:text-red-400 border border-red-200 dark:border-red-500/20 whitespace-nowrap">
                              MISSING SERVICE LANE
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex flex-col gap-1.5 items-start">
                            {asset.is_assigned ? (
                              asset.in_backlog ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-200 w-fit">
                                  Backlog
                                </span>
                              ) : asset.duplicate_allowed ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-200 w-fit">
                                  <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse"></div> Multi
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 w-fit">
                                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></div> Active
                                </span>
                              )
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-200 shadow-sm border border-emerald-200 dark:border-emerald-800">
                                Ready
                              </span>
                            )}

                            {asset.completed_count > 0 && (
                              <span className="text-[10px] font-bold text-slate-500 dark:text-zinc-400 bg-slate-100 dark:bg-zinc-800 px-2 py-0.5 rounded-md">
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
                                <Activity className="h-3.5 w-3.5" />
                              </button>
                            )}
                            {asset.is_archived_this_year ? (
                              <button
                                onClick={() => handleRestore(asset.raw_asset_id)}
                                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-emerald-200 text-emerald-600 hover:bg-emerald-50 dark:border-emerald-900/50 dark:text-emerald-400 dark:hover:bg-emerald-900/30 transition-colors text-sm font-bold shadow-sm"
                              >
                                <RefreshCw className="h-3.5 w-3.5" /> Restore
                              </button>
                            ) : (
                              <>
                                <button
                                  onClick={() => handleRemoveFromPool(asset.id, asset.name)}
                                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-500 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors text-sm"
                                  title="Return to Raw Pool"
                                >
                                  <ArrowBigRightDash className="h-3.5 w-3.5" />
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {/* MOBILE VIEW: Stacked Cards (Hidden on Desktop) */}
              <div className="flex md:hidden flex-col divide-y divide-slate-100 dark:divide-zinc-800 w-full">
                {paginatedAssets.map((asset) => {
                  const isSelected = selectedAssets.includes(asset.id);
                  const isReadyToTest = (!asset.is_assigned || asset.duplicate_allowed) && asset.service_name;

                  return (
                    <div key={asset.id} className={`p-4 flex flex-col gap-3 transition-colors ${isSelected ? 'bg-blue-50 dark:bg-blue-900/10' : ''}`}>

                      {/* Top Row: Checkbox & Title Block */}
                      <div className="flex items-start gap-3 w-full">
                        <input
                          type="checkbox"
                          disabled={(asset.is_assigned && !asset.duplicate_allowed)}
                          checked={isSelected}
                          onChange={() => toggleAssetSelection(asset.id)}
                          className="mt-1 h-4 w-4 text-blue-600 rounded border-slate-300 disabled:opacity-40 flex-shrink-0"
                        />
                        <div className="flex flex-col flex-1 min-w-0">
                          <Link
                            to={`/raw/${asset.raw_asset_id}`}
                            state={{ from: '/assets', label: 'Active Pool' }}
                            className="text-sm font-bold text-blue-600 dark:text-blue-400 hover:underline break-words"
                          >
                            {asset.name}
                          </Link>
                          <div className="text-[11px] text-slate-500 dark:text-zinc-400 mt-1 flex flex-wrap gap-1 items-center">
                            <span className="font-medium text-slate-700 dark:text-zinc-300">{asset.asset_type_name || 'Unknown Type'}</span>
                            <span>•</span>
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-indigo-50 dark:bg-indigo-900/30 text-indigo-800 dark:text-indigo-400 uppercase tracking-wider">
                              {asset.country || 'N/A'}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Middle Row: Service Lane & Status Grid */}
                      <div className="grid grid-cols-2 gap-2 pl-7 mt-1">
                        <div className="flex flex-col gap-1">
                          <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Service Lane</span>
                          {asset.service_name ? (
                            <span className="text-xs font-medium text-slate-700 dark:text-zinc-300 truncate">{asset.service_name}</span>
                          ) : (
                            <span className="inline-flex w-fit items-center px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-100 text-red-800 dark:bg-red-500/10 dark:text-red-400 border border-red-200 dark:border-red-500/20">
                              MISSING LANE
                            </span>
                          )}
                        </div>
                        <div className="flex flex-col gap-1 items-end">
                          <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Status</span>
                          <div className="flex flex-col items-end gap-1 w-full">
                            {asset.is_assigned ? (
                              asset.duplicate_allowed ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-200 w-fit">
                                  <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse"></div> Multi
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 w-fit">
                                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></div> Active
                                </span>
                              )
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-800 w-fit">
                                Ready
                              </span>
                            )}
                            {asset.completed_count > 0 && (
                              <span className="text-[9px] font-bold text-slate-500 dark:text-zinc-400 bg-slate-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded w-fit">
                                Tested: {asset.completed_count}x
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Bottom Row: Actions */}
                      <div className="flex justify-end gap-2 pt-3 border-t border-slate-100 dark:border-zinc-800 mt-2 pl-7">
                        {asset.is_archived_this_year ? (
                          <button
                            onClick={() => handleRestore(asset.raw_asset_id)}
                            className="flex-1 justify-center inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-emerald-200 text-emerald-600 hover:bg-emerald-50 dark:border-emerald-900/50 dark:text-emerald-400 dark:hover:bg-emerald-900/30 transition-colors text-xs font-bold shadow-sm"
                          >
                            <RefreshCw className="h-3.5 w-3.5" /> Restore
                          </button>
                        ) : (
                          <>
                            <button
                              onClick={() => handleRemoveFromPool(asset.id, asset.name)}
                              className="flex-1 justify-center inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-600 hover:text-red-600 dark:text-zinc-400 dark:hover:text-red-400 bg-slate-50 dark:bg-zinc-800/50 transition-colors text-xs font-bold"
                            >
                              <ArrowBigRightDash className="h-3.5 w-3.5" /> Return
                            </button>
                            <button
                              onClick={() => isReadyToTest && handleGenerateSingleTest(asset.id)}
                              disabled={!isReadyToTest}
                              className={`flex-1 justify-center inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs font-bold transition-colors ${
                                isReadyToTest
                                  ? 'border-blue-200 dark:border-blue-900/50 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20'
                                  : 'border-slate-200 dark:border-zinc-800 text-slate-400 bg-slate-100 dark:bg-zinc-900 opacity-50 cursor-not-allowed'
                              }`}
                            >
                              <Activity className="h-3.5 w-3.5" /> Generate
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Empty States & Pagination */}
              {sortedAssets.length === 0 && !loading && (
                <div className="p-12 text-center">
                  <p className="text-slate-500 mb-2 font-medium">No assets found</p>
                  <p className="text-sm text-slate-400">{searchTerm ? "Try adjusting your search or filters" : "No assets in the pool yet"}</p>
                </div>
              )}
              {sortedAssets.length > 0 && !loading && (
                <div className="px-4 md:px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex flex-col sm:flex-row justify-between items-center gap-4 sm:gap-0 bg-slate-50 dark:bg-zinc-950/50">
                  <span className="text-xs md:text-sm text-slate-500">Page {page} of {totalPages || 1}</span>
                  <div className="flex gap-2 w-full sm:w-auto">
                    <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white dark:bg-zinc-900">Prev</button>
                    <button onClick={() => setPage(p => p + 1)} disabled={page >= totalPages} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium transition-colors bg-white dark:bg-zinc-900">Next</button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}