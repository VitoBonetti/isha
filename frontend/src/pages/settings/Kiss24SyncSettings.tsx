import React, { useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import {
  ShieldCheck, Database, RefreshCw, AlertCircle, Building2, Server, UserSquare2, Layers
} from 'lucide-react';

export default function Kiss24SyncSettings() {
  const [isSyncingOrg, setIsSyncingOrg] = useState(false);
  const [isSyncingAsset, setIsSyncingAsset] = useState(false);
  const [isSyncingSnowID, setIsSyncingSnowID] = useState(false);
  const [isSyncingVulnTypesID, setIsSyncingVulnTypesID] = useState(false);
  const [isSyncingUserKissID, setIsSyncingUserKissID] = useState(false);

  // --- ACTIONS ---
  const handleGlobalSyncOrg = async () => {
    setIsSyncingOrg(true);
    const toastId = toast.loading("Syncing Organization UUIDs...");
    try {
      await axios.post('/api/kiss24/sync-org-ids');
      toast.success("Organization Sync Complete!", { id: toastId });
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Sync Failed", { id: toastId });
    } finally {
      setIsSyncingOrg(false);
    }
  };

  const handleGlobalSyncAsset = async () => {
    setIsSyncingAsset(true);
    const toastId = toast.loading("Syncing Asset IDs...");
    try {
      await axios.post('/api/kiss24/sync-asset-ids');
      toast.success("Asset Sync Complete!", { id: toastId });
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Sync Failed", { id: toastId });
    } finally {
      setIsSyncingAsset(false);
    }
  };

  const handleSyncKissSnowID = async () => {
    setIsSyncingSnowID(true);
    const toastId = toast.loading("Updating CustomField 'Service Now ID' in Keep Secure 24...");
    try {
      await axios.post(`/api/kiss24/sync-update-kiss24-snowid`);
      toast.success("CustomField 'Service Now ID' has been updated", { id: toastId });
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to update Service Now ID", { id: toastId });
    } finally {
      setIsSyncingSnowID(false);
    }
  };

  const handleSyncKissVulnTypesID = async () => {
    setIsSyncingVulnTypesID(true);
    const toastId = toast.loading("Updating contexts and vuln types from Keep Secure 24...");
    try {
      await axios.post(`/api/kiss24/sync-vuln-types`);
      toast.success("Contexts and Vuln Types have been updated", { id: toastId });
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to update Contexts and Vuln Types", { id: toastId });
    } finally {
      setIsSyncingVulnTypesID(false);
    }
  };

  const handleSyncKissUserID = async () => {
    setIsSyncingUserKissID(true);
    const toastId = toast.loading("Updating users with kiss24 UUID...");
    try {
      await axios.post(`/api/kiss24/sync-user-kiss24-uuid`);
      toast.success("Users have been updated", { id: toastId });
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to update Users", { id: toastId });
    } finally {
      setIsSyncingUserKissID(false);
    }
  };

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">

      {/* HEADER BAR */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <ShieldCheck size={22} className="text-emerald-500" /> Keep Secure 24 Synchronization
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1 max-w-3xl">
            Admin-only actions to batch update and synchronize Keep Secure 24 mappings, contexts, and custom fields across all platform services.
          </p>
        </div>
      </div>

      <div className="bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-900/30 p-4 rounded-xl flex items-center gap-3 text-amber-800 dark:text-amber-300 mb-8 shadow-sm">
        <AlertCircle className="shrink-0" size={24} />
        <div className="text-sm">
          <strong className="block mb-0.5">System Prerequisites</strong>
          You must configure your Keep Secure 24 Personal API key in your profile before running these global synchronization tasks.
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">

        {/* SYNC ORGS */}
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-6 rounded-2xl shadow-sm flex flex-col items-start gap-4 transition-colors hover:border-emerald-300 dark:hover:border-emerald-700">
          <div className="p-3 bg-emerald-50 dark:bg-emerald-500/10 rounded-xl text-emerald-600 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-500/20">
            <Building2 size={24} />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-bold text-slate-900 dark:text-zinc-100 mb-1">Sync Organizations</h3>
            <p className="text-xs text-slate-500 dark:text-zinc-400">
              Fetch and update all missing Keep Secure 24 Organization UUIDs for operating countries currently mapped in the system.
            </p>
          </div>
          <button
            onClick={handleGlobalSyncOrg}
            disabled={isSyncingOrg}
            className="w-full bg-slate-100 dark:bg-zinc-800 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 text-slate-700 dark:text-zinc-300 hover:text-emerald-600 dark:hover:text-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed border border-slate-200 dark:border-zinc-700 px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 transition-colors"
          >
            <RefreshCw size={16} className={isSyncingOrg ? 'animate-spin' : ''} />
            {isSyncingOrg ? 'Syncing...' : 'Sync Organizations'}
          </button>
        </div>

        {/* SYNC ASSETS */}
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-6 rounded-2xl shadow-sm flex flex-col items-start gap-4 transition-colors hover:border-emerald-300 dark:hover:border-emerald-700">
          <div className="p-3 bg-emerald-50 dark:bg-emerald-500/10 rounded-xl text-emerald-600 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-500/20">
            <Server size={24} />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-bold text-slate-900 dark:text-zinc-100 mb-1">Sync Asset IDs</h3>
            <p className="text-xs text-slate-500 dark:text-zinc-400">
              Cross-reference the active asset pool and update matching raw asset profiles with their respective Keep Secure 24 Asset UUIDs.
            </p>
          </div>
          <button
            onClick={handleGlobalSyncAsset}
            disabled={isSyncingAsset}
            className="w-full bg-slate-100 dark:bg-zinc-800 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 text-slate-700 dark:text-zinc-300 hover:text-emerald-600 dark:hover:text-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed border border-slate-200 dark:border-zinc-700 px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 transition-colors"
          >
            <RefreshCw size={16} className={isSyncingAsset ? 'animate-spin' : ''} />
            {isSyncingAsset ? 'Syncing...' : 'Sync Assets'}
          </button>
        </div>

        {/* SYNC USERS */}
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-6 rounded-2xl shadow-sm flex flex-col items-start gap-4 transition-colors hover:border-emerald-300 dark:hover:border-emerald-700">
          <div className="p-3 bg-emerald-50 dark:bg-emerald-500/10 rounded-xl text-emerald-600 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-500/20">
            <UserSquare2 size={24} />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-bold text-slate-900 dark:text-zinc-100 mb-1">Sync Users</h3>
            <p className="text-xs text-slate-500 dark:text-zinc-400">
              Fetch Keep Secure 24 UUIDs for all active local users and assign them to the corresponding profiles.
            </p>
          </div>
          <button
            onClick={handleSyncKissUserID}
            disabled={isSyncingUserKissID}
            className="w-full bg-slate-100 dark:bg-zinc-800 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 text-slate-700 dark:text-zinc-300 hover:text-emerald-600 dark:hover:text-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed border border-slate-200 dark:border-zinc-700 px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 transition-colors"
          >
            <RefreshCw size={16} className={isSyncingUserKissID ? 'animate-spin' : ''} />
            {isSyncingUserKissID ? 'Syncing...' : 'Sync User Profiles'}
          </button>
        </div>

        {/* SYNC VULN TYPES */}
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-6 rounded-2xl shadow-sm flex flex-col items-start gap-4 transition-colors hover:border-blue-300 dark:hover:border-blue-700">
          <div className="p-3 bg-blue-50 dark:bg-blue-500/10 rounded-xl text-blue-600 dark:text-blue-400 border border-blue-100 dark:border-blue-500/20">
            <Layers size={24} />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-bold text-slate-900 dark:text-zinc-100 mb-1">Sync Vulnerability Types</h3>
            <p className="text-xs text-slate-500 dark:text-zinc-400">
              Update contexts, CWE definitions, and core vulnerability types used when drafting new findings.
            </p>
          </div>
          <button
            onClick={handleSyncKissVulnTypesID}
            disabled={isSyncingVulnTypesID}
            className="w-full bg-slate-100 dark:bg-zinc-800 hover:bg-blue-50 dark:hover:bg-blue-500/10 text-slate-700 dark:text-zinc-300 hover:text-blue-600 dark:hover:text-blue-400 disabled:opacity-50 disabled:cursor-not-allowed border border-slate-200 dark:border-zinc-700 px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 transition-colors"
          >
            <RefreshCw size={16} className={isSyncingVulnTypesID ? 'animate-spin' : ''} />
            {isSyncingVulnTypesID ? 'Syncing...' : 'Sync Contexts & Types'}
          </button>
        </div>

        {/* SYNC SNOW ID */}
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-6 rounded-2xl shadow-sm flex flex-col items-start gap-4 transition-colors hover:border-blue-300 dark:hover:border-blue-700">
          <div className="p-3 bg-blue-50 dark:bg-blue-500/10 rounded-xl text-blue-600 dark:text-blue-400 border border-blue-100 dark:border-blue-500/20">
            <Database size={24} />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-bold text-slate-900 dark:text-zinc-100 mb-1">Update SNow Custom Fields</h3>
            <p className="text-xs text-slate-500 dark:text-zinc-400">
              Inject the "Service Now ID" custom field into Keep Secure 24 for assets linked during reconciliation.
            </p>
          </div>
          <button
            onClick={handleSyncKissSnowID}
            disabled={isSyncingSnowID}
            className="w-full bg-slate-100 dark:bg-zinc-800 hover:bg-blue-50 dark:hover:bg-blue-500/10 text-slate-700 dark:text-zinc-300 hover:text-blue-600 dark:hover:text-blue-400 disabled:opacity-50 disabled:cursor-not-allowed border border-slate-200 dark:border-zinc-700 px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 transition-colors"
          >
            <RefreshCw size={16} className={isSyncingSnowID ? 'animate-spin' : ''} />
            {isSyncingSnowID ? 'Updating Fields...' : 'Sync SNow Fields'}
          </button>
        </div>

      </div>
    </div>
  );
}