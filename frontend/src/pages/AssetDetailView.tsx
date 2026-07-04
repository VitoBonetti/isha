import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import TopNav from "../components/TopNav";
import ConfirmModal from "../components/Modals/ConfirmModal";
import toast, { Toaster } from "react-hot-toast";
import { ChevronLeft, Save, Trash2, ShieldAlert, FileText } from "lucide-react";

export default function AssetDetailView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);

  const [countries, setCountries] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [assetTypes, setAssetTypes] = useState<any[]>([]);

  const [asset, setAsset] = useState<any>(null);
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
        business_critical: businessCritical,
        country_id: asset.country_id === "" ? null : asset.country_id,
        service_forecast_id: asset.service_forecast_id === "" ? null : asset.service_forecast_id,
        category_id: asset.category_id === "" ? null : asset.category_id
      };
      await axios.put(`/api/assets/raw/${id}`, payload);
      toast.success("Asset updated successfully");
    } catch (error) {
      toast.error("Failed to update asset");
    }
  };

  const handleDelete = async () => {
    try {
      await axios.delete(`/api/assets/raw/${id}`);
      toast.success("Asset deleted");
      navigate("/raw");
    } catch (error) {
      toast.error("Failed to delete asset");
    }
  };

  const inputClasses = "w-full mt-1 p-2.5 border border-slate-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-emerald-500 outline-none";
  const ratingClasses = "w-full mt-1 p-2 border border-slate-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-950 text-sm text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-emerald-500 outline-none";

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100">
      <TopNav />
      <Toaster position="bottom-right" />
      <ConfirmModal isOpen={deleteModalOpen} title="Delete Asset" message="Are you sure you want to permanently delete this asset? If it is currently in the active pool, it will be removed." onConfirm={handleDelete} onCancel={() => setDeleteModalOpen(false)} />

      <div className="pt-32 pb-12 px-6 max-w-4xl mx-auto">
        <button onClick={() => navigate("/raw")} className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white mb-6 transition-colors">
          <ChevronLeft size={16} /> Back to Raw Assets
        </button>

        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-8 shadow-sm">
          <div className="flex justify-between items-start mb-8 border-b border-slate-100 dark:border-zinc-800 pb-6">
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2"><FileText className="text-emerald-500" /> {asset.name}</h1>
              <p className="text-slate-500 text-sm mt-1 font-mono">ID: {asset.id}</p>
            </div>
            {asset.is_promoted ? (
              <span className="px-3 py-1 bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-400 font-bold text-xs rounded-full uppercase tracking-wider">In Active Pool</span>
            ) : (
              <span className="px-3 py-1 bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 font-bold text-xs rounded-full uppercase tracking-wider">Raw Status</span>
            )}
          </div>

          <form onSubmit={handleUpdate} className="space-y-8">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div>
                <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Asset Name *</label>
                <input required className={inputClasses} value={asset.name} onChange={e => setAsset({...asset, name: e.target.value})} />
              </div>
              <div>
                <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Asset Type *</label>
                <select required className={inputClasses} value={asset.asset_type_id} onChange={e => setAsset({...asset, asset_type_id: e.target.value})}>
                  {assetTypes.map(at => <option key={at.id} value={at.id}>{at.name}</option>)}
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Description</label>
                <textarea className={`${inputClasses} resize-none h-24`} value={asset.description || ""} onChange={e => setAsset({...asset, description: e.target.value})} />
              </div>

              <div className="sm:col-span-2">
                <label className="flex items-center w-fit gap-3 p-3 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors">
                  <input type="checkbox" className="h-4 w-4 rounded text-emerald-500 border-slate-300" checked={asset.facing_internet} onChange={e => setAsset({...asset, facing_internet: e.target.checked})} />
                  <div className="flex flex-col">
                    <span className="text-sm font-bold text-slate-700 dark:text-zinc-300">Facing Internet</span>
                  </div>
                </label>
              </div>
            </div>

            <div className="bg-slate-50 dark:bg-zinc-950/50 p-6 rounded-xl border border-slate-200 dark:border-zinc-800">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-4 flex items-center gap-2"><ShieldAlert size={16}/> Risk Ratings</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300">Bus. Critical</label>
                  <input type="number" className={`${ratingClasses} bg-slate-100 dark:bg-zinc-800 text-slate-500 font-bold cursor-not-allowed`} value={businessCritical} readOnly />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300">Confidentiality</label>
                  <input type="number" min="0" max="5" className={ratingClasses} value={asset.confidentiality_rating || 0} onChange={e => setAsset({...asset, confidentiality_rating: parseInt(e.target.value) || 0})} />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300">Integrity</label>
                  <input type="number" min="0" max="5" className={ratingClasses} value={asset.integrity_rating || 0} onChange={e => setAsset({...asset, integrity_rating: parseInt(e.target.value) || 0})} />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300">Availability</label>
                  <input type="number" min="0" max="5" className={ratingClasses} value={asset.availability_rating || 0} onChange={e => setAsset({...asset, availability_rating: parseInt(e.target.value) || 0})} />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <div>
                <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Country Mapping</label>
                <select className={inputClasses} value={asset.country_id || ""} onChange={e => setAsset({...asset, country_id: e.target.value})}>
                  <option value="">-- None --</option>
                  {countries.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Service Forecast</label>
                <select className={inputClasses} value={asset.service_forecast_id || ""} onChange={e => setAsset({...asset, service_forecast_id: e.target.value, category_id: ""})}>
                  <option value="">-- None --</option>
                  {services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Forecast Category</label>
                <select className={`${inputClasses} disabled:opacity-50`} value={asset.category_id || ""} onChange={e => setAsset({...asset, category_id: e.target.value})} disabled={!asset.service_forecast_id}>
                  <option value="">-- None --</option>
                  {filteredCategories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
            </div>

            <div className="flex justify-between items-center pt-8 border-t border-slate-100 dark:border-zinc-800">
              <button type="button" onClick={() => setDeleteModalOpen(true)} className="flex items-center gap-2 px-4 py-2.5 text-sm font-bold text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors">
                <Trash2 size={16} /> Delete Asset
              </button>
              <button type="submit" className="flex items-center gap-2 px-6 py-2.5 text-sm font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm transition-colors">
                <Save size={16} /> Save Changes
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}