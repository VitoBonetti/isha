import { useState, useEffect } from "react";
import axios from "axios";
import TopNav from "../components/TopNav";
import toast, { Toaster } from "react-hot-toast";
import { Database, CheckCircle, Activity, Layers, MapPin, Map, ChartNoAxesCombined, XCircle } from "lucide-react";
import { PieChart, Pie, Cell, ComposedChart, Bar, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#6366f1', '#ec4899', '#8b5cf6', '#14b8a6', '#f43f5e'];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    // We only grab the first payload item's value, ignoring the redundant Line/Area duplicates
    const testCount = payload[0].value;
    return (
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-3 rounded-xl shadow-lg">
        <p className="text-blue-600 dark:text-blue-400 font-black mb-1">{label}</p>
        <p className="text-slate-700 dark:text-zinc-300 font-bold text-sm">
          Tests: <span className="text-slate-900 dark:text-zinc-100">{testCount}</span>
        </p>
      </div>
    );
  }
  return null;
};

export default function AnalyticsDashboard() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Dropdown Data
  const [countries, setCountries] = useState<any[]>([]);
  const [regions, setRegions] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [availableYears, setAvailableYears] = useState<number[]>([new Date().getFullYear()]);

  // Filter States
  const [targetYear, setTargetYear] = useState(new Date().getFullYear());
  const [selectedRegion, setSelectedRegion] = useState("");
  const [selectedCountry, setSelectedCountry] = useState("");
  const [selectedService, setSelectedService] = useState("");

  // Chart Interaction State
  const [fillArea, setFillArea] = useState(false);

  useEffect(() => {
    axios.get('/api/countries/').then(res => setCountries(res.data)).catch(console.error);
    axios.get('/api/regions/').then(res => setRegions(res.data)).catch(console.error);
    axios.get('/api/services/').then(res => setServices(res.data)).catch(console.error);
    axios.get('/api/countries/available-years').then(res => setAvailableYears(res.data)).catch(console.error);
  }, []);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        setLoading(true);
        const params = new URLSearchParams({ year: targetYear.toString() });
        if (selectedCountry) params.set("country_id", selectedCountry);
        if (selectedRegion) params.set("region_id", selectedRegion);
        if (selectedService) params.set("service_lane_id", selectedService); // NEW

        const res = await axios.get(`/api/countries/dashboard?${params.toString()}`);
        setData(res.data);
      } catch (error) {
        toast.error("Failed to load dashboard analytics.");
      } finally {
        setLoading(false);
      }
    };
    fetchAnalytics();
  }, [targetYear, selectedRegion, selectedCountry, selectedService]);;

  // Dynamic Title Logic
  const countryName = countries.find(c => c.id === selectedCountry)?.name;
  const regionName = regions.find(r => r.id === selectedRegion)?.name;
  const pageTitle = countryName ? `${countryName} Analytics` : regionName ? `${regionName} Analytics` : "Worldwide Analytics";

  // Coverage Math
  const totalTestsYear = data?.kpis?.total_tests_year || 0;
  const completed = data?.kpis?.completed || 0;
  const planned = data?.kpis?.planned || 0;
  const trueBacklog = data?.kpis?.true_backlog || 0;

  // Bar Width Percentages
  const pctCompleted = totalTestsYear > 0 ? (completed / totalTestsYear) * 100 : 0;
  const pctPlanned = totalTestsYear > 0 ? (planned / totalTestsYear) * 100 : 0;
  const pctBacklog = totalTestsYear > 0 ? (trueBacklog / totalTestsYear) * 100 : 0;

  // Hero Coverage Metric
  const coveragePct = totalTestsYear > 0 ? Math.min(100, (completed / totalTestsYear) * 100) : 0;

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100 pb-12 bg-slate-50/50 dark:bg-[#09090b]">
      <TopNav />
      <Toaster position="bottom-right" />

      <div className="pt-28 md:pt-32 px-4 md:px-6 max-w-7xl mx-auto">

        {/* Header & Filters (Responsive) */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-6 md:mb-8 gap-4 w-full">
          <div className="w-full md:w-auto">
            <h1 className="text-2xl md:text-3xl font-black flex items-center gap-2 md:gap-3 tracking-tight">
              <ChartNoAxesCombined size={28} className="text-blue-600 md:w-8 md:h-8" />
              <span className="truncate">{pageTitle}</span>
            </h1>
            <p className="text-sm md:text-base text-slate-500 dark:text-zinc-400 mt-1 md:mt-2 font-medium">Aggregated asset volume and pentest coverage.</p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-3 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-2 rounded-xl shadow-sm w-full md:w-auto overflow-x-auto">

            <div className="flex items-center gap-2 border-b sm:border-b-0 sm:border-r border-slate-100 dark:border-zinc-800 pb-2 sm:pb-0 pr-0 sm:pr-3 shrink-0">
              <Layers size={16} className="text-slate-400 ml-2 shrink-0" />
              <select
                className="bg-transparent text-sm font-bold text-slate-700 dark:text-zinc-300 outline-none cursor-pointer w-full sm:w-auto appearance-none"
                value={selectedService}
                onChange={(e) => setSelectedService(e.target.value)}
              >
                <option value="">All Services</option>
                {services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>

            <div className="flex items-center gap-2 border-b sm:border-b-0 sm:border-r border-slate-100 dark:border-zinc-800 pb-2 sm:pb-0 pr-0 sm:pr-3 shrink-0">
              <Map size={16} className="text-slate-400 ml-2 shrink-0" />
              <select
                className="bg-transparent text-sm font-bold text-slate-700 dark:text-zinc-300 outline-none cursor-pointer w-full sm:w-auto appearance-none"
                value={selectedRegion}
                onChange={(e) => { setSelectedRegion(e.target.value); setSelectedCountry(""); }}
              >
                <option value="">All Regions</option>
                {regions.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>

            <div className="flex items-center gap-2 border-b sm:border-b-0 sm:border-r border-slate-100 dark:border-zinc-800 pb-2 sm:pb-0 pr-0 sm:pr-3 shrink-0">
              <MapPin size={16} className="text-slate-400 ml-2 shrink-0" />
              <select
                className="bg-transparent text-sm font-bold text-slate-700 dark:text-zinc-300 outline-none cursor-pointer w-full sm:w-32 truncate appearance-none"
                value={selectedCountry}
                onChange={(e) => { setSelectedCountry(e.target.value); setSelectedRegion(""); }}
              >
                <option value="">All Countries</option>
                {countries.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>

            <select
              className="bg-slate-100 dark:bg-zinc-800 border-none text-blue-600 dark:text-blue-400 font-black text-sm px-3 py-2 sm:py-1.5 rounded-lg outline-none cursor-pointer w-full sm:w-auto text-center shrink-0"
              value={targetYear}
              onChange={(e) => setTargetYear(parseInt(e.target.value))}
            >
              {availableYears.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        </div>

        {loading || !data ? (
          <div className="py-24 text-center text-slate-500 font-bold animate-pulse">Calculating analytics...</div>
        ) : (
          <>
            {/* Row 1: Global KPIs (2 columns on mobile, 5 on desktop) */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 md:gap-6 mb-6 md:mb-8">
              <div className="bg-white dark:bg-zinc-900 p-4 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm flex items-center gap-3 md:gap-4">
                <div className="p-2.5 md:p-3 bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 rounded-xl shrink-0"><Database size={20} className="md:w-6 md:h-6"/></div>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] md:text-xs text-slate-500 font-bold uppercase tracking-wider truncate">Total Raw</p>
                  <p className="text-xl md:text-2xl font-black truncate">{data.kpis.raw}</p>
                </div>
              </div>
              <div className="bg-white dark:bg-zinc-900 p-4 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm flex items-center gap-3 md:gap-4">
                <div className="p-2.5 md:p-3 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-xl border border-indigo-100 dark:border-indigo-500/20 shrink-0"><Layers size={20} className="md:w-6 md:h-6"/></div>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] md:text-xs text-slate-500 font-bold uppercase tracking-wider truncate">In Pool</p>
                  <p className="text-xl md:text-2xl font-black text-indigo-600 dark:text-indigo-400 truncate">{data.kpis.pool}</p>
                </div>
              </div>
              <div className="bg-white dark:bg-zinc-900 p-4 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm flex items-center gap-3 md:gap-4">
                <div className="p-2.5 md:p-3 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-xl border border-emerald-100 dark:border-emerald-500/20 shrink-0"><CheckCircle size={20} className="md:w-6 md:h-6"/></div>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] md:text-xs text-slate-500 font-bold uppercase tracking-wider truncate">Done ({targetYear})</p>
                  <p className="text-xl md:text-2xl font-black text-emerald-600 dark:text-emerald-400 truncate">{data.kpis.completed}</p>
                </div>
              </div>
              <div className="bg-white dark:bg-zinc-900 p-4 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm flex items-center gap-3 md:gap-4">
                <div className="p-2.5 md:p-3 bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 rounded-xl border border-amber-100 dark:border-amber-500/20 shrink-0"><Activity size={20} className="md:w-6 md:h-6"/></div>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] md:text-xs text-slate-500 font-bold uppercase tracking-wider truncate">Backlog</p>
                  <p className="text-xl md:text-2xl font-black text-amber-600 dark:text-amber-400 truncate">{data.kpis.backlog}</p>
                </div>
              </div>
              {/* Stopped Card - Spans 2 columns on mobile to keep grid clean */}
              <div className="col-span-2 md:col-span-1 bg-white dark:bg-zinc-900 p-4 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm flex items-center gap-3 md:gap-4">
                <div className="p-2.5 md:p-3 bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 rounded-xl border border-red-100 dark:border-red-500/20 shrink-0"><XCircle size={20} className="md:w-6 md:h-6"/></div>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] md:text-xs text-slate-500 font-bold uppercase tracking-wider truncate">Stopped</p>
                  <p className="text-xl md:text-2xl font-black text-red-600 dark:text-red-400 truncate">{data.kpis.stopped}</p>
                </div>
              </div>
            </div>

            {/* Row 2: Coverage Ratio */}
            <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm p-5 md:p-8 mb-6 md:mb-8">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-4 md:mb-6 gap-2 sm:gap-0">
                <div>
                  <h2 className="text-lg md:text-xl font-black text-slate-900 dark:text-zinc-100">Testing Coverage Ratio</h2>
                  <p className="text-xs md:text-sm text-slate-500 dark:text-zinc-400 mt-1">
                    Breakdown of the <strong className="text-slate-700 dark:text-zinc-300">{totalTestsYear} total tests</strong> tracked for {targetYear}.
                  </p>
                </div>
                <div className="text-3xl md:text-4xl font-black text-emerald-500 dark:text-emerald-400">
                  {coveragePct.toFixed(1)}% <span className="text-xs md:text-sm font-bold text-slate-400 tracking-normal block sm:inline">Completed</span>
                </div>
              </div>

              {/* Segment Progress Bar */}
              <div className="w-full bg-slate-100 dark:bg-zinc-950 rounded-full h-8 md:h-10 overflow-hidden flex border border-slate-200 dark:border-zinc-800 shadow-inner relative">
                <div
                  className="bg-emerald-500 h-full transition-all duration-1000 ease-out flex items-center justify-center text-xs md:text-sm font-bold text-white shadow-[inset_0_-2px_4px_rgba(0,0,0,0.2)]"
                  style={{ width: `${pctCompleted}%` }}
                  title={`${completed} Completed`}
                >
                  {/* Hide text on mobile to prevent overflow */}
                  <span className="hidden sm:inline">{pctCompleted > 5 && `${completed} Completed`}</span>
                </div>
                <div
                  className="bg-blue-500 h-full transition-all duration-1000 ease-out flex items-center justify-center text-xs md:text-sm font-bold text-white shadow-[inset_0_-2px_4px_rgba(0,0,0,0.2)] border-l border-white/20"
                  style={{ width: `${pctPlanned}%` }}
                  title={`${planned} Planned`}
                >
                  <span className="hidden sm:inline">{pctPlanned > 5 && `${planned} Planned`}</span>
                </div>
                <div
                  className="bg-amber-400 h-full transition-all duration-1000 ease-out flex items-center justify-center text-xs md:text-sm font-bold text-amber-900 shadow-[inset_0_-2px_4px_rgba(0,0,0,0.1)] border-l border-white/20"
                  style={{ width: `${pctBacklog}%` }}
                  title={`${trueBacklog} Backlog`}
                >
                  <span className="hidden sm:inline">{pctBacklog > 5 && `${trueBacklog} Backlog`}</span>
                </div>
              </div>

              {/* Status Legend */}
              <div className="flex flex-wrap items-center gap-3 sm:gap-6 mt-4 md:mt-5 pl-1 md:pl-2">
                <div className="flex items-center gap-1.5 md:gap-2">
                  <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-emerald-500 shadow-sm shrink-0"></div>
                  <span className="text-xs md:text-sm font-bold text-slate-700 dark:text-zinc-300">{completed} <span className="text-slate-500 dark:text-zinc-500 font-medium hidden sm:inline">Completed ({targetYear})</span></span>
                </div>
                <div className="flex items-center gap-1.5 md:gap-2">
                  <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-blue-500 shadow-sm shrink-0"></div>
                  <span className="text-xs md:text-sm font-bold text-slate-700 dark:text-zinc-300">{planned} <span className="text-slate-500 dark:text-zinc-500 font-medium hidden sm:inline">Planned ({targetYear})</span></span>
                </div>
                <div className="flex items-center gap-1.5 md:gap-2">
                  <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-amber-400 shadow-sm shrink-0"></div>
                  <span className="text-xs md:text-sm font-bold text-slate-700 dark:text-zinc-300">{trueBacklog} <span className="text-slate-500 dark:text-zinc-500 font-medium hidden sm:inline">Backlog (Unscheduled)</span></span>
                </div>
              </div>
            </div>

            {/* Row 3: Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

              {/* Pie Chart */}
              <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm p-4 md:p-6 flex flex-col items-center justify-center min-h-[350px] md:min-h-[400px]">
                <h3 className="text-sm md:text-base font-bold text-slate-900 dark:text-zinc-100 self-start w-full border-b border-slate-100 dark:border-zinc-800 pb-3 md:pb-4 mb-2 md:mb-4">Service Lane Distribution</h3>
                {data.pie_data.length === 0 ? (
                  <div className="text-slate-400 font-medium flex-1 flex items-center justify-center">No assets in pool.</div>
                ) : (
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie data={data.pie_data} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={4} dataKey="value" stroke="none">
                        {data.pie_data.map((entry: any, index: number) => (
                          <Cell key={`cell-${index}`} fill={entry.name === 'Not Set' ? '#94a3b8' : COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}
                        itemStyle={{ fontWeight: 'bold' }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                )}
                {/* Custom Legend */}
                <div className="flex flex-wrap justify-center gap-2 md:gap-3 mt-4 w-full">
                  {data.pie_data.map((entry: any, index: number) => (
                    <div key={entry.name} className="flex items-center gap-1 md:gap-1.5 text-[10px] md:text-xs font-medium text-slate-600 dark:text-zinc-400">
                      <div className="w-2 h-2 md:w-2.5 md:h-2.5 rounded-full shrink-0" style={{ backgroundColor: entry.name === 'Not Set' ? '#94a3b8' : COLORS[index % COLORS.length] }} />
                      <span className="truncate max-w-[100px]">{entry.name}</span> ({entry.value})
                    </div>
                  ))}
                </div>
              </div>

              {/* Combo Bar-Line Chart */}
              <div className="lg:col-span-2 bg-white dark:bg-zinc-900 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm p-4 md:p-6 flex flex-col min-h-[350px] md:min-h-[400px]">
                <div className="flex justify-between items-start border-b border-slate-100 dark:border-zinc-800 pb-3 md:pb-4 mb-4 md:mb-6">
                  <div>
                    <h3 className="text-sm md:text-base font-bold text-slate-900 dark:text-zinc-100">Monthly Testing Trends</h3>
                    <p className="text-[10px] md:text-xs text-slate-500 dark:text-zinc-400 mt-1">Test volume mapped by start week. Click chart to toggle fill.</p>
                  </div>
                </div>

                <div className="flex-1 w-full cursor-pointer min-h-[250px]" onClick={() => setFillArea(!fillArea)}>
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={data.trend_data} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.2} />
                      <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 10, fontWeight: 'bold'}} dy={10} />
                      <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 10, fontWeight: 'bold'}} />
                      <Tooltip
                        content={<CustomTooltip />}
                        cursor={{fill: 'rgba(59, 130, 246, 0.05)'}}
                        />
                      {fillArea && <Area type="monotone" dataKey="tests" name="Tests" fill="#3b82f6" stroke="none" fillOpacity={0.15} animationDuration={800} />}
                      <Bar dataKey="tests" name="Tests" barSize={24} fill="#3b82f6" radius={[4, 4, 0, 0]} animationDuration={1000} />
                      <Line type="monotone" dataKey="tests" name="Trend" stroke="#10b981" strokeWidth={2} dot={{r: 4, fill: '#10b981', strokeWidth: 2, stroke: '#fff'}} activeDot={{r: 6, fill: '#10b981', stroke: '#fff', strokeWidth: 2}} animationDuration={1200} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>

            </div>
          </>
        )}
      </div>
    </div>
  );
}