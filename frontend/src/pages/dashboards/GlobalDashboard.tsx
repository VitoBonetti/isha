import { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  ShieldAlert, AlertTriangle, CheckCircle2, Clock, 
  Filter, Building2, RefreshCw, Lock
} from 'lucide-react';
import { 
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, Legend 
} from 'recharts';
import { useAppContext } from '../../context/AppContext';

const SEVERITY_COLORS = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#3b82f6',
  info: '#6b7280'
};

export default function GlobalDashboard() {
  const { currentUser, handleLogout } = useAppContext();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  
  // Filters
  const [selectedOpCo, setSelectedOpCo] = useState('ALL');
  const [selectedSeverity, setSelectedSeverity] = useState('ALL');
  const [selectedState, setSelectedState] = useState('ALL');

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const res = await axios.get('/api-global-dash/vulnerabilities', {
        params: {
          opco: selectedOpCo,
          severity: selectedSeverity,
          state: selectedState
        }
      });
      setData(res.data);
    } catch (err) {
      console.error("Failed to load dashboard data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, [selectedOpCo, selectedSeverity, selectedState]);

  if (loading && !data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 text-white">
        <RefreshCw className="animate-spin h-8 w-8 text-blue-500" />
      </div>
    );
  }

  const summary = data?.summary || {};
  
  const severityChartData = [
    { name: 'Critical', value: summary.critical || 0, fill: SEVERITY_COLORS.critical },
    { name: 'High', value: summary.high || 0, fill: SEVERITY_COLORS.high },
    { name: 'Medium', value: summary.medium || 0, fill: SEVERITY_COLORS.medium },
    { name: 'Low', value: summary.low || 0, fill: SEVERITY_COLORS.low },
    { name: 'Info', value: summary.info || 0, fill: SEVERITY_COLORS.info },
  ];

  const stateChartData = [
    { name: 'Open / New', count: summary.open || 0 },
    { name: 'Validating', count: summary.validating || 0 },
    { name: 'Parked', count: summary.parked || 0 },
    { name: 'Closed', count: summary.closed || 0 },
  ];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 p-6 space-y-6">
      {/* HEADER */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white dark:bg-zinc-900 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ShieldAlert className="text-blue-500" /> Executive Vulnerability Dashboard
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1">
            Logged in as <span className="font-semibold text-slate-700 dark:text-zinc-200">{currentUser?.email}</span> ({currentUser?.role})
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button 
            onClick={fetchDashboardData} 
            className="p-2.5 rounded-xl border border-slate-200 dark:border-zinc-800 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
            title="Refresh Data"
          >
            <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
          </button>
          <button 
            onClick={handleLogout} 
            className="flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-red-600 bg-red-50 dark:bg-red-950/40 rounded-xl hover:bg-red-100 dark:hover:bg-red-900/60 transition-colors"
          >
            <Lock size={16} /> Logout
          </button>
        </div>
      </div>

      {/* FILTER BAR */}
      <div className="flex flex-wrap items-center gap-4 bg-white dark:bg-zinc-900 p-4 rounded-xl border border-slate-200 dark:border-zinc-800">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-500 dark:text-zinc-400 mr-2">
          <Filter size={16} /> Filters:
        </div>

        {/* OpCo Selector */}
        {data?.available_opcos?.length > 1 && (
          <div className="flex items-center gap-2">
            <Building2 size={16} className="text-slate-400" />
            <select 
              value={selectedOpCo} 
              onChange={(e) => setSelectedOpCo(e.target.value)}
              className="bg-slate-100 dark:bg-zinc-800 border-none text-sm font-medium rounded-lg px-3 py-2"
            >
              <option value="ALL">All Authorized OpCos</option>
              {data.available_opcos.map((opco: string) => (
                <option key={opco} value={opco}>{opco}</option>
              ))}
            </select>
          </div>
        )}

        {/* Severity Selector */}
        <select 
          value={selectedSeverity} 
          onChange={(e) => setSelectedSeverity(e.target.value)}
          className="bg-slate-100 dark:bg-zinc-800 border-none text-sm font-medium rounded-lg px-3 py-2"
        >
          <option value="ALL">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>

        {/* State Selector */}
        <select 
          value={selectedState} 
          onChange={(e) => setSelectedState(e.target.value)}
          className="bg-slate-100 dark:bg-zinc-800 border-none text-sm font-medium rounded-lg px-3 py-2"
        >
          <option value="ALL">All States</option>
          <option value="open">Open / New</option>
          <option value="validating">Validating</option>
          <option value="parked">Parked</option>
          <option value="closed">Closed</option>
        </select>
      </div>

      {/* KPI METRIC CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-zinc-900 p-5 rounded-2xl border border-slate-200 dark:border-zinc-800">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Findings</p>
          <h3 className="text-3xl font-extrabold mt-2">{summary.total || 0}</h3>
        </div>

        <div className="bg-white dark:bg-zinc-900 p-5 rounded-2xl border border-slate-200 dark:border-zinc-800">
          <p className="text-xs font-bold text-red-500 uppercase tracking-wider flex items-center gap-1">
            <AlertTriangle size={14} /> Critical & High
          </p>
          <h3 className="text-3xl font-extrabold text-red-600 dark:text-red-400 mt-2">
            {(summary.critical || 0) + (summary.high || 0)}
          </h3>
        </div>

        <div className="bg-white dark:bg-zinc-900 p-5 rounded-2xl border border-slate-200 dark:border-zinc-800">
          <p className="text-xs font-bold text-amber-500 uppercase tracking-wider flex items-center gap-1">
            <Clock size={14} /> Policy Overdue
          </p>
          <h3 className="text-3xl font-extrabold text-amber-600 dark:text-amber-400 mt-2">
            {summary.policy_overdue || 0}
          </h3>
        </div>

        <div className="bg-white dark:bg-zinc-900 p-5 rounded-2xl border border-slate-200 dark:border-zinc-800">
          <p className="text-xs font-bold text-emerald-500 uppercase tracking-wider flex items-center gap-1">
            <CheckCircle2 size={14} /> Resolved / Closed
          </p>
          <h3 className="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400 mt-2">
            {summary.closed || 0}
          </h3>
        </div>
      </div>

      {/* CHARTS SECTION */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Severity Distribution Donut */}
        <div className="bg-white dark:bg-zinc-900 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800">
          <h4 className="text-base font-bold mb-4">Severity Breakdown</h4>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={severityChartData} innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                  {severityChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* State Breakdown Bar Chart */}
        <div className="bg-white dark:bg-zinc-900 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800">
          <h4 className="text-base font-bold mb-4">Vulnerability Lifecycle States</h4>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stateChartData}>
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#3b82f6" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* PAGINATED DATA TABLE */}
      <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-slate-200 dark:border-zinc-800 overflow-hidden">
        <div className="p-4 border-b border-slate-200 dark:border-zinc-800 flex justify-between items-center">
          <h4 className="text-base font-bold">Vulnerability Details (Top {data?.items?.length || 0})</h4>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-zinc-800/50 text-slate-500 dark:text-zinc-400 font-semibold border-b border-slate-200 dark:border-zinc-800">
              <tr>
                <th className="p-3">Severity</th>
                <th className="p-3">OpCo</th>
                <th className="p-3">Asset Name</th>
                <th className="p-3">Description</th>
                <th className="p-3">State</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-zinc-800">
              {data?.items?.map((item: any, idx: number) => (
                <tr key={item.UUID || idx} className="hover:bg-slate-50/50 dark:hover:bg-zinc-800/30">
                  <td className="p-3">
                    <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-bold uppercase text-white ${
                      item.Severity?.toLowerCase() === 'critical' ? 'bg-red-600' :
                      item.Severity?.toLowerCase() === 'high' ? 'bg-orange-500' :
                      item.Severity?.toLowerCase() === 'medium' ? 'bg-yellow-500' : 'bg-blue-500'
                    }`}>
                      {item.Severity || 'Info'}
                    </span>
                  </td>
                  <td className="p-3 font-semibold">{item.OpCo}</td>
                  <td className="p-3 font-medium">{item.Asset_Name || 'N/A'}</td>
                  <td className="p-3 max-w-md truncate">{item.Description}</td>
                  <td className="p-3 font-semibold text-slate-600 dark:text-zinc-300">{item.State}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}