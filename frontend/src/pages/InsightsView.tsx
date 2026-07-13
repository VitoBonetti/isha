import { useState, useEffect } from "react";
import axios from "axios";
import TopNav from "../components/TopNav";
import { Target, ChevronDown, ChevronRight, AlertTriangle, LineChart, Info, Zap  } from "lucide-react";

// --- CUSTOM OVERFLOW-AWARE TARGET BAR ---
const TargetBar = ({ label, completed, planned, unplanned, goal, isHero }: any) => {
  const actual = completed + planned + unplanned;
  const maxVal = Math.max(actual, goal, 1);
  const pctCompleted = (completed / maxVal) * 100;
  const pctPlanned = (planned / maxVal) * 100;
  const pctUnplanned = (unplanned / maxVal) * 100;
  const pctGoal = (goal / maxVal) * 100;

  return (
    <div className={`mb-5 ${isHero ? 'bg-slate-50 dark:bg-zinc-950/50 p-5 rounded-2xl border border-slate-100 dark:border-zinc-800/80 shadow-sm' : ''}`}>
      <div className="flex justify-between items-end mb-2.5">
        <span className={`font-bold text-slate-700 dark:text-zinc-300 flex items-center gap-2 ${isHero ? 'text-lg' : 'text-sm'}`}>
          {isHero && <Zap size={18} className="text-blue-500" />} {label}
        </span>
        <span className="text-slate-500 font-medium text-xs">
          Actual: <strong className={`text-slate-700 dark:text-zinc-300 ${isHero ? 'text-sm' : ''}`}>{actual}</strong> / Target: {goal || 'None'}
        </span>
      </div>
      <div className={`relative bg-slate-100 dark:bg-zinc-800 overflow-hidden flex shadow-inner ${isHero ? 'h-8 rounded-xl' : 'h-5 rounded-md opacity-90'}`}>
        <div className="bg-emerald-500 h-full border-r border-white/20" style={{ width: `${pctCompleted}%` }} title={`Completed: ${completed}`} />
        <div className="bg-blue-500 h-full border-r border-white/20" style={{ width: `${pctPlanned}%` }} title={`Scheduled: ${planned}`} />
        <div className="bg-slate-300 dark:bg-zinc-600 h-full" style={{ width: `${pctUnplanned}%` }} title={`Backlog: ${unplanned}`} />

        {goal > 0 && (
          <div
            className={`absolute top-0 bottom-0 border-r-[3px] border-red-500 z-10 ${isHero ? 'border-r-[4px] shadow-[0_0_10px_rgba(239,68,68,0.8)]' : ''}`}
            style={{ left: `${pctGoal}%` }}
            title={`Target Goal: ${goal}`}
          />
        )}
      </div>
    </div>
  );
};

// --- BREAKDOWN CARD COMPONENT ---
const ForecastCard = ({ title, total, breakdown, isOpen, toggleOpen }: any) => (
  <div className="bg-white dark:bg-zinc-900 p-5 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm flex flex-col">
    <div className="flex justify-between items-center mb-4">
      <span className="font-bold text-slate-700 dark:text-zinc-300">{title}</span>
      <span className="font-black text-slate-900 dark:text-zinc-100">{total.toFixed(1)} cr</span>
    </div>
    <button onClick={toggleOpen} className="flex items-center gap-1 text-xs font-bold text-slate-400 hover:text-slate-600 dark:hover:text-zinc-300 transition-colors mb-2">
      {isOpen ? <ChevronDown size={14}/> : <ChevronRight size={14}/>} View Breakdown
    </button>
    {isOpen && (
      <div className="mt-2 space-y-2 border-t border-slate-100 dark:border-zinc-800 pt-3">
        {Object.entries(breakdown).filter(([_, val]) => (val as number) > 0).map(([key, val]) => (
          <div key={key} className="flex justify-between text-sm">
            <span className="text-slate-500 dark:text-zinc-400 font-medium">{key}:</span>
            <span className="font-bold text-slate-700 dark:text-zinc-300">{(val as number).toFixed(1)}</span>
          </div>
        ))}
      </div>
    )}
  </div>
);

export default function InsightsView() {
  const [data, setData] = useState<any>(null);
  const [targetYear, setTargetYear] = useState(new Date().getFullYear());

  // Breakdown Toggles
  const [showSched, setShowSched] = useState(false);
  const [showBacklog, setShowBacklog] = useState(false);
  const [showTimeOff, setShowTimeOff] = useState(false);

  // Accordion Toggles
  const [openServices, setOpenServices] = useState<Record<string, boolean>>({});

  const toggleService = (id: string) => setOpenServices(prev => ({ ...prev, [id]: !prev[id] }));

  useEffect(() => {
    axios.get(`/api/insights/?year=${targetYear}`).then(res => setData(res.data));
  }, [targetYear]);

  if (!data) return <div className="min-h-screen pt-32 text-center text-slate-500">Loading Insights...</div>;

  const netCap = data.forecast.net_capacity;

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100 pb-12 bg-slate-50/30 dark:bg-[#09090b]">
      <TopNav />
      <div className="pt-32 px-6 max-w-7xl mx-auto">

        <div className="flex justify-between items-end mb-8">
          <div>
            <h1 className="text-3xl font-black flex items-center gap-3"><LineChart size={32} className="text-blue-600" /> Insights</h1>
            <p className="text-slate-500 mt-2 font-medium">Strategic overview of team capacity vs. target goals.</p>
          </div>
          <select
            className="px-4 py-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl font-black text-blue-600 outline-none shadow-sm"
            value={targetYear} onChange={e => setTargetYear(parseInt(e.target.value))}
          >
            {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>

        {/* 1. Header Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="bg-white dark:bg-zinc-900 p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm border-t-4 border-t-slate-700">
            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">1. Gross Capacity</div>
            <div className="text-3xl font-black">{data.header.gross_capacity.toFixed(1)} <span className="text-sm font-bold text-slate-400">cr</span></div>
          </div>
          <div className="bg-white dark:bg-zinc-900 p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm border-t-4 border-t-red-500">
            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">2. PTO & Holidays</div>
            <div className="text-3xl font-black text-red-500">-{data.header.total_time_off.toFixed(1)} <span className="text-sm font-bold text-red-300">cr</span></div>
          </div>
          <div className="bg-white dark:bg-zinc-900 p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm border-t-4 border-t-blue-500">
            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">3. Assigned Resources</div>
            <div className="text-3xl font-black text-blue-600">-{data.header.assigned_resources.toFixed(1)} <span className="text-sm font-bold text-blue-300">cr</span></div>
          </div>
          <div className="bg-white dark:bg-zinc-900 p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm border-t-4 border-t-emerald-500">
            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">4. Unassigned Bench</div>
            <div className="text-3xl font-black text-emerald-600">{data.header.unassigned_bench.toFixed(1)} <span className="text-sm font-bold text-emerald-300">cr</span></div>
          </div>
        </div>

        {/* 2. Annual Workload Forecast */}
        <div className="bg-red-50/50 dark:bg-red-950/10 border border-red-100 dark:border-red-900/30 rounded-2xl p-6 mb-10 shadow-sm">
          <h2 className="text-xl font-bold text-red-900 dark:text-red-400 mb-6">Annual Workload Forecast</h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <ForecastCard title="Scheduled Tests" total={data.forecast.scheduled.total} breakdown={data.forecast.scheduled.breakdown} isOpen={showSched} toggleOpen={() => setShowSched(!showSched)} />
            <ForecastCard title="Backlog Tests" total={data.forecast.backlog.total} breakdown={data.forecast.backlog.breakdown} isOpen={showBacklog} toggleOpen={() => setShowBacklog(!showBacklog)} />
            <ForecastCard title="Time Off" total={data.forecast.time_off.total} breakdown={data.forecast.time_off.breakdown} isOpen={showTimeOff} toggleOpen={() => setShowTimeOff(!showTimeOff)} />
          </div>

          <div className="border-t border-red-200 dark:border-red-900/50 pt-6 flex flex-col md:flex-row justify-between items-center gap-4">
            <div>
              <div className="text-xs font-bold text-red-800 dark:text-red-500 uppercase tracking-wider mb-1">Net Capacity Remaining</div>
              <div className={`text-3xl font-black ${netCap < 0 ? 'text-red-600 dark:text-red-500' : 'text-emerald-600 dark:text-emerald-500'}`}>
                {netCap > 0 ? '+' : ''}{netCap.toFixed(1)} <span className="text-sm">cr</span>
              </div>
            </div>
            {netCap < 0 ? (
              <div className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 text-amber-800 dark:text-amber-400 px-4 py-3 rounded-lg flex items-center gap-3 font-bold text-sm shadow-sm">
                <AlertTriangle size={18} /> You are understaffed by {Math.abs(netCap).toFixed(1)} credits for this workload.
              </div>
            ) : netCap > 0 ? (
              <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30 text-blue-800 dark:text-blue-400 px-4 py-3 rounded-lg flex items-center gap-3 font-bold text-sm shadow-sm">
                <Info size={18} /> You have {netCap.toFixed(1)} unassigned credits. Team members are sitting on the bench!
              </div>
            ) : null}
          </div>
        </div>

        {/* 3. Service & Category Accordions */}
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-slate-900 dark:text-zinc-100">Target vs Actual Performance</h2>
          <div className="flex gap-4 text-xs font-bold text-slate-500">
            <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-emerald-500 rounded-sm"></div> Completed</div>
            <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-blue-500 rounded-sm"></div> Scheduled</div>
            <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-slate-300 dark:bg-zinc-600 rounded-sm"></div> Backlog</div>
            <div className="flex items-center gap-1.5"><div className="w-0.5 h-3 bg-red-500 rounded-sm"></div> Target Goal</div>
          </div>
        </div>

        <div className="space-y-4">
          {data.services.map((s: any) => (
            <div key={s.id} className="bg-white dark:bg-zinc-900 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden transition-colors">
              <button onClick={() => toggleService(s.id)} className="w-full p-6 flex justify-between items-center hover:bg-slate-50 dark:hover:bg-zinc-800/50 outline-none">
                <div className="flex items-center gap-3">
                  {openServices[s.id] ? <ChevronDown size={20} className="text-slate-400" /> : <ChevronRight size={20} className="text-slate-400" />}
                  <div className="w-3 h-3 rounded-full shadow-sm" style={{backgroundColor: s.theme_color}}/>
                  <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100">{s.name}</h3>
                  {!s.is_active && <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wider bg-slate-100 dark:bg-zinc-800 text-slate-500">Inactive</span>}
                </div>
              </button>

              {openServices[s.id] && (
                <div className="px-6 pb-6 pt-2 border-t border-slate-100 dark:border-zinc-800 animate-in fade-in slide-in-from-top-2">
                  <TargetBar label="Overall Service Total" completed={s.completed} planned={s.planned} unplanned={s.unplanned} goal={s.target_goal} isHero={true} />

                  {s.categories && s.categories.length > 0 && (
                    <div className="mt-8">
                      <div className="flex justify-between items-center mb-4">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">Category Breakdowns</h4>
                        {s.goal_warning && (
                          <span className="text-[11px] font-bold text-amber-600 bg-amber-50 dark:bg-amber-500/10 px-2.5 py-1 rounded-md border border-amber-200 dark:border-amber-500/20">
                            Warning: Overall target is less than sum of category targets.
                          </span>
                        )}
                      </div>
                      <div className="space-y-6">
                        {s.categories.map((c: any) => (
                          <TargetBar key={c.id} label={c.name} completed={c.completed} planned={c.planned} unplanned={c.unplanned} goal={c.target_goal} isHero={false} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

            </div>
          ))}
        </div>

      </div>
    </div>
  );
}