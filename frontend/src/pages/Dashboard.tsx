import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import TopNav from '../components/TopNav';
import {
  CalendarDays, Palmtree, ChartNoAxesCombined, Database,
  Server, ShieldAlert, LineChart, Settings, ChevronRight, Users, CheckSquare
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
        { title: 'Tests', desc: 'Manage generated tests and lifecycle milestones.', icon: <ShieldAlert size={24} />, view: 'tests', color: 'text-indigo-500', allowedRoles: ['admin', 'pentester', 'read_only'] },
        { title: 'Validation', desc: 'Live reconciliation of Keep Secure 24 vulnerabilities pending retest.', icon: <CheckSquare size={24} />, view: 'validating', color: 'text-rose-500', allowedRoles: ['admin', 'pentester', 'read_only'] }
      ]
    },
    {
      name: "Asset Management",
      features: [
        { title: 'Raw Data Lab', desc: 'Data staging, sheet importation, and asset promotion pipeline.', icon: <Database size={24} />, view: 'raw', color: 'text-slate-600 dark:text-slate-400', allowedRoles: ['admin'] },
        { title: 'Active Pool', desc: 'Centralized inventory of applications prioritized for testing.', icon: <Server size={24} />, view: 'assets', color: 'text-emerald-500', allowedRoles: ['admin', 'read_only'] },
        { title: 'Contacts', desc: 'Manage stakeholders and developers across all countries and assets.', icon: <Users size={24} />, view: 'contacts', color: 'text-blue-500', allowedRoles: ['admin'] }
      ]
    },
    {
      name: "System Data",
      features: [
        { title: 'Analytics', desc: 'Regional/country logic and aggregated analytics.', icon: <ChartNoAxesCombined size={24} />, view: 'countries', color: 'text-emerald-600', allowedRoles: ['admin', 'read_only'] },
        { title: 'Insights', desc: 'Analyze throughput, workload distribution, and goal tracking.', icon: <LineChart size={24} />, view: 'insights', color: 'text-amber-500', allowedRoles: ['admin', 'read_only'] },
        { title: 'System', desc: 'Manage user accounts, roles, capacities, and global platform logic.', icon: <Settings size={24} />, view: 'settings', color: 'text-red-500', allowedRoles: ['admin'] }
      ]
    }
  ];

  if (isLoading) return null;

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100 flex flex-col relative overflow-hidden transition-colors duration-300">
      <TopNav />

      <main className="flex-1 pt-28 md:pt-36 pb-12 px-4 md:px-8 relative z-10">
        <div className="max-w-5xl mx-auto">

          <div className="mb-8 md:mb-12">
            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight">
              Welcome back, {currentUser?.name?.split(' ')[0] || 'User'}
            </h1>
            <p className="text-slate-500 dark:text-zinc-400 mt-1.5 md:mt-2 text-base md:text-lg">
              Select a module below to continue your work.
            </p>
          </div>

          <div className="flex flex-col gap-6 md:gap-8">
            {clusters.map((cluster) => {
              const visibleFeatures = cluster.features.filter(f => f.allowedRoles.includes(role));
              if (visibleFeatures.length === 0) return null;

              const isExpanded = expandedSections[cluster.name];

              return (
                <div key={cluster.name}>
                  <div
                    onClick={() => toggleSection(cluster.name)}
                    className="flex items-center gap-3 md:gap-4 cursor-pointer group mb-4 md:mb-6 select-none"
                  >
                    <h2 className="text-xs md:text-sm font-bold uppercase tracking-widest text-slate-900 dark:text-zinc-100 flex items-center gap-1.5 md:gap-2">
                      <ChevronRight size={16} className={`text-blue-500 transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`} />
                      {cluster.name}
                    </h2>
                    <div className="flex-1 h-px bg-slate-200 dark:bg-zinc-800 transition-colors group-hover:bg-slate-300 dark:group-hover:bg-zinc-700" />
                  </div>

                  <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6 transition-all duration-300 origin-top ${isExpanded ? 'opacity-100 scale-y-100 h-auto' : 'opacity-0 scale-y-0 h-0 overflow-hidden'}`}>
                    {visibleFeatures.map((feature) => (
                      <div
                        key={feature.title}
                        onClick={() => navigate(`/${feature.view}`)}
                        className="group flex flex-col bg-white dark:bg-zinc-900 p-5 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all cursor-pointer"
                      >
                        <div className={`w-10 h-10 md:w-12 md:h-12 rounded-xl flex items-center justify-center mb-3 md:mb-4 bg-slate-50 dark:bg-zinc-950 border border-slate-100 dark:border-zinc-800 group-hover:scale-110 transition-transform ${feature.color}`}>
                          {feature.icon}
                        </div>
                        <h3 className="text-lg md:text-xl font-semibold mb-1.5 md:mb-2">{feature.title}</h3>
                        <p className="text-slate-500 dark:text-zinc-400 text-xs md:text-sm leading-relaxed">
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