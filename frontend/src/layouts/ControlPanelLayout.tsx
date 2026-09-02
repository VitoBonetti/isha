import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import TopNav from '../components/TopNav';
import {
  Users, MapPin, LayoutTemplate, Activity, Tags, Globe, Flag, KeySquare,
  Server, BookUser, ShieldCheck, CloudSync, AlertTriangle, LayoutDashboard, GitMerge, Filter
} from 'lucide-react';;

export default function ControlPanelLayout() {
  const navItems = [
    { path: "/settings", label: "Dashboard", icon: LayoutDashboard, exact: true },
    { path: "/settings/users", label: "Users", icon: Users },
    { path: "/settings/locations", label: "Locations", icon: MapPin },
    { path: "/settings/asset-types", label: "Asset Types", icon: LayoutTemplate },
    { path: "/settings/asset-criteria", label: "KPI Criteria", icon: Filter },
    { path: "/settings/services", label: "Services", icon: Activity },
    { path: "/settings/categories", label: "Categories", icon: Tags },
    { path: "/settings/regions", label: "Regions", icon: Globe },
    { path: "/settings/countries", label: "Countries", icon: Flag },
    { path: "/settings/contacts", label: "Contacts", icon: BookUser },
    { path: "/settings/kiss24", label: "Kiss 24 Sync", icon: ShieldCheck },
    { path: "/settings/servicenow", label: "ServiceNow Sync", icon: CloudSync },
    { path: "/settings/reconciliation", label: "Asset Reconciliation", icon: GitMerge },
    { path: "/settings/api-keys", label: "API Keys", icon: KeySquare },
    { path: "/settings/logs", label: "System Logs", icon: Server },
    { path: "/settings/danger", label: "Danger Zone", icon: AlertTriangle, isDanger: true },
  ];

  const getNavLinkClass = (isActive: boolean, isDanger?: boolean) => {
    const baseClass = "flex items-center gap-3 px-4 py-2.5 rounded-xl font-medium text-sm whitespace-nowrap transition-colors";

    if (isActive) {
      return isDanger
        ? `${baseClass} bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800/50`
        : `${baseClass} bg-slate-200 dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 border border-slate-300 dark:border-zinc-700 shadow-sm`;
    }

    return isDanger
      ? `${baseClass} text-red-500/70 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/20`
      : `${baseClass} text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 hover:bg-slate-100 dark:hover:bg-zinc-800/50`;
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100">
      <TopNav />

      <div className="pt-32 md:pt-36 pb-12 px-4 md:px-6 w-full max-w-[1600px] mx-auto flex flex-col md:flex-row gap-6">

        {/* MOBILE: Horizontally Scrollable Pills */}
        <div className="md:hidden flex overflow-x-auto gap-2 pb-2 -mx-4 px-4 [&::-webkit-scrollbar]:hidden">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              className={({ isActive }) => getNavLinkClass(isActive, item.isDanger)}
            >
              <item.icon size={16} />
              {item.label}
            </NavLink>
          ))}
        </div>

        {/* DESKTOP: Persistent Left Sidebar */}
        <div className="hidden md:flex flex-col gap-1 w-64 shrink-0 border-r border-slate-200 dark:border-zinc-800 pr-6 overflow-y-auto max-h-[calc(100vh-9rem)] sticky top-36 [&::-webkit-scrollbar]:hidden">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              className={({ isActive }) => getNavLinkClass(isActive, item.isDanger)}
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </div>

        {/* MAIN CONTENT AREA: Rendered dynamically via React Router Outlet */}
        <div className="flex-1 w-full min-w-0">
          <Outlet />
        </div>

      </div>
    </div>
  );
}