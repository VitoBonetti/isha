import React, { useState } from 'react';
import { X, Plus, ShieldAlert, Globe } from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';

interface AddRawAssetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  countries: any[];
  services: any[];
  categories: any[];
  assetTypes: any[];
}

export default function AddRawAssetModal({ isOpen, onClose, onSuccess, countries, services, categories, assetTypes }: AddRawAssetModalProps) {
  const [newAsset, setNewAsset] = useState({
    name: "",
    description: "",
    asset_type_id: "",
    facing_internet: false,
    duplicate_allowed: false,
    country_id: "",
    service_forecast_id: "",
    category_id: "",
    confidentiality_rating: 0,
    integrity_rating: 0,
    availability_rating: 0
  });

  if (!isOpen) return null;

  const businessCritical = Math.min(
    9,
    newAsset.confidentiality_rating + newAsset.integrity_rating + newAsset.availability_rating
  );

  const filteredCategories = categories.filter(c => c.service_lane_id === newAsset.service_forecast_id);

  const handleCreateAsset = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        ...newAsset,
        business_critical: businessCritical,
        country_id: newAsset.country_id === "" ? null : newAsset.country_id,
        service_forecast_id: newAsset.service_forecast_id === "" ? null : newAsset.service_forecast_id,
        category_id: newAsset.category_id === "" ? null : newAsset.category_id
      };

      await axios.post('/api/assets/raw', payload);
      toast.success("Asset added successfully!");

      setNewAsset({ name: "", description: "", asset_type_id: "", facing_internet: false, duplicate_allowed: false, country_id: "", service_forecast_id: "", category_id: "", confidentiality_rating: 0, integrity_rating: 0, availability_rating: 0 });
      onSuccess();
      onClose();
    } catch (error) {
      toast.error("Failed to create asset.");
    }
  };

  const inputClasses = "w-full mt-1 p-2.5 border border-slate-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-emerald-500 outline-none text-sm md:text-base";
  const ratingClasses = "w-full mt-1 p-2 border border-slate-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-950 text-sm text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-emerald-500 outline-none";

  return (
    <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-50 flex items-start sm:items-center justify-center p-2 sm:p-4 animate-in fade-in overflow-y-auto">
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 sm:p-6 w-[95%] sm:w-full max-w-xl shadow-2xl animate-in zoom-in-95 my-4 sm:my-8 flex-shrink-0">
        <div className="flex justify-between items-center mb-4 sm:mb-6 border-b border-slate-100 dark:border-zinc-800 pb-4">
          <h2 className="text-lg sm:text-xl font-bold flex items-center gap-2">
            <Plus size={20} className="text-emerald-500" /> Add Raw Asset
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors p-1">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleCreateAsset} className="space-y-4 sm:space-y-5">
          {/* Basic Info */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Asset Name *</label>
              <input required className={inputClasses} value={newAsset.name} onChange={e => setNewAsset({...newAsset, name: e.target.value})} placeholder="e.g. Primary Banking API" />
            </div>
            <div>
              <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Asset Type *</label>
              <select required className={inputClasses} value={newAsset.asset_type_id} onChange={e => setNewAsset({...newAsset, asset_type_id: e.target.value})}>
                <option value="" disabled>-- Select Type --</option>
                {assetTypes.map(at => <option key={at.id} value={at.id}>{at.name}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Description</label>
            <textarea className={`${inputClasses} resize-none h-20`} value={newAsset.description} onChange={e => setNewAsset({...newAsset, description: e.target.value})} placeholder="Brief overview of the asset..." />
          </div>

          {/* Toggle Buttons Container */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
            <label className="flex items-center gap-3 p-3 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors">
              <input type="checkbox" className="h-4 w-4 rounded text-emerald-500 border-slate-300 flex-shrink-0" checked={newAsset.facing_internet} onChange={e => setNewAsset({...newAsset, facing_internet: e.target.checked})} />
              <div className="flex flex-col">
                <span className="text-sm font-bold text-slate-700 dark:text-zinc-300 flex items-center gap-2"><Globe size={14}/> Facing Internet</span>
                <span className="text-xs text-slate-500 leading-tight mt-0.5">Accessible externally without VPN.</span>
              </div>
            </label>
            <label className="flex items-center gap-3 p-3 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors">
              <input type="checkbox" className="h-4 w-4 rounded text-blue-500 border-slate-300 flex-shrink-0" checked={newAsset.duplicate_allowed} onChange={e => setNewAsset({...newAsset, duplicate_allowed: e.target.checked})} />
              <div className="flex flex-col">
                <span className="text-sm font-bold text-slate-700 dark:text-zinc-300 flex items-center gap-2">Allow Duplicates</span>
                <span className="text-xs text-slate-500 leading-tight mt-0.5">Permit concurrent active tests.</span>
              </div>
            </label>
          </div>

          {/* Ratings (CIA Triad & Business Criticality) */}
          <div className="bg-slate-50 dark:bg-zinc-950/50 p-3 sm:p-4 rounded-xl border border-slate-200 dark:border-zinc-800">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-3 flex items-center gap-1.5"><ShieldAlert size={14}/> Risk Ratings</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
              <div>
                <label className="text-[10px] sm:text-xs font-bold text-slate-700 dark:text-zinc-300 truncate block">Bus. Critical</label>
                <input
                  type="number"
                  className={`${ratingClasses} bg-slate-100 dark:bg-zinc-800 text-slate-500 font-bold cursor-not-allowed`}
                  value={businessCritical}
                  readOnly
                  title="Sum of C, I, and A (Max 9)"
                />
              </div>
              <div>
                <label className="text-[10px] sm:text-xs font-bold text-slate-700 dark:text-zinc-300 truncate block">Confidentiality</label>
                <input type="number" min="0" max="5" className={ratingClasses} value={newAsset.confidentiality_rating} onChange={e => setNewAsset({...newAsset, confidentiality_rating: parseInt(e.target.value) || 0})} />
              </div>
              <div>
                <label className="text-[10px] sm:text-xs font-bold text-slate-700 dark:text-zinc-300 truncate block">Integrity</label>
                <input type="number" min="0" max="5" className={ratingClasses} value={newAsset.integrity_rating} onChange={e => setNewAsset({...newAsset, integrity_rating: parseInt(e.target.value) || 0})} />
              </div>
              <div>
                <label className="text-[10px] sm:text-xs font-bold text-slate-700 dark:text-zinc-300 truncate block">Availability</label>
                <input type="number" min="0" max="5" className={ratingClasses} value={newAsset.availability_rating} onChange={e => setNewAsset({...newAsset, availability_rating: parseInt(e.target.value) || 0})} />
              </div>
            </div>
          </div>

          {/* Mappings */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Country</label>
              <select className={inputClasses} value={newAsset.country_id} onChange={e => setNewAsset({...newAsset, country_id: e.target.value})}>
                <option value="">-- None --</option>
                {countries.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Service Lane</label>
              <select className={inputClasses} value={newAsset.service_forecast_id} onChange={e => setNewAsset({...newAsset, service_forecast_id: e.target.value, category_id: ""})}>
                <option value="">-- None --</option>
                {services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Category</label>
              <select className={`${inputClasses} disabled:opacity-50 disabled:cursor-not-allowed`} value={newAsset.category_id} onChange={e => setNewAsset({...newAsset, category_id: e.target.value})} disabled={!newAsset.service_forecast_id}>
                <option value="">-- None --</option>
                {filteredCategories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          </div>

          {/* Action Buttons - Stacked on Mobile */}
          <div className="flex flex-col sm:flex-row justify-end gap-3 pt-4 sm:pt-6 border-t border-slate-100 dark:border-zinc-800 mt-6">
            <button type="submit" className="w-full sm:w-auto px-5 py-2.5 text-sm font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm transition-colors order-1 sm:order-2 flex justify-center items-center">
              Save Asset
            </button>
            <button type="button" onClick={onClose} className="w-full sm:w-auto px-4 py-2.5 text-sm font-bold bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors order-2 sm:order-1 flex justify-center items-center">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}