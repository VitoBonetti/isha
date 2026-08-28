import React, { useState } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { Database, CloudSync } from 'lucide-react';

export default function ServiceNowSyncSettings() {
  const [isSyncing, setIsSyncing] = useState(false);

  const handleSnowSync = async () => {
    setIsSyncing(true);
    const startTime = new Date().getTime();
    const loadingToastId = toast.loading("ServiceNow sync initiated. Fetching and mapping data in the background...");

    try {
      await axios.post('/api/assets/servicenow', {});

      const pollInterval = setInterval(async () => {
        try {
          const logsRes = await axios.get('/api/system/logs/');
          const latestLogs = logsRes.data;

          const completionLog = latestLogs.find((log: any) =>
            new Date(log.timestamp).getTime() > startTime &&
            (log.action.includes("SERVICE_NOW_SYNC_SUCCESS") || log.action.includes("SERVICE_NOW_SYNC_CRASH"))
          );

          if (completionLog) {
            clearInterval(pollInterval);
            setIsSyncing(false);

            if (completionLog.action.includes("SUCCESS")) {
              toast.success("Sync Complete! Check the system logs for details.", { id: loadingToastId, duration: 6000 });
            } else {
              toast.error("Sync Failed: " + completionLog.details, { id: loadingToastId, duration: 10000 });
            }
          }
        } catch (e) {}
      }, 3000);

      setTimeout(() => {
        clearInterval(pollInterval);
        setIsSyncing(false);
        toast("Sync is taking longer than usual. Check the logs manually in a few minutes.", { id: loadingToastId, icon: '⏳' });
      }, 120000);

    } catch (err: any) {
      setIsSyncing(false);
      toast.error(err.response?.data?.detail || "Failed to trigger ServiceNow sync.", { id: loadingToastId });
    }
  };

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
          <CloudSync size={22} className="text-blue-500" /> ServiceNow CMDB Integration
        </h1>
        <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1 max-w-3xl">
          Manually trigger a background synchronization to fetch and map active application assets from the ServiceNow CMDB. This process maps regions, strips duplicates, and processes up to 10,000 items in the background.
        </p>
      </div>

      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-8 rounded-2xl shadow-sm max-w-xl text-center flex flex-col items-center">
        <div className="p-4 bg-blue-50 dark:bg-blue-500/10 rounded-full mb-4">
          <Database size={32} className="text-blue-500" />
        </div>
        <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100 mb-2">Execute Database Sync</h3>
        <p className="text-sm text-slate-500 dark:text-zinc-400 mb-6">
          The sync will run on the FastAPI backend without freezing the UI. You will receive a toast notification when the operation finishes.
        </p>

        <button
          onClick={handleSnowSync}
          disabled={isSyncing}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed px-6 py-3 rounded-xl text-sm font-bold flex justify-center items-center gap-2 transition-colors shadow-sm"
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
              <CloudSync size={18} /> Sync Assets Now
            </>
          )}
        </button>
      </div>
    </div>
  );
}