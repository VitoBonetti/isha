import { useState, useEffect } from "react";
import axios from "axios";
import TopNav from "../components/TopNav";
import toast, { Toaster } from "react-hot-toast";
import { Globe, BarChart3, Database, CheckCircle, Clock, Layers } from "lucide-react";

export default function CountriesView() {
  const [analytics, setAnalytics] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Default to current year
  const [targetYear, setTargetYear] = useState(new Date().getFullYear());

  useEffect(() => {
    fetchAnalytics();
  }, [targetYear]);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`/api/countries/analytics?year=${targetYear}`);
      setAnalytics(res.data);
    } catch (error) {
      toast.error("Failed to load country analytics.");
    } finally {
      setLoading(false);
    }
  };

  // Global totals for the header cards
  const globalTotals = analytics.reduce((acc, curr) => ({
    raw: acc.raw + curr.raw_assets_count,
    pool: acc.pool + curr.pool_assets_count,
    completed: acc.completed + curr.completed_tests_count,
    active: acc.active + curr.active_tests_count
  }), { raw: 0, pool: 0, completed: 0, active: 0 });

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100 pb-12">
      <TopNav />
      <Toaster position="bottom-right" />

      <div className="pt-32 px-6 max-w-7xl mx-auto">
        <div className="flex justify-between items-end mb-8">
          <div>
            <h1 className="text-2xl font-extrabold flex items-center gap-2">
              <Globe size={28} className="text-emerald-600" />
              Regional Analytics
            </h1>
            <p className="text-slate-500 dark:text-zinc-400 mt-1">Aggregated asset volume and pentest coverage by country.</p>
          </div>

          <div className="flex items-center gap-3 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-2 rounded-xl shadow-sm">
            <span className="text-sm font-bold text-slate-500 dark:text-zinc-400 pl-2">Reporting Year:</span>
            <select
              className="bg-slate-50 dark:bg-zinc-950 border border-slate-300 dark:border-zinc-700 text-slate-900 dark:text-zinc-100 font-bold px-4 py-1.5 rounded-lg outline-none cursor-pointer focus:ring-2 focus:ring-emerald-500"
              value={targetYear}
              onChange={(e) => setTargetYear(parseInt(e.target.value))}
            >
              {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        </div>

        {/* Global KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white dark:bg-zinc-900 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm flex items-center gap-4">
            <div className="p-3 bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 rounded-xl"><Database size={24}/></div>
            <div>
              <p className="text-sm text-slate-500 font-bold uppercase tracking-wider">Total Raw</p>
              <p className="text-2xl font-black">{globalTotals.raw}</p>
            </div>
          </div>
          <div className="bg-white dark:bg-zinc-900 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm flex items-center gap-4">
            <div className="p-3 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-xl border border-indigo-100 dark:border-indigo-500/20"><Layers size={24}/></div>
            <div>
              <p className="text-sm text-slate-500 font-bold uppercase tracking-wider">In Pool</p>
              <p className="text-2xl font-black text-indigo-600 dark:text-indigo-400">{globalTotals.pool}</p>
            </div>
          </div>
          <div className="bg-white dark:bg-zinc-900 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm flex items-center gap-4">
            <div className="p-3 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-xl border border-emerald-100 dark:border-emerald-500/20"><CheckCircle size={24}/></div>
            <div>
              <p className="text-sm text-slate-500 font-bold uppercase tracking-wider">Completed ({targetYear})</p>
              <p className="text-2xl font-black text-emerald-600 dark:text-emerald-400">{globalTotals.completed}</p>
            </div>
          </div>
          <div className="bg-white dark:bg-zinc-900 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm flex items-center gap-4">
            <div className="p-3 bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 rounded-xl border border-blue-100 dark:border-blue-500/20"><Clock size={24}/></div>
            <div>
              <p className="text-sm text-slate-500 font-bold uppercase tracking-wider">Active ({targetYear})</p>
              <p className="text-2xl font-black text-blue-600 dark:text-blue-400">{globalTotals.active}</p>
            </div>
          </div>
        </div>

        {/* Detailed Table */}
        <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden flex flex-col">
          {loading ? (
            <div className="p-12 text-center text-slate-500">Calculating analytics...</div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 dark:bg-zinc-800/50 border-b border-slate-200 dark:border-zinc-700">
                <tr>
                  <th className="p-4 font-semibold text-slate-500 uppercase tracking-wider">Country</th>
                  <th className="p-4 font-semibold text-slate-500 uppercase tracking-wider text-right">Raw Inv.</th>
                  <th className="p-4 font-semibold text-indigo-500 uppercase tracking-wider text-right">Pool Inv.</th>
                  <th className="p-4 font-semibold text-emerald-500 uppercase tracking-wider text-center">Completed ({targetYear})</th>
                  <th className="p-4 font-semibold text-blue-500 uppercase tracking-wider text-center">Active ({targetYear})</th>
                  <th className="p-4 font-semibold text-slate-500 uppercase tracking-wider">Coverage Ratio</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                {analytics.map((c) => {
                  // Coverage Ratio = (Completed + Active) / Pool Inventory
                  const coveragePct = c.pool_assets_count > 0
                    ? Math.min(100, ((c.completed_tests_count + c.active_tests_count) / c.pool_assets_count) * 100)
                    : 0;

                  return (
                    <tr key={c.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors">
                      <td className="p-4">
                        <div className="font-bold text-slate-900 dark:text-zinc-100">{c.name} <span className="text-xs text-slate-400 font-mono ml-2">{c.code}</span></div>
                        <div className="text-xs text-slate-500 mt-0.5">{c.region_name || 'No Region'}</div>
                      </td>
                      <td className="p-4 text-right font-medium text-slate-600 dark:text-zinc-400">{c.raw_assets_count}</td>
                      <td className="p-4 text-right font-bold text-indigo-700 dark:text-indigo-400">{c.pool_assets_count}</td>

                      <td className="p-4 text-center">
                        {c.completed_tests_count > 0 ? (
                          <span className="px-3 py-1 bg-emerald-100 dark:bg-emerald-500/20 text-emerald-800 dark:text-emerald-400 font-bold rounded-lg border border-emerald-200 dark:border-emerald-500/30">{c.completed_tests_count}</span>
                        ) : <span className="text-slate-300 dark:text-zinc-700">-</span>}
                      </td>

                      <td className="p-4 text-center">
                        {c.active_tests_count > 0 ? (
                          <span className="px-3 py-1 bg-blue-100 dark:bg-blue-500/20 text-blue-800 dark:text-blue-400 font-bold rounded-lg border border-blue-200 dark:border-blue-500/30">{c.active_tests_count}</span>
                        ) : <span className="text-slate-300 dark:text-zinc-700">-</span>}
                      </td>

                      <td className="p-4 w-48">
                        <div className="flex items-center gap-3">
                          <div className="flex-1 bg-slate-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden flex">
                            <div className="bg-emerald-500 h-full" style={{ width: `${(c.completed_tests_count / Math.max(1, c.pool_assets_count)) * 100}%` }} />
                            <div className="bg-blue-500 h-full" style={{ width: `${(c.active_tests_count / Math.max(1, c.pool_assets_count)) * 100}%` }} />
                          </div>
                          <span className="text-xs font-bold text-slate-500">{Math.round(coveragePct)}%</span>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}