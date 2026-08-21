import { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import TopNav from "../components/TopNav";
import ConfirmModal from "../components/Modals/ConfirmModal";
import toast, { Toaster } from "react-hot-toast";
import { ChevronLeft, Save, Trash2, ShieldAlert, FileText, Edit2, X, History, ChevronDown, ChevronRight, Clock, CheckCircle, HelpCircle, Database, RefreshCw, Shield, Code, MapPin, Server, ExternalLink } from "lucide-react";
import { useAppContext } from "../context/AppContext";

export default function AssetDetailView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { currentUser } = useAppContext();
  const isAdmin = currentUser?.role === 'admin';
  const backPath = location.state?.from || "/raw";
  const backLabel = location.state?.label || "Raw Assets";

  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);

  // Accordion States
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isCompletedTestsOpen, setIsCompletedTestsOpen] = useState(false);
  const [isSnowDataOpen, setIsSnowDataOpen] = useState(false);
  const [isCountryContactsOpen, setIsCountryContactsOpen] = useState(false);
  const [isAssetContactsOpen, setIsAssetContactsOpen] = useState(false);

  // Data States
  const [countries, setCountries] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [assetTypes, setAssetTypes] = useState<any[]>([]);
  const [asset, setAsset] = useState<any>(null);
  const [originalAsset, setOriginalAsset] = useState<any>(null);

  // Contact States
  const [assetContacts, setAssetContacts] = useState<any[]>([]);
  const [countryContacts, setCountryContacts] = useState<any[]>([]);

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  const currentYear = new Date().getFullYear();

  // 1. Initial Load
  useEffect(() => {
    Promise.all([
      axios.get(`/api/assets/raw/${id}`),
      axios.get('/api/countries/'),
      axios.get('/api/services/'),
      axios.get('/api/board/categories/'),
      axios.get('/api/assets/types'),
      axios.get(`/api/contacts/raw-asset/${id}`).catch(() => ({ data: [] }))
    ]).then(([resAsset, resC, resS, resCat, resTypes, resAssetContacts]) => {
      setAssetTypes(resTypes.data);
      setAsset(resAsset.data);
      setOriginalAsset(resAsset.data);
      setCountries(resC.data);
      setServices(resS.data);
      setCategories(resCat.data);
      setAssetContacts(resAssetContacts.data);
    }).catch(() => {
      toast.error("Failed to load asset");
      navigate("/raw");
    }).finally(() => setLoading(false));
  }, [id, navigate]);

  // 2. Dynamically fetch Country Contacts whenever the asset's country changes
  useEffect(() => {
    if (asset?.country_id) {
      axios.get(`/api/contacts/country/${asset.country_id}`)
        .then(res => setCountryContacts(res.data))
        .catch(() => setCountryContacts([]));
    } else {
      setCountryContacts([]);
    }
  }, [asset?.country_id]);

  if (loading || !asset) return <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 flex items-center justify-center">Loading...</div>;

  const businessCritical = Math.min(9, (asset.confidentiality_rating || 0) + (asset.integrity_rating || 0) + (asset.availability_rating || 0));

  const filteredCategories = categories
    .filter(c => c.service_lane_id === asset.service_forecast_id && (c.goal_year === currentYear || c.goal_year === currentYear + 1))
    .sort((a, b) => (a.goal_year || 0) - (b.goal_year || 0));

  const isSynced = !!asset.snow_number;
  const maxArchivedYear = asset?.archived_years?.length > 0 ? Math.max(...asset.archived_years) : 0;
  const isArchivedThisYear = asset?.archived_years?.includes(currentYear) || (asset?.is_archived && currentYear > maxArchivedYear);

  const handleRestore = async () => {
    try {
      await axios.put(`/api/assets/raw/${id}/restore?year=${currentYear}`);
      toast.success("Asset restored successfully!");
      const resAsset = await axios.get(`/api/assets/raw/${id}`);
      setAsset(resAsset.data);
      setOriginalAsset(resAsset.data);
      setIsEditing(false);
    } catch (error) {
      toast.error("Failed to restore asset");
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        ...asset,
        facing_internet: !!asset.facing_internet,
        duplicate_allowed: !!asset.duplicate_allowed,
        business_critical: businessCritical,
        country_id: asset.country_id === "" ? null : asset.country_id,
        service_forecast_id: asset.service_forecast_id === "" ? null : asset.service_forecast_id,
        category_id: asset.category_id === "" ? null : asset.category_id,
        snow_number: asset.snow_number || null,
        team_note: asset.team_note || null,
        kiss24_asset_id: asset.kiss24_asset_id || null
      };
      await axios.put(`/api/assets/raw/${id}`, payload);
      const resAsset = await axios.get(`/api/assets/raw/${id}`);
      setAsset(resAsset.data);
      setOriginalAsset(resAsset.data);
      setIsEditing(false);
      toast.success("Asset updated successfully");
    } catch (error) {
      toast.error("Failed to update asset");
    }
  };

  const handleDelete = async () => {
    try {
      const res = await axios.delete(`/api/assets/raw/${id}?year=${currentYear}`);
      toast.success(res.data.message || "Asset processed successfully");
      setDeleteModalOpen(false);

      if (res.data.message && res.data.message.toLowerCase().includes("archived")) {
        const resAsset = await axios.get(`/api/assets/raw/${id}`);
        setAsset(resAsset.data);
        setOriginalAsset(resAsset.data);
        setIsEditing(false);
      } else {
        navigate("/raw");
      }
    } catch (error) {
      toast.error("Failed to process asset");
    }
  };

  const handleCancel = () => {
    setAsset(originalAsset);
    setIsEditing(false);
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
  };

  const inputClasses = isEditing
    ? "w-full mt-1 p-2.5 border border-slate-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-emerald-500 outline-none transition-all"
    : "w-full mt-1 p-2.5 border border-transparent rounded-lg bg-slate-50 dark:bg-zinc-950/50 text-slate-900 dark:text-zinc-100 outline-none cursor-default font-medium appearance-none";

  const ratingClasses = isEditing
    ? "w-full mt-1 p-2 border border-slate-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-sm text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-emerald-500 outline-none transition-all"
    : "w-full mt-1 p-2 border border-transparent rounded-lg bg-slate-100 dark:bg-zinc-900 text-sm text-slate-900 dark:text-zinc-100 outline-none cursor-default font-bold";

  const SyncLabel = ({ label }: { label: string }) => (
    <div className="flex items-center gap-1.5 mb-1">
      <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">{label}</label>
      {isSynced && (
        <div className="group relative flex items-center">
          <HelpCircle size={14} className="text-blue-500 cursor-help" />
          <div className="absolute bottom-full mb-2 left-0 md:left-1/2 md:-translate-x-1/2 w-48 p-2 bg-slate-800 text-white text-xs rounded shadow-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-10 text-center">
            This field is managed by ServiceNow. Manual changes will be overwritten on the next sync.
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100">
      <TopNav />
      <Toaster position="bottom-right" />
      <ConfirmModal
        isOpen={deleteModalOpen}
        title="Delete / Archive Asset"
        message="Are you sure you want to remove this asset? If it has completed tests, it will be safely archived to preserve history. Otherwise, it will be permanently deleted."
        onConfirm={handleDelete}
        onCancel={() => setDeleteModalOpen(false)}
      />

      <div className="pt-28 md:pt-32 pb-12 px-4 md:px-6 w-full max-w-[1600px] mx-auto overflow-hidden">

        {/* Top Toolbar */}
        <div className="flex justify-between items-center mb-4 md:mb-6">
          <button onClick={() => navigate(backPath)} className="flex items-center gap-1 md:gap-2 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white transition-colors font-medium">
            <ChevronLeft size={16} /> <span className="hidden sm:inline">Back to</span> {backLabel}
          </button>

          {!isEditing && (
            <button onClick={() => setIsEditing(true)} className="flex items-center gap-2 px-3 py-1.5 md:px-4 md:py-2 bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-800 dark:text-zinc-200 rounded-lg text-sm font-bold transition-colors shadow-sm">
              <Edit2 size={16} /> <span className="hidden sm:inline">Edit Asset</span><span className="sm:hidden">Edit</span>
            </button>
          )}
        </div>

        {/* TWO-COLUMN WIDE LAYOUT */}
        <div className="flex flex-col lg:flex-row gap-6 md:gap-8 items-start w-full">

          {/* LEFT COLUMN: Editable Form (2/3 width) */}
          <div className="w-full lg:w-2/3 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 md:p-8 shadow-sm">

            {/* Header Section */}
            <div className="flex flex-col md:flex-row justify-between items-start gap-4 md:gap-0 mb-6 md:mb-8 border-b border-slate-100 dark:border-zinc-800 pb-6">
              <div>
                <div className="flex items-center gap-2 mt-2 xl:mt-0">
                  <h1 className="text-xl md:text-2xl font-bold flex items-start md:items-center gap-2">
                    <FileText className="text-emerald-500 flex-shrink-0 mt-1 md:mt-0" />
                    <span className="break-words">{asset.name}</span>
                  </h1>
                  { isAdmin && asset.kiss24_asset_id && (
                    <a href={`https://randstad.eu.vulnmanager.com/assets/${asset.kiss24_asset_id}/show`} target="_blank" rel="noopener noreferrer" className="ml-2 text-blue-500 hover:text-blue-600 transition-colors bg-blue-50 dark:bg-blue-900/30 p-1.5 rounded-lg border border-blue-200 dark:border-blue-900/50">
                      <ExternalLink size={16} title="Keep Secure 24 link" />
                    </a>
                  )}
                </div>
                <div className="text-slate-500 text-xs md:text-sm mt-2 flex flex-col gap-1.5">
                  <span className="font-mono break-all">ID: {asset.id}</span>
                  <span className="flex items-center gap-1.5"><Clock size={14}/> Created: {formatDate(asset.create_date)}</span>
                  {asset.update_date && <span className="flex items-center gap-1.5"><Edit2 size={14}/> Updated: {formatDate(asset.update_date)}</span>}
                </div>
              </div>

              {/* Status Badges */}
              <div className="flex flex-row md:flex-col flex-wrap items-start md:items-end gap-2 w-full md:w-auto">
                {isArchivedThisYear ? (
                  <span className="px-3 py-1 bg-slate-100 dark:bg-zinc-800 text-slate-500 dark:text-zinc-400 font-bold text-xs rounded-full uppercase tracking-wider border border-slate-200 dark:border-zinc-700 flex items-center gap-1.5">
                    <RefreshCw size={12} /> Archived
                  </span>
                ) : asset.is_promoted ? (
                  <span className="px-3 py-1 bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-400 font-bold text-xs rounded-full uppercase tracking-wider">In Active Pool</span>
                ) : (
                  <span className="px-3 py-1 bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 font-bold text-xs rounded-full uppercase tracking-wider">Raw Status</span>
                )}
                {isSynced && (
                  <span className="flex items-center gap-1 px-3 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 font-bold text-xs rounded-full uppercase tracking-wider border border-blue-200 dark:border-blue-800/30 shadow-sm md:mt-1">
                    <Database size={12} /> SNOW Synced
                  </span>
                )}
              </div>
            </div>

            <form onSubmit={handleUpdate} className="space-y-6 md:space-y-8">
              {/* --- CORRECTED FORM GRID --- */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-6">
                <div>
                  <SyncLabel label="Asset Name" />
                  <input required disabled={!isEditing} className={inputClasses} value={asset.name} onChange={e => setAsset({...asset, name: e.target.value})} />
                </div>
                <div>
                  <div className="flex items-center gap-1.5 mb-1">
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">ServiceNow ID</label>
                  </div>
                  <input disabled={!isEditing || isSynced} className={`${inputClasses} ${isSynced ? 'cursor-not-allowed opacity-70' : ''}`} placeholder="e.g. APM00123" value={asset.snow_number || ""} onChange={e => setAsset({...asset, snow_number: e.target.value})} />
                </div>

                <div>
                  <SyncLabel label="Asset Type" />
                  <select required disabled={!isEditing} className={inputClasses} value={asset.asset_type_id} onChange={e => setAsset({...asset, asset_type_id: e.target.value})}>
                    {assetTypes.map(at => <option key={at.id} value={at.id}>{at.name}</option>)}
                  </select>
                </div>
                <div>
                  <SyncLabel label="Country Mapping" />
                  <select disabled={!isEditing} className={inputClasses} value={asset.country_id || ""} onChange={e => setAsset({...asset, country_id: e.target.value})}>
                    <option value="">-- None --</option>
                    {countries.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>

                <div className="sm:col-span-2">
                  <SyncLabel label="Description" />
                  <textarea disabled={!isEditing} className={`${inputClasses} resize-none ${isEditing ? 'h-32' : 'h-auto min-h-[100px]'}`} value={asset.description || ""} onChange={e => setAsset({...asset, description: e.target.value})} />
                </div>

                <div className="sm:col-span-2">
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 mb-1 flex items-center gap-2 flex-wrap">
                    Team Notes <span className="text-[10px] md:text-xs font-normal text-slate-400 bg-slate-100 dark:bg-zinc-800 px-2 py-0.5 rounded-full">(Never overwritten by Sync)</span>
                  </label>
                  <textarea disabled={!isEditing} placeholder="Add internal pentesting notes or context here..." className={`${inputClasses} resize-none ${isEditing ? 'h-32' : 'h-auto min-h-[100px]'}`} value={asset.team_note || ""} onChange={e => setAsset({...asset, team_note: e.target.value})} />
                </div>

                {/* Kiss24, Internet, and Duplicate layout perfectly aligned */}
                <div className="sm:col-span-2 flex flex-col sm:flex-row gap-4 md:gap-6">
                  <div className="w-full sm:w-auto shrink-0">
                    <SyncLabel label="Facing Internet" />
                    <label className={`flex items-center w-full gap-3 p-3 rounded-lg transition-colors ${isEditing ? 'bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50' : 'bg-transparent'}`}>
                      <input type="checkbox" disabled={!isEditing} className="h-4 w-4 rounded text-emerald-500 border-slate-300 disabled:opacity-70" checked={asset.facing_internet} onChange={e => setAsset({...asset, facing_internet: e.target.checked})} />
                      <span className="text-sm font-bold text-slate-700 dark:text-zinc-300 pr-2">Yes</span>
                    </label>
                  </div>
                  <div className="w-full sm:w-auto shrink-0">
                    <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 block mb-1">Allow Duplicates</label>
                    <label className={`flex items-center w-full gap-3 p-3 rounded-lg transition-colors ${isEditing ? 'bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50' : 'bg-transparent '}`}>
                      <input type="checkbox" disabled={!isEditing} className="h-4 w-4 rounded text-blue-500 border-slate-300 disabled:opacity-70" checked={asset.duplicate_allowed || false} onChange={e => setAsset({...asset, duplicate_allowed: e.target.checked})} />
                      <span className="text-sm font-bold text-slate-700 dark:text-zinc-300 pr-2">Yes</span>
                    </label>
                  </div>
                  <div className="w-full sm:flex-1 min-w-[200px]">
                    <div className="flex items-center gap-1.5 mb-1">
                      <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Kiss24 UUID</label>
                    </div>
                    <input disabled={!isEditing} className={inputClasses} placeholder="123a45bc-6d7e-..." value={asset.kiss24_asset_id || ""} onChange={e => setAsset({...asset, kiss24_asset_id: e.target.value})} />
                  </div>
                </div>
              </div>

              <div className={`p-4 md:p-6 rounded-xl border ${isEditing ? 'bg-slate-50 dark:bg-zinc-950/50 border-slate-200 dark:border-zinc-800' : 'border-slate-100 dark:border-zinc-800/50'}`}>
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-4 flex items-center gap-2"><ShieldAlert size={16}/> Risk Ratings</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
                  <div>
                    <label className="text-[11px] md:text-xs font-bold text-slate-700 dark:text-zinc-300">Bus. Critical</label>
                    <input type="number" disabled className={`${ratingClasses} !bg-slate-200 dark:!bg-zinc-800 text-slate-500 font-bold cursor-not-allowed`} value={businessCritical} readOnly />
                  </div>
                  <div>
                    <SyncLabel label="Confidentiality" />
                    <input type="number" disabled={!isEditing} min="0" max="5" className={ratingClasses} value={asset.confidentiality_rating || 0} onChange={e => setAsset({...asset, confidentiality_rating: parseInt(e.target.value) || 0})} />
                  </div>
                  <div>
                    <SyncLabel label="Integrity" />
                    <input type="number" disabled={!isEditing} min="0" max="5" className={ratingClasses} value={asset.integrity_rating || 0} onChange={e => setAsset({...asset, integrity_rating: parseInt(e.target.value) || 0})} />
                  </div>
                  <div>
                    <SyncLabel label="Availability" />
                    <input type="number" disabled={!isEditing} min="0" max="5" className={ratingClasses} value={asset.availability_rating || 0} onChange={e => setAsset({...asset, availability_rating: parseInt(e.target.value) || 0})} />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-6">
                <div>
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Service Forecast</label>
                  <select disabled={!isEditing} className={inputClasses} value={asset.service_forecast_id || ""} onChange={e => setAsset({...asset, service_forecast_id: e.target.value, category_id: ""})}>
                    <option value="">-- None --</option>
                    {services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Forecast Category</label>
                  <select disabled={!isEditing || !asset.service_forecast_id} className={inputClasses} value={asset.category_id || ""} onChange={e => setAsset({...asset, category_id: e.target.value})}>
                    <option value="">-- None --</option>
                    {filteredCategories.map(c => (
                      <option key={c.id} value={c.id}>{c.name} - {c.goal_year || 'Not Set'}</option>
                    ))}
                  </select>
                </div>
              </div>

              {isEditing && (
                <div className="flex flex-col md:flex-row justify-between items-center gap-4 pt-6 md:pt-8 border-t border-slate-100 dark:border-zinc-800 animate-in fade-in slide-in-from-bottom-2">
                  {isArchivedThisYear ? (
                    <button type="button" onClick={handleRestore} className="w-full md:w-auto flex justify-center items-center gap-2 px-4 py-2.5 text-sm font-bold text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 rounded-lg transition-colors order-2 md:order-1">
                      <RefreshCw size={16} /> Restore Asset
                    </button>
                  ) : (
                    <button type="button" onClick={() => setDeleteModalOpen(true)} className="w-full md:w-auto flex justify-center items-center gap-2 px-4 py-2.5 text-sm font-bold text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors order-2 md:order-1">
                      <Trash2 size={16} /> Delete / Archive
                    </button>
                  )}

                  <div className="w-full md:w-auto flex flex-col md:flex-row gap-3 order-1 md:order-2">
                    <button type="button" onClick={handleCancel} className="w-full md:w-auto flex justify-center items-center gap-2 px-6 py-2.5 text-sm font-bold bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors">
                      <X size={16} /> Cancel
                    </button>
                    <button type="submit" className="w-full md:w-auto flex justify-center items-center gap-2 px-6 py-2.5 text-sm font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm transition-colors">
                      <Save size={16} /> Save Changes
                    </button>
                  </div>
                </div>
              )}
            </form>
          </div>

          {/* RIGHT COLUMN: Accordions (1/3 width) */}
          <div className="w-full lg:w-1/3 flex flex-col gap-4">

            {/* ASSET CONTACTS */}
            <div>
              <button onClick={() => setIsAssetContactsOpen(!isAssetContactsOpen)} className="flex items-center gap-2 md:gap-3 w-full text-left font-bold text-slate-800 dark:text-zinc-200 bg-white dark:bg-zinc-900 p-4 md:p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm hover:border-slate-300 dark:hover:border-zinc-700 transition-colors outline-none">
                {isAssetContactsOpen ? <ChevronDown size={20} className="text-slate-400 flex-shrink-0" /> : <ChevronRight size={20} className="text-slate-400 flex-shrink-0" />}
                <Server size={18} className="text-indigo-500 flex-shrink-0 md:h-5 md:w-5" />
                <span className="truncate">Asset Contacts</span>
                <span className="ml-auto text-[10px] md:text-xs bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded-full text-slate-500 whitespace-nowrap">{assetContacts.length} contacts</span>
              </button>
              {isAssetContactsOpen && (
                <div className="mt-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 md:p-6 shadow-sm animate-in fade-in slide-in-from-top-2">
                  {assetContacts.length > 0 ? (
                    <div className="relative border-l border-slate-200 dark:border-zinc-800 ml-2 md:ml-3 space-y-6">
                      {assetContacts.map((c: any) => (
                        <div key={c.mapping_id} className="relative pl-5 md:pl-6">
                          <div className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-indigo-500 ring-4 ring-white dark:ring-zinc-900"></div>
                          <div className="flex flex-col mb-1">
                            <span className="font-bold text-sm text-slate-900 dark:text-zinc-100">{c.full_name || 'No Name Provided'}</span>
                            <span className="text-[10px] md:text-xs font-mono text-slate-500">{c.email}</span>
                          </div>
                          <div className="flex gap-2 mt-1.5 flex-wrap">
                            {c.is_stakeholder && <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 text-[9px] font-extrabold uppercase tracking-wider text-amber-700 dark:text-amber-400"><Shield size={10}/> Stakeholder</span>}
                            {c.is_developer && <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 text-[9px] font-extrabold uppercase tracking-wider text-indigo-700 dark:text-indigo-400"><Code size={10}/> Developer</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-slate-500 py-4 md:py-6 text-sm">No specific contacts assigned to this asset.</div>
                  )}
                </div>
              )}
            </div>

            {/* COUNTRY CONTACTS */}
            <div>
              <button onClick={() => setIsCountryContactsOpen(!isCountryContactsOpen)} className="flex items-center gap-2 md:gap-3 w-full text-left font-bold text-slate-800 dark:text-zinc-200 bg-white dark:bg-zinc-900 p-4 md:p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm hover:border-slate-300 dark:hover:border-zinc-700 transition-colors outline-none">
                {isCountryContactsOpen ? <ChevronDown size={20} className="text-slate-400 flex-shrink-0" /> : <ChevronRight size={20} className="text-slate-400 flex-shrink-0" />}
                <MapPin size={18} className="text-amber-500 flex-shrink-0 md:h-5 md:w-5" />
                <span className="truncate">Country Contacts</span>
                <span className="ml-auto text-[10px] md:text-xs bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded-full text-slate-500 whitespace-nowrap">{countryContacts.length} contacts</span>
              </button>
              {isCountryContactsOpen && (
                <div className="mt-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 md:p-6 shadow-sm animate-in fade-in slide-in-from-top-2">
                  {!asset.country_id ? (
                     <div className="text-center text-slate-500 py-4 md:py-6 text-sm italic">Assign a country mapping to this asset to see its regional contacts.</div>
                  ) : countryContacts.length > 0 ? (
                    <div className="relative border-l border-slate-200 dark:border-zinc-800 ml-2 md:ml-3 space-y-6">
                      {countryContacts.map((c: any) => (
                        <div key={c.mapping_id} className="relative pl-5 md:pl-6">
                          <div className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-amber-500 ring-4 ring-white dark:ring-zinc-900"></div>
                          <div className="flex flex-col mb-1">
                            <span className="font-bold text-sm text-slate-900 dark:text-zinc-100">{c.full_name || 'No Name Provided'}</span>
                            <span className="text-[10px] md:text-xs font-mono text-slate-500">{c.email}</span>
                          </div>
                          <div className="flex gap-2 mt-1.5 flex-wrap">
                            {c.is_stakeholder && <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 text-[9px] font-extrabold uppercase tracking-wider text-amber-700 dark:text-amber-400"><Shield size={10}/> Stakeholder</span>}
                            {c.is_developer && <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 text-[9px] font-extrabold uppercase tracking-wider text-indigo-700 dark:text-indigo-400"><Code size={10}/> Developer</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-slate-500 py-4 md:py-6 text-sm">No contacts assigned for this region.</div>
                  )}
                </div>
              )}
            </div>

            {/* ASSET HISTORY */}
            <div>
              <button onClick={() => setIsHistoryOpen(!isHistoryOpen)} className="flex items-center gap-2 md:gap-3 w-full text-left font-bold text-slate-800 dark:text-zinc-200 bg-white dark:bg-zinc-900 p-4 md:p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm hover:border-slate-300 dark:hover:border-zinc-700 transition-colors outline-none">
                {isHistoryOpen ? <ChevronDown size={20} className="text-slate-400 flex-shrink-0" /> : <ChevronRight size={20} className="text-slate-400 flex-shrink-0" />}
                <History size={18} className="text-blue-500 flex-shrink-0 md:h-5 md:w-5" />
                <span className="truncate">Asset History</span>
                <span className="ml-auto text-[10px] md:text-xs bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded-full text-slate-500 whitespace-nowrap">{asset.history?.length || 0} events</span>
              </button>
              {isHistoryOpen && (
                <div className="mt-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 md:p-6 shadow-sm animate-in fade-in slide-in-from-top-2">
                  {asset.history && asset.history.length > 0 ? (
                    <div className="relative border-l border-slate-200 dark:border-zinc-800 ml-2 md:ml-3 space-y-6">
                      {asset.history.map((h: any) => (
                        <div key={h.id} className="relative pl-5 md:pl-6">
                          <div className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-blue-500 ring-4 ring-white dark:ring-zinc-900"></div>
                          <div className="flex flex-col md:flex-row md:justify-between items-start mb-1 gap-1 md:gap-0">
                            <span className="font-bold text-sm text-slate-900 dark:text-zinc-100">{h.action}</span>
                            <span className="text-[10px] md:text-xs font-mono text-slate-400">{formatDate(h.timestamp)}</span>
                          </div>
                          <div className="text-sm text-slate-600 dark:text-zinc-400 break-words">{h.details}</div>
                          <div className="text-[10px] md:text-xs text-slate-400 mt-1 font-medium">By: {h.user_name || 'System'}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-slate-500 py-4 md:py-6 text-sm">No history recorded for this asset yet.</div>
                  )}
                </div>
              )}
            </div>

            {/* COMPLETED TESTS */}
            <div>
              <button onClick={() => setIsCompletedTestsOpen(!isCompletedTestsOpen)} className="flex items-center gap-2 md:gap-3 w-full text-left font-bold text-slate-800 dark:text-zinc-200 bg-white dark:bg-zinc-900 p-4 md:p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm hover:border-slate-300 dark:hover:border-zinc-700 transition-colors outline-none">
                {isCompletedTestsOpen ? <ChevronDown size={20} className="text-slate-400 flex-shrink-0" /> : <ChevronRight size={20} className="text-slate-400 flex-shrink-0" />}
                <CheckCircle size={18} className="text-emerald-500 flex-shrink-0 md:h-5 md:w-5" />
                <span className="truncate">Completed Tests</span>
                <span className="ml-auto text-[10px] md:text-xs bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded-full text-slate-500 whitespace-nowrap">{asset.completed_tests?.length || 0} tests</span>
              </button>
              {isCompletedTestsOpen && (
                <div className="mt-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 md:p-6 shadow-sm animate-in fade-in slide-in-from-top-2">
                  {asset.completed_tests && asset.completed_tests.length > 0 ? (
                    <div className="relative border-l border-slate-200 dark:border-zinc-800 ml-2 md:ml-3 space-y-6">
                      {asset.completed_tests.map((test: any) => (
                        <div key={test.id} className="relative pl-5 md:pl-6">
                          <div className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-emerald-500 ring-4 ring-white dark:ring-zinc-900"></div>
                          <div className="flex flex-col md:flex-row md:justify-between items-start mb-2 md:mb-1 gap-1 md:gap-0">
                            <span className="font-bold text-sm text-slate-900 dark:text-zinc-100 flex flex-wrap items-center gap-2">
                              {test.name}
                              {test.start_week && test.start_year && (
                                <span className="px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-400 text-[10px] font-bold uppercase tracking-wider border border-emerald-200 dark:border-emerald-800/30">
                                  Wk {test.start_week}, {test.start_year}
                                </span>
                              )}
                            </span>
                            <span className="text-[10px] md:text-xs font-mono text-slate-400">{formatDate(test.completion_date)}</span>
                          </div>
                          <div className="text-sm text-slate-600 dark:text-zinc-400">
                            <span className="font-medium text-slate-700 dark:text-zinc-300">Service Lane:</span> {test.service_lane || 'Unknown'}
                          </div>
                          <div className="text-[10px] md:text-xs text-slate-400 mt-1 font-medium">
                            By: <span className="text-slate-700 dark:text-zinc-300">{test.pentesters || 'Unassigned'}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-slate-500 py-4 md:py-6 text-sm">No completed tests recorded for this asset yet.</div>
                  )}
                </div>
              )}
            </div>

            {/* SERVICENOW METADATA */}
            {asset.snow_data && (
              <div>
                <button onClick={() => setIsSnowDataOpen(!isSnowDataOpen)} className="flex items-center gap-2 md:gap-3 w-full text-left font-bold text-slate-800 dark:text-zinc-200 bg-blue-50 dark:bg-blue-900/10 p-4 md:p-5 rounded-2xl border border-blue-200 dark:border-blue-900/30 shadow-sm hover:border-blue-300 dark:hover:border-blue-800/50 transition-colors outline-none">
                  {isSnowDataOpen ? <ChevronDown size={20} className="text-blue-500 flex-shrink-0" /> : <ChevronRight size={20} className="text-blue-500 flex-shrink-0" />}
                  <Database size={18} className="text-blue-500 flex-shrink-0 md:h-5 md:w-5" />
                  <span className="truncate">ServiceNow Metadata</span>
                </button>
                {isSnowDataOpen && (
                  <div className="mt-2 bg-[#0c0c0e] rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden animate-in fade-in slide-in-from-top-2 w-full">
                    <div className="p-3 md:p-4 overflow-x-auto w-full max-w-[calc(100vw-2rem)] md:max-w-full custom-scrollbar">
                      <pre className="text-[10px] md:text-xs text-blue-300 font-mono w-max min-w-full">
                        {JSON.stringify(asset.snow_data, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}