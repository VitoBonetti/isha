import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast, { Toaster } from 'react-hot-toast';
import { Database, CloudSync, Clock } from 'lucide-react';

export default function ServiceNowSyncSettings() {
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSync, setLastSync] = useState<string | null>(null);

  // Fetch the last sync time when the page loads
  const fetchLastSync = async () => {
    try {
      const res = await axios.get(`/api/assets/servicenow/last-sync?t=${new Date().getTime()}`);
      setLastSync(res.data.last_sync);
    } catch (error) {
      console.error("Failed to fetch last sync time", error);
    }
  };

  useEffect(() => {
    fetchLastSync();
  }, []);

  const handleSnowSync = async () => {
    setIsSyncing(true);
    const loadingToastId = toast.loading("ServiceNow sync running in the background...");

    try {
      // 1. Trigger the background sync
      await axios.post('/api/assets/servicenow', {});

      // 2. Simply check the database timestamp every 5 seconds.
      // When it changes from our current 'lastSync', the background job is done!
      const pollInterval = setInterval(async () => {
        try {
          const res = await axios.get(`/api/assets/servicenow/last-sync?t=${new Date().getTime()}`);
          const newSyncTime = res.data.last_sync;

          if (newSyncTime && newSyncTime !== lastSync) {
            clearInterval(pollInterval);
            setIsSyncing(false);
            setLastSync(newSyncTime); // Instantly updates the UI date
            toast.success("Sync Complete! The database has been updated.", { id: loadingToastId, duration: 6000 });
          }
        } catch (e) {}
      }, 5000);

      // 3. Safety timeout (3 minutes max for large SNow databases)
      setTimeout(() => {
        clearInterval(pollInterval);
        setIsSyncing((currentSyncingState) => {
          if (currentSyncingState) {
            toast("Sync is processing a massive payload. Check back in a few minutes.", { id: loadingToastId, icon: '⏳' });
            fetchLastSync();
          }
          return false;
        });
      }, 180000);

    } catch (err: any) {
      setIsSyncing(false);
      toast.error(err.response?.data?.detail || "Failed to trigger ServiceNow sync.", { id: loadingToastId });
    }
  };

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">
      {/* ADDED THE MISSING TOASTER HERE */}
      <Toaster position="bottom-right" />

      <div className="mb-8">
        <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
          <CloudSync size={22} className="text-blue-500" /> ServiceNow CMDB Integration
        </h1>
        <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1 max-w-3xl">
          Manually trigger a background synchronization to fetch and map active application assets from the ServiceNow CMDB. This process maps regions, strips duplicates, and processes up to 10,000 items in the background.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl">
        {/* Sync Status Card */}
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-6 rounded-2xl shadow-sm flex flex-col justify-center">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2.5 bg-indigo-50 dark:bg-indigo-500/10 rounded-xl">
              <Clock size={20} className="text-indigo-600 dark:text-indigo-400" />
            </div>
            <h3 className="font-bold text-slate-900 dark:text-zinc-100">Last Sync Status</h3>
          </div>
          {lastSync ? (
            <p className="text-3xl font-black text-slate-700 dark:text-zinc-300 mt-2">
              {new Date(lastSync).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
            </p>
          ) : (
            <p className="text-lg font-bold text-slate-400 italic mt-2">Never Synced</p>
          )}
          <p className="text-xs text-slate-500 dark:text-zinc-400 mt-2">
            The database timestamp of the most recent successful asset import from ServiceNow.
          </p>
        </div>

        {/* Sync Execution Card */}
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-6 rounded-2xl shadow-sm text-center flex flex-col items-center">
          <div className="p-4 bg-blue-50 dark:bg-blue-500/10 rounded-full mb-4">
            <Database size={28} className="text-blue-500" />
          </div>
          <h3 className="text-base font-bold text-slate-900 dark:text-zinc-100 mb-2">Execute Database Sync</h3>
          <p className="text-xs text-slate-500 dark:text-zinc-400 mb-6 px-4">
            The sync runs on the FastAPI backend without freezing the UI.
          </p>

          <button
            onClick={handleSnowSync}
            disabled={isSyncing}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed px-6 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 transition-colors shadow-sm"
          >
            {isSyncing ? (
              <>
                <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Queuing Sync...
              </>
            ) : (
              <>
                <CloudSync size={16} /> Sync Assets Now
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}