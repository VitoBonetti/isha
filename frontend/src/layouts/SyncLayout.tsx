import React from 'react';
import { Outlet, NavLink, Navigate, useLocation } from 'react-router-dom';
import TopNav from '../components/TopNav';
import { ShieldCheck, CloudSync, Unplug, Blocks, LayoutDashboard, Metronome } from 'lucide-react';
import { useAppContext } from '../context/AppContext';


export default function SyncLayout() {
  const location = useLocation();
  const { currentUser } = useAppContext();

  let navItems: any[] = [];

   if (currentUser?.role === 'admin') {
    navItems = [
      { path: "/sync", label: "Sync Dashboard", icon: LayoutDashboard, exact: true },
      { path: "/sync/kiss24", label: "Keep Secure 24", icon: ShieldCheck },
      { path: "/sync/servicenow", label: "SNow Manual Sync", icon: CloudSync },
      { path: "/sync/asset-reconciliation", label: "Asset Reconciliation", icon: Unplug },
      { path: "/sync/test-reconciliation", label: "Test Reconciliation", icon: Blocks },
      { path: "/sync/scheduled-tasks", label: "Scheduled Tasks", icon: Metronome },
    ];
  } else {
    navItems = [
      { path: "/sync", label: "Sync Dashboard", icon: LayoutDashboard, exact: true },
    ];
  }

  const getNavLinkClass = (isActive: boolean) => {
    const baseClass = "flex items-center gap-3 px-4 py-2.5 rounded-xl font-medium text-sm whitespace-nowrap transition-colors";
    if (isActive) {
      return `${baseClass} bg-slate-200 dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 border border-slate-300 dark:border-zinc-700 shadow-sm`;
    }
    return `${baseClass} text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 hover:bg-slate-100 dark:hover:bg-zinc-800/50`;
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100">
      <TopNav />

      {/* MOBILE: Horizontally Scrollable Pills */}
      <div className="pt-32 md:pt-36 pb-12 px-4 md:px-6 w-full max-w-[1600px] mx-auto flex flex-col md:flex-row gap-6">
        <div className="md:hidden flex overflow-x-auto gap-2 pb-2 -mx-4 px-4 [&::-webkit-scrollbar]:hidden">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              className={({ isActive }) => getNavLinkClass(isActive)}
            >
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
              className={({ isActive }) => getNavLinkClass(isActive)}
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </div>
        <div className="flex-1 w-full min-w-0">
          <Outlet />
        </div>

      </div>
    </div>
  );
}