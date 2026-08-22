import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import {
  X, Cable, CheckCircle2, AlertCircle, BrainCircuit,
  Database, Activity, ShieldAlert, Lock, RefreshCw, Send, Check, DownloadCloud, Clock, User, ExternalLink, FingerprintPattern, TestTubeDiagonal, Bug
} from 'lucide-react';
import { useAppContext } from '../context/AppContext';
import Kiss24KeyModal from './Modals/Kiss24KeyModal';
import Kiss24CreateVulnModal from './Modals/Kiss24CreateVulnModal';

interface Kiss24ControlPanelProps {
  isOpen: boolean;
  onClose: () => void;
  test: any;
  onRefresh: () => void;
}

export default function Kiss24ControlPanel({ isOpen, onClose, test, onRefresh }: Kiss24ControlPanelProps) {

  const { currentUser } = useAppContext();
  const [activeTab, setActiveTab] = useState<'identifiers' | 'tests' | 'vulnerabilities'>('identifiers');

  // Action States
  const [isSyncingOrg, setIsSyncingOrg] = useState(false);
  const [isSyncingAsset, setIsSyncingAsset] = useState(false);
  const [isSyncingSnowID, setIsSyncingSnowID] = useState(false);
  const [isSyncingVulnTypesID, setIsSyncingVulnTypesID] = useState(false);
  const [isSyncingUserKissID, setIsSyncingUserKissID] = useState(false);
  const [isCreatingTest, setIsCreatingTest] = useState(false);
  const [isFetchingLive, setIsFetchingLive] = useState(false);
  const [isFetchingVulns, setIsFetchingVulns] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isKeyModalOpen, setIsKeyModalOpen] = useState(false);

  // kiss24 key State
  const [isKeyValid, setIsKeyValid] = useState<boolean | null>(null);
  const [isValidatingKey, setIsValidatingKey] = useState(false);

  // Vulns state
  const [isCreateVulnModalOpen, setIsCreateVulnModalOpen] = useState(false);

  useEffect(() => {
    if (isOpen && currentUser?.has_kiss24_key) {
      setIsValidatingKey(true);
      axios.get('/api/users/me/kiss24-key/validate')
        .then(res => setIsKeyValid(res.data.is_valid))
        .catch(() => setIsKeyValid(false))
        .finally(() => setIsValidatingKey(false));
    } else if (!currentUser?.has_kiss24_key) {
      setIsKeyValid(false);
    }
  }, [isOpen, currentUser?.has_kiss24_key]);

  // Data States
  const [liveData, setLiveData] = useState<any>(null);
  const [vulnsData, setVulnsData] = useState<any[] | null>(null);

  // 1. Identifiers
  const countryKiss24Uuid = test?.country_kiss24_uuid;
  const assetKiss24Id = test?.assets?.[0]?.kiss24_asset_id;
  const testKiss24Uuid = test?.kiss24;
  const serviceLaneName = test?.service_lane_name || 'Unknown Service';

  // 2. Tab Unlocking Logic (Fixed)
  const isKeyReady = currentUser?.has_kiss24_key && isKeyValid !== false;
  const canAccessTests = !!countryKiss24Uuid && !!assetKiss24Id && isKeyReady;
  const canAccessVulns = canAccessTests && !!testKiss24Uuid && isKeyReady;

  useEffect(() => {
    if (!canAccessTests && activeTab === 'tests') setActiveTab('identifiers');
    if (!canAccessVulns && activeTab === 'vulnerabilities') setActiveTab('identifiers');
  }, [canAccessTests, canAccessVulns, activeTab]);

  if (!isOpen) return null;

  const handleTabSwitch = (tab: 'identifiers' | 'tests' | 'vulnerabilities') => {
    if (tab === 'tests' && !canAccessTests) return;
    if (tab === 'vulnerabilities' && !canAccessVulns) return;
    setActiveTab(tab);
  }; // <--- Fixed missing brace here

  // --- ACTIONS ---

  const handleGlobalSyncOrg = async () => {
    setIsSyncingOrg(true);
    const toastId = toast.loading("Syncing Organization UUIDs...");
    try {
      await axios.post('/api/kiss24/sync-org-ids');
      toast.success("Organization Sync Complete!", { id: toastId });
      onRefresh();
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
      onRefresh();
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
      onRefresh();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Update CustomField 'Service Now ID'", { id: toastId });
    } finally {
      setIsSyncingSnowID(false);
    }
  }

  const handleSyncKissVulnTypesID = async () => {
    setIsSyncingVulnTypesID(true);
    const toastId = toast.loading("Updating contexts and vulns type from Keep Secure 24...");
    try {
      await axios.post(`/api/kiss24/sync-vuln-types`);
      toast.success("Contexts and Vuln Types have been updated", { id: toastId });
      onRefresh();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Update Contexts and Vuln Types", { id: toastId });
    } finally {
      setIsSyncingVulnTypesID(false);
    }
  }

  const handleSyncKissUserID = async () => {
    setIsSyncingUserKissID(true);
    const toastId = toast.loading("Updating users with kiss24 UUID...");
    try {
      await axios.post(`/api/kiss24/sync-user-kiss24-uuid`);
      toast.success("Users have been updated", { id: toastId });
      onRefresh();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Update Users ", { id: toastId });
    } finally {
      setIsSyncingUserKissID(false);
    }
  }

  const handleCreateTest = async () => {
    setIsCreatingTest(true);
    const toastId = toast.loading("Registering Test in Keep Secure 24...");
    try {
      await axios.post(`/api/kiss24/${test.id}/create-test`);
      toast.success("Test successfully registered!", { id: toastId });
      onRefresh();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Test Creation Failed", { id: toastId });
    } finally {
      setIsCreatingTest(false);
    }
  };

  const handleFetchLiveStatus = async () => {
    setIsFetchingLive(true);
    const toastId = toast.loading("Fetching live test data from Keep Secure 24...");
    try {
      const res = await axios.get(`/api/kiss24/${test.id}/live-status`);
      setLiveData(res.data);
      toast.success("Live data retrieved!", { id: toastId });
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to fetch live data.", { id: toastId });
    } finally {
      setIsFetchingLive(false);
    }
  };

  const handleFetchVulns = async () => {
    setIsFetchingVulns(true);
    const toastId = toast.loading("Fetching vulnerabilities from Keep Secure 24...");
    try {
      const res = await axios.get(`/api/kiss24/${test.id}/vulnerabilities`);
      setVulnsData(res.data);
      toast.success(`Retrieved ${res.data.length} vulnerabilities!`, { id: toastId });
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Failed to fetch vulnerabilities.", { id: toastId });
    } finally {
      setIsFetchingVulns(false);
    }
  };

  const handleLocalRefresh = () => {
    setIsRefreshing(true);
    onRefresh();
    setTimeout(() => setIsRefreshing(false), 800);
  };

  // Date Formatting for the Recap
  const generateFormattedDate = () => {
    if (!test?.start_year || !test?.start_week) return "Not Scheduled (Required)";
    const simpleDate = new Date(test.start_year, 0, 1 + (test.start_week - 1) * 7);
    return simpleDate.toISOString().split('T')[0];
  };

  // Helper for Severity Colors
  const getSeverityColor = (sev: string) => {
    switch (sev?.toLowerCase()) {
      case 'critical': return 'bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-400 border-purple-200 dark:border-purple-500/30';
      case 'high': return 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400 border-red-200 dark:border-red-500/30';
      case 'medium': return 'bg-orange-100 text-orange-700 dark:bg-orange-500/20 dark:text-orange-400 border-orange-200 dark:border-orange-500/30';
      case 'low': return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-500/20 dark:text-yellow-400 border-yellow-200 dark:border-yellow-500/30';
      default: return 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400 border-blue-200 dark:border-blue-500/30';
    }
  };

  return (
    <div className="fixed inset-0 z-[120] overflow-hidden bg-black/40 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="absolute inset-y-0 right-0 w-full sm:w-[500px] md:w-[600px] lg:w-[700px] flex" onClick={(e) => e.stopPropagation()}>
        <div className="w-full h-full bg-white dark:bg-zinc-950 border-l border-slate-200 dark:border-zinc-800 shadow-2xl flex flex-col">

          {/* HEADER */}
          <div className="p-4 sm:p-5 md:p-6 border-b border-slate-200 dark:border-zinc-800 bg-gradient-to-r from-blue-50/50 to-indigo-50/50 dark:from-blue-950/20 dark:to-indigo-950/20 flex justify-between items-center shrink-0">
            <div className="flex items-center gap-3 sm:gap-4 min-w-0">
              <div className="p-2 sm:p-3 bg-blue-600 text-white rounded-xl shadow-md shadow-blue-500/20 shrink-0">
                <Cable size={24} />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="font-extrabold text-lg sm:text-xl text-slate-900 dark:text-zinc-100 truncate">Keep Secure 24</h2>
                  <span className="hidden sm:inline-block text-[10px] sm:text-xs uppercase tracking-wider font-extrabold px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                    Control Panel
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-slate-500 dark:text-zinc-400 truncate mt-0.5">
                  {test?.name}
                </p>
              </div>
            </div>
            <button onClick={onClose} className="p-2 shrink-0 text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 rounded-full hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">
              <X size={24} />
            </button>
          </div>

          {/* TABS - Scrollable horizontally on mobile */}
          <div className="flex border-b border-slate-200 dark:border-zinc-800 px-2 sm:px-6 bg-slate-50/50 dark:bg-zinc-900/30 shrink-0 overflow-x-auto no-scrollbar whitespace-nowrap">
            <button onClick={() => handleTabSwitch('identifiers')} className={`py-3 sm:py-4 px-3 sm:px-4 text-xs sm:text-sm font-bold border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'identifiers' ? 'border-blue-600 text-blue-600 dark:text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-zinc-200'}`}>
              <FingerprintPattern size={16} /> Identifiers
            </button>
            <button onClick={() => handleTabSwitch('tests')} className={`py-3 sm:py-4 px-3 sm:px-4 text-xs sm:text-sm font-bold border-b-2 transition-colors flex items-center gap-2 ${!canAccessTests ? 'opacity-40 cursor-not-allowed border-transparent text-slate-400' : activeTab === 'tests' ? 'border-blue-600 text-blue-600 dark:text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-zinc-200'}`}>
              {!canAccessTests ? <Lock size={16} /> : <TestTubeDiagonal size={16} />} Test Management
            </button>
            <button onClick={() => handleTabSwitch('vulnerabilities')} className={`py-3 sm:py-4 px-3 sm:px-4 text-xs sm:text-sm font-bold border-b-2 transition-colors flex items-center gap-2 ${!canAccessVulns ? 'opacity-40 cursor-not-allowed border-transparent text-slate-400' : activeTab === 'vulnerabilities' ? 'border-blue-600 text-blue-600 dark:text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-zinc-200'}`}>
              {!canAccessVulns ? <Lock size={16} /> : <Bug size={16} />} Vulnerabilities
            </button>
          </div>

          {/* MAIN BODY PANEL */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8">

            {/* TAB 1: IDENTIFIERS */}
            {activeTab === 'identifiers' && (
              <div className="space-y-4 sm:space-y-6 animate-in fade-in flex flex-col h-full">
                {!currentUser?.has_kiss24_key && (
                  <div className="bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/30 p-4 rounded-xl flex flex-col sm:flex-row items-center justify-between gap-4 mb-6 shadow-sm">
                    <div className="flex items-center gap-3 text-red-800 dark:text-red-300">
                      <AlertCircle className="shrink-0" size={24} />
                      <div className="text-sm">
                        <strong className="block mb-0.5">Missing Personal API Key</strong>
                        You must configure your Keep Secure 24 API key before you can interact with the external platform.
                      </div>
                    </div>
                    <button
                      onClick={() => setIsKeyModalOpen(true)}
                      className="w-full sm:w-auto shrink-0 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-lg transition-colors shadow-md"
                    >
                      Configure Key
                    </button>
                  </div>
                )}

                {currentUser?.has_kiss24_key && isKeyValid === false && !isValidatingKey && (
                  <div className="bg-orange-50 dark:bg-orange-900/10 border border-orange-200 dark:border-orange-900/30 p-4 rounded-xl flex flex-col sm:flex-row items-center justify-between gap-4 mb-6 shadow-sm">
                    <div className="flex items-center gap-3 text-orange-800 dark:text-orange-300">
                      <AlertCircle className="shrink-0" size={24} />
                      <div className="text-sm">
                        <strong className="block mb-0.5">Invalid or Expired API Key</strong>
                        Your Keep Secure 24 API key was rejected by the server. It may have expired or been revoked.
                      </div>
                    </div>
                    <button
                      onClick={() => setIsKeyModalOpen(true)}
                      className="w-full sm:w-auto shrink-0 px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white text-xs font-bold rounded-lg transition-colors shadow-md"
                    >
                      Reset Key
                    </button>
                  </div>
                )}

                <div className="bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-900/30 p-3 sm:p-4 rounded-xl text-xs sm:text-sm text-blue-800 dark:text-blue-300">
                  <strong>System Prerequisites:</strong> Ensure UUIDs are populated before interacting with the API. You can trigger a global sync to fetch missing IDs at any time.
                </div>

                <div className="space-y-4 flex-1">
                  {/* Country Check */}
                  <div className={`p-4 sm:p-5 rounded-xl border flex flex-col md:flex-row items-start md:items-center justify-between gap-3 sm:gap-4 shadow-sm ${countryKiss24Uuid ? 'bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-800' : 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-900/30'}`}>
                    <div className="flex items-start gap-3 sm:gap-4 w-full md:w-auto">
                      {countryKiss24Uuid ? <CheckCircle2 size={24} className="text-emerald-500 shrink-0 mt-0.5" /> : <AlertCircle size={24} className="text-red-500 shrink-0 mt-0.5" />}
                      <div className="flex-1 min-w-0">
                        <span className={`font-bold text-sm sm:text-base block mb-1 ${countryKiss24Uuid ? 'text-slate-900 dark:text-zinc-100' : 'text-red-800 dark:text-red-400'}`}>1. Country KISS24 UUID</span>
                        <div className="bg-slate-100 dark:bg-zinc-950 p-2 rounded text-[10px] sm:text-xs font-mono text-slate-600 dark:text-zinc-400 break-all border border-slate-200 dark:border-zinc-800">
                          {countryKiss24Uuid || "MISSING"}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Asset Check */}
                  <div className={`p-4 sm:p-5 rounded-xl border flex flex-col md:flex-row items-start md:items-center justify-between gap-3 sm:gap-4 shadow-sm ${assetKiss24Id ? 'bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-800' : 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-900/30'}`}>
                    <div className="flex items-start gap-3 sm:gap-4 w-full md:w-auto">
                      {assetKiss24Id ? <CheckCircle2 size={24} className="text-emerald-500 shrink-0 mt-0.5" /> : <AlertCircle size={24} className="text-red-500 shrink-0 mt-0.5" />}
                      <div className="flex-1 min-w-0">
                        <span className={`font-bold text-sm sm:text-base block mb-1 ${assetKiss24Id ? 'text-slate-900 dark:text-zinc-100' : 'text-red-800 dark:text-red-400'}`}>2. Raw Asset KISS24 ID</span>
                        <div className="bg-slate-100 dark:bg-zinc-950 p-2 rounded text-[10px] sm:text-xs font-mono text-slate-600 dark:text-zinc-400 break-all border border-slate-200 dark:border-zinc-800">
                          {assetKiss24Id || "MISSING"}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Test Check */}
                  <div className={`p-4 sm:p-5 rounded-xl border flex items-start gap-3 sm:gap-4 shadow-sm ${testKiss24Uuid ? 'bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-800' : 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-900/30'}`}>
                    {testKiss24Uuid ? <CheckCircle2 size={24} className="text-emerald-500 shrink-0 mt-0.5" /> : <Lock size={24} className="text-amber-500 shrink-0 mt-0.5" />}
                    <div className="flex-1 min-w-0">
                      <span className={`font-bold text-sm sm:text-base block mb-1 ${testKiss24Uuid ? 'text-slate-900 dark:text-zinc-100' : 'text-amber-800 dark:text-amber-400'}`}>3. Test Entity UUID</span>
                      <p className="text-xs sm:text-sm text-slate-500 dark:text-zinc-400 mb-2">Generated by KISS24 upon successful registration.</p>
                      <div className="bg-slate-100 dark:bg-zinc-950 p-2 rounded text-[10px] sm:text-xs font-mono text-slate-600 dark:text-zinc-400 break-all border border-slate-200 dark:border-zinc-800">
                        {testKiss24Uuid || "NOT GENERATED YET"}
                      </div>
                    </div>
                  </div>
                </div>

                {/* ADMIN ACTION PANEL */}
                {currentUser?.role === 'admin' && (
                  <div className="mt-8 pt-6 border-t border-slate-200 dark:border-zinc-800">
                    <h3 className="text-sm font-bold text-slate-800 dark:text-zinc-200 mb-1 flex items-center gap-2">
                      <Database size={16} className="text-blue-500" /> Global Synchronization
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-zinc-400 mb-4">
                      Admin-only actions to batch update Keep Secure 24 mappings across all services.
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
                      <button
                        onClick={handleGlobalSyncOrg}
                        disabled={isSyncingOrg}
                        className="flex flex-col items-center justify-center gap-3 p-4 bg-slate-50 hover:bg-slate-100 dark:bg-zinc-900 dark:hover:bg-zinc-800/80 border border-slate-200 dark:border-zinc-800 text-slate-700 dark:text-zinc-300 font-bold text-xs rounded-xl transition-all shadow-sm disabled:opacity-50"
                      >
                        <div className={`p-2 rounded-lg ${isSyncingOrg ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30' : 'bg-slate-200 text-slate-600 dark:bg-zinc-800 dark:text-zinc-400'}`}>
                          <RefreshCw size={18} className={isSyncingOrg ? 'animate-spin' : ''} />
                        </div>
                        Sync Orgs
                      </button>

                      <button
                        onClick={handleGlobalSyncAsset}
                        disabled={isSyncingAsset}
                        className="flex flex-col items-center justify-center gap-3 p-4 bg-slate-50 hover:bg-slate-100 dark:bg-zinc-900 dark:hover:bg-zinc-800/80 border border-slate-200 dark:border-zinc-800 text-slate-700 dark:text-zinc-300 font-bold text-xs rounded-xl transition-all shadow-sm disabled:opacity-50"
                      >
                        <div className={`p-2 rounded-lg ${isSyncingAsset ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30' : 'bg-slate-200 text-slate-600 dark:bg-zinc-800 dark:text-zinc-400'}`}>
                          <RefreshCw size={18} className={isSyncingAsset ? 'animate-spin' : ''} />
                        </div>
                        Sync Assets
                      </button>

                      <button
                        onClick={handleSyncKissSnowID}
                        disabled={isSyncingSnowID}
                        className="flex flex-col items-center justify-center gap-3 p-4 bg-slate-50 hover:bg-slate-100 dark:bg-zinc-900 dark:hover:bg-zinc-800/80 border border-slate-200 dark:border-zinc-800 text-slate-700 dark:text-zinc-300 font-bold text-xs rounded-xl transition-all shadow-sm disabled:opacity-50"
                      >
                        <div className={`p-2 rounded-lg ${isSyncingSnowID ? 'bg-amber-100 text-amber-600 dark:bg-amber-900/30' : 'bg-slate-200 text-slate-600 dark:bg-zinc-800 dark:text-zinc-400'}`}>
                          <RefreshCw size={18} className={isSyncingSnowID ? 'animate-spin' : ''} />
                        </div>
                        Sync SnowID
                      </button>

                      <button
                        onClick={handleSyncKissVulnTypesID}
                        disabled={isSyncingVulnTypesID}
                        className="flex flex-col items-center justify-center gap-3 p-4 bg-slate-50 hover:bg-slate-100 dark:bg-zinc-900 dark:hover:bg-zinc-800/80 border border-slate-200 dark:border-zinc-800 text-slate-700 dark:text-zinc-300 font-bold text-xs rounded-xl transition-all shadow-sm disabled:opacity-50"
                      >
                        <div className={`p-2 rounded-lg ${isSyncingVulnTypesID ? 'bg-amber-100 text-amber-600 dark:bg-amber-900/30' : 'bg-slate-200 text-slate-600 dark:bg-zinc-800 dark:text-zinc-400'}`}>
                          <RefreshCw size={18} className={isSyncingVulnTypesID ? 'animate-spin' : ''} />
                        </div>
                        Sync Types
                      </button>

                      <button
                        onClick={handleSyncKissUserID}
                        disabled={isSyncingUserKissID}
                        className="flex flex-col items-center justify-center gap-3 p-4 bg-slate-50 hover:bg-slate-100 dark:bg-zinc-900 dark:hover:bg-zinc-800/80 border border-slate-200 dark:border-zinc-800 text-slate-700 dark:text-zinc-300 font-bold text-xs rounded-xl transition-all shadow-sm disabled:opacity-50"
                      >
                        <div className={`p-2 rounded-lg ${isSyncingUserKissID ? 'bg-amber-100 text-amber-600 dark:bg-amber-900/30' : 'bg-slate-200 text-slate-600 dark:bg-zinc-800 dark:text-zinc-400'}`}>
                          <RefreshCw size={18} className={isSyncingUserKissID ? 'animate-spin' : ''} />
                        </div>
                        Sync Users
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: TEST MANAGEMENT */}
            {activeTab === 'tests' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-right-4">
                <div className="border-b border-slate-200 dark:border-zinc-800 pb-4 flex flex-col sm:flex-row justify-between sm:items-end gap-3 sm:gap-0">
                  <div>
                    <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100">Test Creation & Operations</h3>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-zinc-400 mt-1">Register the pentest or fetch live details.</p>
                  </div>
                  {testKiss24Uuid && (
                    <button
                      onClick={handleFetchLiveStatus}
                      disabled={isFetchingLive}
                      className="w-full sm:w-auto px-4 py-2.5 sm:py-2 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 text-blue-600 dark:text-blue-400 text-xs font-bold rounded-lg transition-colors flex justify-center items-center gap-2 border border-blue-200 dark:border-blue-900/50"
                    >
                      <RefreshCw size={14} className={isFetchingLive ? "animate-spin" : ""} /> Sync Status
                    </button>
                  )}
                </div>

                {!testKiss24Uuid ? (
                  /* --- TEST CREATION UI --- */
                  <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl overflow-hidden shadow-sm">
                    <div className="p-3 sm:p-4 bg-slate-50 dark:bg-zinc-950 border-b border-slate-200 dark:border-zinc-800 flex items-center gap-2">
                      <Send size={18} className="text-blue-500" />
                      <span className="font-bold text-sm sm:text-base text-slate-900 dark:text-zinc-100">Creation Payload Preview</span>
                    </div>

                    <div className="p-4 sm:p-6 space-y-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
                        <div className="p-3 bg-slate-50 dark:bg-zinc-950/50 rounded-lg border border-slate-100 dark:border-zinc-800">
                          <span className="text-[9px] sm:text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Target Name</span>
                          <span className="font-mono text-xs sm:text-sm text-slate-800 dark:text-zinc-200 block truncate">{test.name} - {serviceLaneName} {test.start_year}</span>
                        </div>
                        <div className="p-3 bg-slate-50 dark:bg-zinc-950/50 rounded-lg border border-slate-100 dark:border-zinc-800">
                          <span className="text-[9px] sm:text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Scheduled Start</span>
                          <span className="font-mono text-xs sm:text-sm text-slate-800 dark:text-zinc-200">{generateFormattedDate()}</span>
                        </div>
                      </div>

                      <button
                        onClick={handleCreateTest}
                        disabled={isCreatingTest || !test.start_year || !test.start_week}
                        className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 dark:disabled:bg-zinc-800 text-white text-sm font-bold rounded-xl transition-colors flex justify-center items-center gap-2 mt-4 shadow-sm"
                      >
                        {isCreatingTest ? <RefreshCw className="animate-spin" size={18} /> : <Send size={18} />}
                        {isCreatingTest ? 'Creating Test...' : 'Create Test in Keep Secure 24'}
                      </button>
                      {(!test.start_year || !test.start_week) && (
                        <p className="text-center text-xs font-bold text-red-500 mt-2">Test must be scheduled (Week & Year) before creation.</p>
                      )}
                    </div>
                  </div>
                ) : (
                  /* --- LIVE DATA UI --- */
                  <div className="space-y-4">
                    {!liveData && !isFetchingLive && (
                      <div className="p-6 sm:p-10 border-2 border-dashed border-slate-200 dark:border-zinc-800 rounded-2xl flex flex-col items-center justify-center text-center bg-slate-50/50 dark:bg-zinc-900/20">
                        <DownloadCloud size={32} className="text-slate-400 mb-3 sm:mb-4" />
                        <h4 className="text-sm sm:text-base font-bold text-slate-700 dark:text-zinc-300">Test Linked Successfully</h4>
                        <p className="text-xs sm:text-sm text-slate-500 mt-2 max-w-sm mb-5 sm:mb-6">
                          This test is attached to Keep Secure 24. Fetch the live status to view its exact details and timelines from the external system.
                        </p>
                        <button
                          onClick={handleFetchLiveStatus}
                          className="w-full sm:w-auto px-6 py-2.5 sm:py-2 bg-slate-800 hover:bg-slate-900 text-white font-bold text-sm rounded-lg shadow-md transition-colors"
                        >
                          Fetch Live Status
                        </button>
                      </div>
                    )}

                    {isFetchingLive && !liveData && (
                      <div className="p-12 flex flex-col items-center justify-center text-slate-500">
                        <RefreshCw size={32} className="animate-spin text-blue-500 mb-4" />
                        <p className="font-bold text-sm">Contacting API...</p>
                      </div>
                    )}

                    {liveData && (
                      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-sm overflow-hidden animate-in zoom-in-95 duration-200">
                        <div className="p-3 sm:p-4 bg-slate-50 dark:bg-zinc-950 border-b border-slate-200 dark:border-zinc-800 flex justify-between items-center">
                          <span className="font-bold text-sm text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                            <Activity size={16} className="text-emerald-500"/> Remote Platform Data
                          </span>
                          <span className={`px-2.5 py-1 rounded-full text-[9px] sm:text-[10px] font-extrabold uppercase tracking-wider ${liveData.state === 'New' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30' : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30'}`}>
                            State: {liveData.state}
                          </span>
                        </div>

                        <div className="p-4 sm:p-5 grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
                          <div>
                            <span className="text-[9px] sm:text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">KISS24 Custom ID</span>
                            <span className="font-mono text-xs sm:text-sm font-bold text-slate-800 dark:text-zinc-200">{liveData.id}</span>
                          </div>
                          <div>
                            <span className="text-[9px] sm:text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Organization</span>
                            <span className="font-medium text-xs sm:text-sm text-slate-800 dark:text-zinc-200">{liveData.organisation_name || 'Unknown'}</span>
                          </div>
                          <div className="md:col-span-2">
                            <span className="text-[9px] sm:text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Test Name</span>
                            <span className="font-medium text-xs sm:text-sm text-slate-800 dark:text-zinc-200">{liveData.name}</span>
                          </div>

                          <div className="pt-3 border-t border-slate-100 dark:border-zinc-800/50">
                            <span className="text-[9px] sm:text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1 flex items-center gap-1"><Clock size={12}/> Scheduled For</span>
                            <span className="text-xs sm:text-sm text-slate-800 dark:text-zinc-200">{liveData.scheduled_date || 'N/A'}</span>
                          </div>
                          <div className="pt-3 border-t border-slate-100 dark:border-zinc-800/50">
                            <span className="text-[9px] sm:text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1 flex items-center gap-1"><User size={12}/> Requested By</span>
                            <span className="text-xs sm:text-sm text-slate-800 dark:text-zinc-200 block truncate" title={liveData.requested_by_email}>{liveData.requested_by_email || 'N/A'}</span>
                            <span className="text-[9px] sm:text-[10px] text-slate-400 block mt-0.5">{liveData.requested_at}</span>
                          </div>
                          <div className="pt-3 border-t border-slate-100 dark:border-zinc-800/50">
                            <span className="text-[9px] sm:text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1 flex items-center gap-1"><User size={12}/> Started By</span>
                            <span className="text-xs sm:text-sm text-slate-800 dark:text-zinc-200 block truncate">{liveData.started_by_email || 'Not Started'}</span>
                            <span className="text-[9px] sm:text-[10px] text-slate-400 block mt-0.5">{liveData.started_at || ''}</span>
                          </div>
                          <div className="pt-3 border-t border-slate-100 dark:border-zinc-800/50">
                            <span className="text-[9px] sm:text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1 flex items-center gap-1"><User size={12}/> Ended By</span>
                            <span className="text-xs sm:text-sm text-slate-800 dark:text-zinc-200 block truncate">{liveData.ended_by_email || 'Not Ended'}</span>
                            <span className="text-[9px] sm:text-[10px] text-slate-400 block mt-0.5">{liveData.ended_at || ''}</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: VULNERABILITIES */}
            {activeTab === 'vulnerabilities' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-right-4">
                <div className="border-b border-slate-200 dark:border-zinc-800 pb-4 flex flex-col sm:flex-row justify-between sm:items-end gap-4 sm:gap-0">
                  <div>
                    <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100">Vulnerabilities</h3>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-zinc-400 mt-1">Review and publish findings to Keep Secure 24.</p>
                  </div>
                  <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
                    <button
                      onClick={() => setIsCreateVulnModalOpen(true)}
                      className="w-full sm:w-auto px-4 py-2.5 sm:py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow-md transition-colors flex justify-center items-center gap-2"
                    >
                      <BrainCircuit size={14} /> Draft & Publish
                    </button>
                    <button
                      onClick={handleFetchVulns}
                      disabled={isFetchingVulns}
                      className="w-full sm:w-auto px-4 py-2.5 sm:py-2 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 text-blue-600 dark:text-blue-400 text-xs font-bold rounded-lg transition-colors flex justify-center items-center gap-2 border border-blue-200 dark:border-blue-900/50"
                    >
                      <RefreshCw size={14} className={isFetchingVulns ? "animate-spin" : ""} /> Sync Findings
                    </button>
                  </div>
                </div>

                {!vulnsData && !isFetchingVulns && (
                  <div className="p-6 sm:p-10 border-2 border-dashed border-slate-200 dark:border-zinc-800 rounded-2xl flex flex-col items-center justify-center text-center bg-slate-50/50 dark:bg-zinc-900/20">
                    <ShieldAlert size={32} className="text-slate-400 mb-3 sm:mb-4" />
                    <h4 className="text-sm sm:text-base font-bold text-slate-700 dark:text-zinc-300">No Data Fetched Yet</h4>
                    <p className="text-xs sm:text-sm text-slate-500 mt-2 max-w-sm mb-5 sm:mb-6">
                      Click the sync button above to pull the latest published vulnerabilities for this test from KISS24.
                    </p>
                  </div>
                )}

                {vulnsData && vulnsData.length === 0 && (
                  <div className="p-8 sm:p-10 rounded-2xl flex flex-col items-center justify-center text-center bg-slate-50 dark:bg-zinc-900/50 border border-slate-200 dark:border-zinc-800">
                    <CheckCircle2 size={32} className="text-emerald-500 mb-3 sm:mb-4" />
                    <h4 className="text-sm sm:text-base font-bold text-slate-700 dark:text-zinc-300">0 Vulnerabilities Found</h4>
                    <p className="text-xs sm:text-sm text-slate-500 mt-1">There are currently no findings published to this test.</p>
                  </div>
                )}

                {vulnsData && vulnsData.length > 0 && (
                  <div className="space-y-4">
                    {vulnsData.map((vuln: any) => (
                      <div key={vuln.uuid} className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-sm overflow-hidden flex flex-col hover:border-blue-300 dark:hover:border-blue-700/50 transition-colors">

                        <div className="p-3 sm:p-4 border-b border-slate-100 dark:border-zinc-800/50 flex flex-col sm:flex-row justify-between items-start gap-3 sm:gap-4">
                          <div className="flex-1 min-w-0 w-full">
                            <div className="flex items-center flex-wrap gap-2 mb-2">
                              <span className="font-mono text-[10px] sm:text-xs font-bold text-slate-500 dark:text-zinc-400 bg-slate-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">
                                {vuln.id}
                              </span>
                              <span className={`px-2 py-0.5 rounded text-[9px] sm:text-[10px] font-extrabold uppercase tracking-wider border ${getSeverityColor(vuln.severity)}`}>
                                {vuln.severity}
                              </span>
                              <span className={`px-2 py-0.5 rounded text-[9px] sm:text-[10px] font-extrabold uppercase tracking-wider border ${vuln.state === 'Closed' || vuln.state === 'Resolved' ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400 dark:border-emerald-900/50' : 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-zinc-800 dark:text-zinc-400 dark:border-zinc-700'}`}>
                                State: {vuln.state}
                              </span>
                            </div>
                            <h4 className="font-bold text-xs sm:text-sm text-slate-900 dark:text-zinc-100 leading-snug">
                              {vuln.description}
                            </h4>
                          </div>

                          <a
                            href={`https://randstad.eu.vulnmanager.com/vulnerabilities/${vuln.uuid}/show`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="shrink-0 w-full sm:w-auto flex justify-center p-2 text-blue-600 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/40 rounded-lg transition-colors"
                            title="Open in Keep Secure 24"
                          >
                            <ExternalLink size={16} /> <span className="sm:hidden ml-2 text-xs font-bold">View Finding</span>
                          </a>
                        </div>

                        <div className="p-3 bg-slate-50 dark:bg-zinc-950/50 flex flex-col sm:flex-row sm:items-center justify-between gap-1 sm:gap-2 text-[10px] sm:text-xs text-slate-500 dark:text-zinc-400">
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium">Published:</span> {vuln.published_at || 'Unknown'}
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium">By:</span> {vuln.published_by_name || 'System'}
                          </div>
                        </div>

                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

          </div>

          {/* FOOTER */}
          <div className="p-4 sm:p-5 md:p-6 border-t border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-950 flex justify-between items-center shrink-0">
            {/* FIXED: Added visual refresh state to footer button */}
            <button
              onClick={handleLocalRefresh}
              disabled={isRefreshing}
              className="text-xs sm:text-sm font-bold text-slate-500 hover:text-slate-800 dark:hover:text-zinc-200 flex items-center gap-2 transition-colors disabled:opacity-50"
            >
              <RefreshCw size={16} className={isRefreshing ? 'animate-spin' : ''} /> Refresh Panel
            </button>
            <button
              onClick={onClose}
              className="px-5 py-2.5 sm:px-6 sm:py-2.5 bg-slate-200 dark:bg-zinc-800 hover:bg-slate-300 dark:hover:bg-zinc-700 text-slate-800 dark:text-zinc-200 font-bold text-xs sm:text-sm rounded-xl transition-colors"
            >
              Close
            </button>
          </div>

        </div>
      </div>
      <Kiss24KeyModal isOpen={isKeyModalOpen} onClose={() => setIsKeyModalOpen(false)} />
      <Kiss24CreateVulnModal
        isOpen={isCreateVulnModalOpen}
        testId={test.id}
        onClose={() => setIsCreateVulnModalOpen(false)}
        onSuccess={handleFetchVulns} // Automatically fetch the new vulns after publishing!
      />
    </div>
  );
}