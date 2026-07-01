import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import TopNav from '../components/TopNav';
import {
  CalendarDays, Palmtree, Globe, Database,
  Server, ShieldAlert, LineChart, Settings, ChevronRight
} from 'lucide-react';

interface Feature {
  title: string;
  desc: string;
  icon: React.ReactNode;
  view: string;
  color: string;
  allowedRoles: string[];
}

export default function Dashboard() {
  const { currentUser, isLoading } = useAppContext();
  const navigate = useNavigate();
  const role = currentUser?.role || 'read_only';

  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    "Operations & Planning": true,
    "Asset Management": true,
    "System Data": true
  });

  const toggleSection = (sectionName: string) => {
    setExpandedSections(prev => ({ ...prev, [sectionName]: !prev[sectionName] }));
  };

  const clusters = [
    {
      name: "Operations & Planning",
      features: [
        { title: 'Planner', desc: 'Manage and schedule active pentest assignments across the team.', icon: <CalendarDays size={24} />, view: 'planner', color: 'text-blue-500', allowedRoles: ['admin', 'pentester', 'read_only'] },
        { title: 'Holidays', desc: 'Visual timeline of personal time off and national holidays.', icon: <Palmtree size={24} />, view: 'calendar', color: 'text-purple-500', allowedRoles: ['admin', 'pentester', 'read_only'] },
        { title: 'Tests', desc: 'Manage generated tests and lifecycle milestones.', icon: <ShieldAlert size={24} />, view: 'tests', color: 'text-indigo-500', allowedRoles: ['admin', 'pentester', 'read_only'] }
      ]
    },
    {
      name: "Asset Management",
      features: [
        { title: 'Countries', desc: 'Regional market logic and aggregated analytics.', icon: <Globe size={24} />, view: 'countries', color: 'text-emerald-600', allowedRoles: ['admin', 'read_only'] },
        { title: 'Raw Data Lab', desc: 'Data staging, sheet importation, and asset promotion pipeline.', icon: <Database size={24} />, view: 'raw', color: 'text-slate-600 dark:text-slate-400', allowedRoles: ['admin', 'read_only'] },
        { title: 'Active Pool', desc: 'Centralized inventory of applications prioritized for testing.', icon: <Server size={24} />, view: 'assets', color: 'text-emerald-500', allowedRoles: ['admin', 'read_only'] },
      ]
    },
    {
      name: "System Data",
      features: [
        { title: 'Insights', desc: 'Analyze throughput, workload distribution, and goal tracking.', icon: <LineChart size={24} />, view: 'insights', color: 'text-amber-500', allowedRoles: ['admin', 'read_only'] },
        { title: 'Settings', desc: 'Manage user accounts, roles, capacities, and global platform logic.', icon: <Settings size={24} />, view: 'settings', color: 'text-red-500', allowedRoles: ['admin'] }
      ]
    }
  ];

  if (isLoading) return null;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#09090b] text-slate-900 dark:text-zinc-100 flex flex-col relative overflow-hidden transition-colors duration-300">
      <TopNav />

      <main className="flex-1 pt-36 pb-12 px-6 md:px-12 relative z-10">
        <div className="max-w-5xl mx-auto">

          <div className="mb-12">
            <h1 className="text-3xl font-extrabold tracking-tight">
              Welcome back, {currentUser?.name?.split(' ')[0] || 'User'}
            </h1>
            <p className="text-slate-500 dark:text-zinc-400 mt-2 text-lg">
              Select a module below to continue your work.
            </p>
          </div>

          <div className="flex flex-col gap-8">
            {clusters.map((cluster) => {
              const visibleFeatures = cluster.features.filter(f => f.allowedRoles.includes(role));
              if (visibleFeatures.length === 0) return null;

              const isExpanded = expandedSections[cluster.name];

              return (
                <div key={cluster.name}>
                  <div
                    onClick={() => toggleSection(cluster.name)}
                    className="flex items-center gap-4 cursor-pointer group mb-6 select-none"
                  >
                    <h2 className="text-sm font-bold uppercase tracking-widest text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                      <ChevronRight size={16} className={`text-blue-500 transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`} />
                      {cluster.name}
                    </h2>
                    <div className="flex-1 h-px bg-slate-200 dark:bg-zinc-800 transition-colors group-hover:bg-slate-300 dark:group-hover:bg-zinc-700" />
                  </div>

                  <div className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 transition-all duration-300 origin-top ${isExpanded ? 'opacity-100 scale-y-100 h-auto' : 'opacity-0 scale-y-0 h-0 overflow-hidden'}`}>
                    {visibleFeatures.map((feature) => (
                      <div
                        key={feature.title}
                        onClick={() => navigate(`/${feature.view}`)}
                        className="group flex flex-col bg-white dark:bg-zinc-900 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all cursor-pointer"
                      >
                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 bg-slate-50 dark:bg-zinc-950 border border-slate-100 dark:border-zinc-800 group-hover:scale-110 transition-transform ${feature.color}`}>
                          {feature.icon}
                        </div>
                        <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
                        <p className="text-slate-500 dark:text-zinc-400 text-sm leading-relaxed">
                          {feature.desc}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}