import React from 'react';
import { ExternalLink, Activity, LayoutDashboard } from 'lucide-react';

export default function ControlPanelHome() {
  // Define your external links and dashboards here. 
  // It is easy to add more to this array later!
  const dashboardLinks = [
    {
      title: "Snitcher Dashboard",
      description: "View the weekly actions, ticket movements, and user KPIs in a flow-diagram view.",
      href: "/snitcher-dashboard",
      icon: Activity,
      color: "text-purple-500",
      bg: "bg-purple-100 dark:bg-purple-500/10"
    }
    // Add future links here like:
    // { title: "Compliance Hub", description: "...", href: "/compliance", icon: Shield, ... }
  ];

  return (
    <div className="max-w-6xl space-y-8">
      
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
          <LayoutDashboard className="text-slate-500 dark:text-zinc-400" size={24} />
          Control Panel Hub
        </h1>
        <p className="text-slate-500 dark:text-zinc-400 mt-1">
          Manage system configurations or launch independent reporting dashboards.
        </p>
      </div>

      {/* Grid of Launch Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {dashboardLinks.map(function (link, index) {
          const Icon = link.icon;
          return (
            <a
              key={index}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              className="group block p-6 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-sm hover:shadow-md transition-all duration-200 hover:border-slate-300 dark:hover:border-zinc-700 relative overflow-hidden"
            >
              {/* Card Content */}
              <div className="relative z-10 flex flex-col h-full">
                <div className="flex items-start justify-between mb-4">
                  <div className={`p-3 rounded-xl ${link.bg}`}>
                    <Icon className={link.color} size={24} />
                  </div>
                  <ExternalLink size={20} className="text-slate-400 group-hover:text-slate-600 dark:group-hover:text-zinc-300 transition-colors" />
                </div>
                
                <h3 className="text-lg font-semibold text-slate-900 dark:text-zinc-100 mb-2">
                  {link.title}
                </h3>
                
                <p className="text-sm text-slate-500 dark:text-zinc-400 flex-grow">
                  {link.description}
                </p>
              </div>

              {/* Decorative background hover effect */}
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-transparent to-slate-100 dark:to-zinc-800/50 rounded-bl-full -z-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            </a>
          );
        })}
      </div>

    </div>
  );
}