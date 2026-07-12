import { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import TopNav from "../components/TopNav";
import ConfirmModal from "../components/Modals/ConfirmModal";
import toast, { Toaster } from "react-hot-toast";
import { ChevronLeft, Save, Trash2, ShieldAlert, FileText, Edit2, X, History, ChevronDown, ChevronRight, Clock, CheckCircle } from "lucide-react";

export default function AssetDetailView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const backPath = location.state?.from || "/raw";
  const backLabel = location.state?.label || "Raw Assets";
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isCompletedTestsOpen, setIsCompletedTestsOpen] = useState(false);

  const [countries, setCountries] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [assetTypes, setAssetTypes] = useState<any[]>([]);

  const [asset, setAsset] = useState<any>(null);
  const [originalAsset, setOriginalAsset] = useState<any>(null); // To revert changes on Cancel
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  useEffect(() => {
    Promise.all([
      axios.get(`/api/assets/raw/${id}`),
      axios.get('/api/countries/'),
      axios.get('/api/services/'),
      axios.get('/api/board/categories/'),
      axios.get('/api/assets/types')
    ]).then(([resAsset, resC, resS, resCat, resTypes]) => {
      setAssetTypes(resTypes.data);
      setAsset(resAsset.data);
      setOriginalAsset(resAsset.data);
      setCountries(resC.data);
      setServices(resS.data);
      setCategories(resCat.data);
    }).catch(() => {
      toast.error("Failed to load asset");
      navigate("/raw");
    }).finally(() => setLoading(false));
  }, [id, navigate]);

  if (loading || !asset) return <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 flex items-center justify-center">Loading...</div>;

  const businessCritical = Math.min(9, (asset.confidentiality_rating || 0) + (asset.integrity_rating || 0) + (asset.availability_rating || 0));
  const filteredCategories = categories.filter(c => c.service_lane_id === asset.service_forecast_id);

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
        category_id: asset.category_id === "" ? null : asset.category_id
      };
      await axios.put(`/api/assets/raw/${id}`, payload);

      // Re-fetch to get updated dates and history
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
      await axios.post(`/api/assets/raw/bulk-delete`, { raw_asset_ids: [id] });
      toast.success("Asset deleted");
      navigate("/raw");
    } catch (error) {
      toast.error("Failed to delete asset");
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

  // Dynamic classes based on edit state
  const inputClasses = isEditing
    ? "w-full mt-1 p-2.5 border border-slate-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-emerald-500 outline-none transition-all"
    : "w-full mt-1 p-2.5 border border-transparent rounded-lg bg-slate-50 dark:bg-zinc-950/50 text-slate-900 dark:text-zinc-100 outline-none cursor-default font-medium appearance-none";

  const ratingClasses = isEditing
    ? "w-full mt-1 p-2 border border-slate-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-sm text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-emerald-500 outline-none transition-all"
    : "w-full mt-1 p-2 border border-transparent rounded-lg bg-slate-100 dark:bg-zinc-900 text-sm text-slate-900 dark:text-zinc-100 outline-none cursor-default font-bold";

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100">
      <TopNav />
      <Toaster position="bottom-right" />
      <ConfirmModal isOpen={deleteModalOpen} title="Delete Asset" message="Are you sure you want to permanently delete this asset? If it is currently in the active pool, it will be removed." onConfirm={handleDelete} onCancel={() => setDeleteModalOpen(false)} />

      <div className="pt-32 pb-12 px-6 max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <button onClick={() => navigate(backPath)} className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white transition-colors">
            <ChevronLeft size={16} /> Back to {backLabel}
          </button>

          {!isEditing && (
            <button onClick={() => setIsEditing(true)} className="flex items-center gap-2 px-4 py-2 bg-slate-200 hover:bg-slate-300 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-800 dark:text-zinc-200 rounded-lg text-sm font-bold transition-colors">
              <Edit2 size={16} /> Edit Asset
            </button>
          )}
        </div>

        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-8 shadow-sm">
          <div className="flex justify-between items-start mb-8 border-b border-slate-100 dark:border-zinc-800 pb-6">
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2"><FileText className="text-emerald-500" /> {asset.name}</h1>
              <div className="text-slate-500 text-sm mt-2 flex flex-col gap-1">
                <span className="font-mono">ID: {asset.id}</span>
                <span className="flex items-center gap-1.5"><Clock size={14}/> Created: {formatDate(asset.create_date)}</span>
                {asset.update_date && <span className="flex items-center gap-1.5"><Edit2 size={14}/> Updated: {formatDate(asset.update_date)}</span>}
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
              {asset.is_promoted ? (
                <span className="px-3 py-1 bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-400 font-bold text-xs rounded-full uppercase tracking-wider">In Active Pool</span>
              ) : (
                <span className="px-3 py-1 bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 font-bold text-xs rounded-full uppercase tracking-wider">Raw Status</span>
              )}
            </div>
          </div>

          <form onSubmit={handleUpdate} className="space-y-8">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div>
                <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Asset Name</label>
                <input required disabled={!isEditing} className={inputClasses} value={asset.name} onChange={e => setAsset({...asset, name: e.target.value})} />
              </div>
              <div>
                <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Asset Type</label>
                <select required disabled={!isEditing} className={inputClasses} value={asset.asset_type_id} onChange={e => setAsset({...asset, asset_type_id: e.target.value})}>
                  {assetTypes.map(at => <option key={at.id} value={at.id}>{at.name}</option>)}
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Description</label>
                <textarea disabled={!isEditing} className={`${inputClasses} resize-none ${isEditing ? 'h-24' : 'h-auto min-h-[40px]'}`} value={asset.description || ""} onChange={e => setAsset({...asset, description: e.target.value})} />
              </div>

              <div className="sm:col-span-2">
                <label className={`flex items-center w-fit gap-3 p-3 rounded-lg transition-colors ${isEditing ? 'bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50' : 'bg-transparent'}`}>
                  <input type="checkbox" disabled={!isEditing} className="h-4 w-4 rounded text-emerald-500 border-slate-300 disabled:opacity-70" checked={asset.facing_internet} onChange={e => setAsset({...asset, facing_internet: e.target.checked})} />
                  <div className="flex flex-col">
                    <span className="text-sm font-bold text-slate-700 dark:text-zinc-300">Facing Internet</span>
                  </div>
                </label>
                <label className={`flex items-center w-fit gap-3 p-3 rounded-lg transition-colors ${isEditing ? 'bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50' : 'bg-transparent '}`}>
                  <input type="checkbox" disabled={!isEditing} className="h-4 w-4 rounded text-blue-500 border-slate-300 disabled:opacity-70" checked={asset.duplicate_allowed || false} onChange={e => setAsset({...asset, duplicate_allowed: e.target.checked})} />
                  <div className="flex flex-col">
                    <span className="text-sm font-bold text-slate-700 dark:text-zinc-300">Allow Duplicates</span>
                  </div>
                </label>
              </div>
            </div>

            <div className={`p-6 rounded-xl border ${isEditing ? 'bg-slate-50 dark:bg-zinc-950/50 border-slate-200 dark:border-zinc-800' : 'border-slate-100 dark:border-zinc-800/50'}`}>
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-4 flex items-center gap-2"><ShieldAlert size={16}/> Risk Ratings</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300">Bus. Critical</label>
                  <input type="number" disabled className={`${ratingClasses} !bg-slate-200 dark:!bg-zinc-800 text-slate-500 font-bold cursor-not-allowed`} value={businessCritical} readOnly />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300">Confidentiality</label>
                  <input type="number" disabled={!isEditing} min="0" max="5" className={ratingClasses} value={asset.confidentiality_rating || 0} onChange={e => setAsset({...asset, confidentiality_rating: parseInt(e.target.value) || 0})} />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300">Integrity</label>
                  <input type="number" disabled={!isEditing} min="0" max="5" className={ratingClasses} value={asset.integrity_rating || 0} onChange={e => setAsset({...asset, integrity_rating: parseInt(e.target.value) || 0})} />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300">Availability</label>
                  <input type="number" disabled={!isEditing} min="0" max="5" className={ratingClasses} value={asset.availability_rating || 0} onChange={e => setAsset({...asset, availability_rating: parseInt(e.target.value) || 0})} />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <div>
                <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Country Mapping</label>
                <select disabled={!isEditing} className={inputClasses} value={asset.country_id || ""} onChange={e => setAsset({...asset, country_id: e.target.value})}>
                  <option value="">-- None --</option>
                  {countries.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
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
                  {filteredCategories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
            </div>

            {/* Form Actions (Only visible when editing) */}
            {isEditing && (
              <div className="flex justify-between items-center pt-8 border-t border-slate-100 dark:border-zinc-800 animate-in fade-in slide-in-from-bottom-2">
                <button type="button" onClick={() => setDeleteModalOpen(true)} className="flex items-center gap-2 px-4 py-2.5 text-sm font-bold text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors">
                  <Trash2 size={16} /> Delete Asset
                </button>
                <div className="flex gap-3">
                  <button type="button" onClick={handleCancel} className="flex items-center gap-2 px-6 py-2.5 text-sm font-bold bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors">
                    <X size={16} /> Cancel
                  </button>
                  <button type="submit" className="flex items-center gap-2 px-6 py-2.5 text-sm font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm transition-colors">
                    <Save size={16} /> Save Changes
                  </button>
                </div>
              </div>
            )}
          </form>
        </div>

        {/* ASSET HISTORY ACCORDION */}
        <div className="mt-8">
          <button
            onClick={() => setIsHistoryOpen(!isHistoryOpen)}
            className="flex items-center gap-3 w-full text-left font-bold text-slate-800 dark:text-zinc-200 bg-white dark:bg-zinc-900 p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm hover:border-slate-300 dark:hover:border-zinc-700 transition-colors outline-none"
          >
            {isHistoryOpen ? <ChevronDown size={20} className="text-slate-400" /> : <ChevronRight size={20} className="text-slate-400" />}
            <History size={20} className="text-blue-500" />
            Asset History Log
            <span className="ml-auto text-xs bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded-full text-slate-500">{asset.history?.length || 0} events</span>
          </button>

          {isHistoryOpen && (
            <div className="mt-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 shadow-sm animate-in fade-in slide-in-from-top-2">
              {asset.history && asset.history.length > 0 ? (
                <div className="relative border-l border-slate-200 dark:border-zinc-800 ml-3 space-y-6">
                  {asset.history.map((h: any) => (
                    <div key={h.id} className="relative pl-6">
                      <div className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-blue-500 ring-4 ring-white dark:ring-zinc-900"></div>
                      <div className="flex justify-between items-start mb-1">
                        <span className="font-bold text-sm text-slate-900 dark:text-zinc-100">{h.action}</span>
                        <span className="text-xs font-mono text-slate-400">{formatDate(h.timestamp)}</span>
                      </div>
                      <div className="text-sm text-slate-600 dark:text-zinc-400">{h.details}</div>
                      <div className="text-xs text-slate-400 mt-1 font-medium">By: {h.user_name || 'System'}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-slate-500 py-6">No history recorded for this asset yet.</div>
              )}
            </div>
          )}
        </div>
        {/* COMPLETED TESTS ACCORDION */}
        <div className="mt-6">
          <button
            onClick={() => setIsCompletedTestsOpen(!isCompletedTestsOpen)}
            className="flex items-center gap-3 w-full text-left font-bold text-slate-800 dark:text-zinc-200 bg-white dark:bg-zinc-900 p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm hover:border-slate-300 dark:hover:border-zinc-700 transition-colors outline-none"
          >
            {isCompletedTestsOpen ? <ChevronDown size={20} className="text-slate-400" /> : <ChevronRight size={20} className="text-slate-400" />}
            <CheckCircle size={20} className="text-emerald-500" />
            Completed Tests
            <span className="ml-auto text-xs bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded-full text-slate-500">{asset.completed_tests?.length || 0} tests</span>
          </button>

          {isCompletedTestsOpen && (
            <div className="mt-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 shadow-sm animate-in fade-in slide-in-from-top-2">
              {asset.completed_tests && asset.completed_tests.length > 0 ? (
                <div className="relative border-l border-slate-200 dark:border-zinc-800 ml-3 space-y-6">
                  {asset.completed_tests.map((test: any) => (
                    <div key={test.id} className="relative pl-6">
                      <div className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-emerald-500 ring-4 ring-white dark:ring-zinc-900"></div>
                      <div className="flex justify-between items-start mb-1">
                        <span className="font-bold text-sm text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                          {test.name}
                          {test.start_week && test.start_year && (
                            <span className="px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-400 text-[10px] font-bold uppercase tracking-wider border border-emerald-200 dark:border-emerald-800/30">
                              Wk {test.start_week}, {test.start_year}
                            </span>
                          )}
                        </span>
                        <span className="text-xs font-mono text-slate-400">{formatDate(test.completion_date)}</span>
                      </div>
                      <div className="text-sm text-slate-600 dark:text-zinc-400">
                        <span className="font-medium text-slate-700 dark:text-zinc-300">Service Lane:</span> {test.service_lane || 'Unknown'}
                      </div>
                      <div className="text-xs text-slate-400 mt-1 font-medium">
                        By: <span className="text-slate-700 dark:text-zinc-300">{test.pentesters || 'Unassigned'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-slate-500 py-6">No completed tests recorded for this asset yet.</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}