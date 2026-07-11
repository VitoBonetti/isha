import { useState, useEffect } from "react";
import axios from "axios";
import TopNav from "../components/TopNav";
import { Activity, Zap, ShieldAlert, Target } from "lucide-react";

export default function InsightsView() {
  const [data, setData] = useState<any>(null);
  const [targetYear, setTargetYear] = useState(new Date().getFullYear());

  useEffect(() => {
    axios.get(`/api/insights/?year=${targetYear}`).then(res => setData(res.data));
  }, [targetYear]);

  if (!data) return <div className="min-h-screen pt-32 text-center text-slate-500">Loading Insights...</div>;

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100 pb-12">
      <TopNav />
      <div className="pt-32 px-6 max-w-7xl mx-auto">

        <div className="flex justify-between items-end mb-8">
          <div>
            <h1 className="text-2xl font-extrabold flex items-center gap-2"><Target size={28} className="text-blue-500" /> Platform Insights</h1>
            <p className="text-slate-500 mt-1">Resource allocation, burn rates, and asset coverage.</p>
          </div>
          <select
            className="px-4 py-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-lg font-bold outline-none"
            value={targetYear} onChange={e => setTargetYear(parseInt(e.target.value))}
          >
            {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>

        {/* Top KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white dark:bg-zinc-900 p-5 rounded-2xl border border-slate-200 dark:border-zinc-800">
            <div className="text-sm font-bold text-slate-500 mb-1">Net Yearly Capacity</div>
            <div className="text-3xl font-black text-emerald-600">{data.capacity.net.toFixed(1)} <span className="text-sm">cr</span></div>
            <div className="text-xs text-slate-400 mt-2">Gross: {data.capacity.gross.toFixed(1)}cr</div>
          </div>

          <div className="bg-white dark:bg-zinc-900 p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 md:col-span-3 flex justify-between items-center">
             <div>
                <div className="text-sm font-bold text-slate-500 mb-1">Time-Off Costs</div>
                <div className="flex gap-6 mt-2">
                    <div><span className="text-red-500 font-black">{data.capacity.events.national_holiday.toFixed(1)}</span> <span className="text-xs text-slate-500">cr (Holidays)</span></div>
                    <div><span className="text-orange-500 font-black">{data.capacity.events.sick_day.toFixed(1)}</span> <span className="text-xs text-slate-500">cr (Sick)</span></div>
                    <div><span className="text-blue-500 font-black">{data.capacity.events.personal_time_off.toFixed(1)}</span> <span className="text-xs text-slate-500">cr (PTO)</span></div>
                    <div><span className="text-purple-500 font-black">{data.capacity.events.team_day.toFixed(1)}</span> <span className="text-xs text-slate-500">cr (Team)</span></div>
                </div>
             </div>
          </div>
        </div>

        {/* Service Breakdown */}
        <h2 className="text-xl font-bold mb-4">Service Forecasts & Pipeline</h2>
        <div className="space-y-6">
          {data.services.map((s: any) => {
             const total = s.total_pool_assets || 1; // prevent div/0
             const pctComplete = (s.completed_tests / total) * 100;
             const pctPlanned = (s.planned_tests / total) * 100;
             const pctReady = (s.unplanned_assets / total) * 100;

             return (
               <div key={s.service_id} className="bg-white dark:bg-zinc-900 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h3 className="font-bold text-lg flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{backgroundColor: s.theme_color}}/> {s.service_name}
                      </h3>
                      <div className="text-sm text-slate-500 flex gap-4 mt-1">
                        <span>Burned: <b className="text-slate-700 dark:text-zinc-300">{s.real_assigned_credits.toFixed(1)} cr</b></span>
                        <span>Forecast: <b className="text-amber-600">{s.forecast_credits.toFixed(1)} cr</b></span>
                      </div>
                    </div>
                  </div>

                  {/* Stacked Progress Bar */}
                  <div className="mb-2 flex justify-between text-xs font-bold text-slate-500">
                    <span>{s.completed_tests} Completed</span>
                    <span>{s.planned_tests} Planned</span>
                    <span>{s.unplanned_assets} Ready</span>
                  </div>
                  <div className="w-full h-4 rounded-full overflow-hidden flex bg-slate-100 dark:bg-zinc-800 mb-6">
                    <div className="h-full bg-emerald-500" style={{ width: `${pctComplete}%` }} title="Completed" />
                    <div className="h-full bg-blue-500" style={{ width: `${pctPlanned}%` }} title="Planned" />
                    <div className="h-full bg-slate-300 dark:bg-zinc-600" style={{ width: `${pctReady}%` }} title="Unplanned" />
                  </div>

                  {/* Categories Sub-table */}
                  {s.categories.length > 0 && (
                    <table className="w-full text-left text-sm mt-4 bg-slate-50 dark:bg-zinc-950/50 rounded-xl overflow-hidden">
                      <thead className="text-slate-500 border-b border-slate-200 dark:border-zinc-800">
                        <tr>
                          <th className="p-3">Category</th>
                          <th className="p-3">Target Goal</th>
                          <th className="p-3">In Pool</th>
                          <th className="p-3">Completed</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-zinc-800/50">
                        {s.categories.map((c: any) => (
                          <tr key={c.id}>
                            <td className="p-3 font-medium text-slate-700 dark:text-zinc-300">{c.name}</td>
                            <td className="p-3 font-bold">{c.target_goal}</td>
                            <td className="p-3 text-indigo-600">{c.cat_pool_count}</td>
                            <td className="p-3 text-emerald-600">{c.cat_completed}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
               </div>
             )
          })}
        </div>
      </div>
    </div>
  );
}