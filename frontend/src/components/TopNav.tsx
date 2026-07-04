import { useState, useRef, useEffect } from 'react';
import { Link, useLocation } from "react-router-dom";
import { useAppContext } from '../context/AppContext';
import { useTheme } from './ThemeProvider';
import {
  Sun, Moon, Laptop, LogOut, User as UserIcon, Bell,
  SprayCan, Snail, SunMoon, Fingerprint, Rabbit, Cat, Shell, Turtle, Radar, HandMetal, Drum, TentTree,
  Wifi, WifiOff, Loader2, ChevronDown
} from 'lucide-react';

export default function TopNav() {
  const { currentUser, handleLogout, notifications, showNotifications, setShowNotifications, markNotificationsRead, wsStatus } = useAppContext();
  const { setTheme } = useTheme();
  const location = useLocation();
  const currentPath = location.pathname;

  const [isThemeOpen, setIsThemeOpen] = useState(false);
  const [isUserOpen, setIsUserOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const themeRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);

  // Rotating Logo Icons Logic
  const logoIcons = [SprayCan, Snail, SunMoon, Fingerprint, Rabbit, Cat, Shell, Turtle, Radar, HandMetal, Drum, TentTree];
  const ICON_ROTATION_TIME = 1000 * 60 * 5;
  const iconIndex = Math.floor(Date.now() / ICON_ROTATION_TIME) % logoIcons.length;
  const LogoIcon = logoIcons[iconIndex];

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (themeRef.current && !themeRef.current.contains(event.target as Node)) setIsThemeOpen(false);
      if (userRef.current && !userRef.current.contains(event.target as Node)) setIsUserOpen(false);
      if (settingsRef.current && !settingsRef.current.contains(event.target as Node)) setIsSettingsOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const navClass = (path: string) => {
    const isActive = currentPath === path;
    return isActive
      ? "text-slate-900 dark:text-zinc-100 px-4 py-1.5 rounded-full bg-slate-200/50 dark:bg-zinc-800/50 border border-slate-300/50 dark:border-zinc-700/50"
      : "text-slate-500 dark:text-zinc-400 px-4 py-1.5 rounded-full border border-transparent hover:text-slate-900 dark:hover:text-zinc-100 transition-colors";
  };

  const unreadCount = notifications?.length || 0;

  return (
    <nav className="fixed top-6 left-1/2 -translate-x-1/2 z-50 flex items-center justify-between w-[95%] max-w-5xl px-6 py-3 bg-white/70 dark:bg-zinc-950/60 backdrop-blur-xl border border-slate-200 dark:border-zinc-800/80 rounded-full shadow-xl dark:shadow-2xl transition-colors">

      {/* Logo */}
      <Link to="/dashboard" className="flex items-center gap-3 cursor-pointer group">
        <div className="bg-emerald-500/10 p-2 rounded-full border border-emerald-500/20 group-hover:bg-emerald-500/20 transition-colors">
          <LogoIcon className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
        </div>
        <span className="font-bold tracking-widest text-sm text-slate-900 dark:text-zinc-100 uppercase">Isha</span>
      </Link>

      {/* Nav Links */}
      <div className="hidden md:flex items-center gap-2 text-sm font-medium">
        <Link to="/planner" className={navClass("/planner")}>Planner</Link>
        <Link to="/calendar" className={navClass("/calendar")}>Holidays</Link>
        <Link to="/tests" className={navClass("/tests")}>Tests</Link>

        {currentUser?.role === 'admin' && (
          <div className="relative" ref={settingsRef}>
            <button
              onClick={() => setIsSettingsOpen(!isSettingsOpen)}
              className={`flex items-center gap-1.5 ${['/settings', '/raw', '/assets', '/countries', '/insights'].some(p => currentPath.startsWith(p)) ? "text-slate-900 dark:text-zinc-100 px-4 py-1.5 rounded-full bg-slate-200/50 dark:bg-zinc-800/50 border border-slate-300/50 dark:border-zinc-700/50" : "text-slate-500 dark:text-zinc-400 px-4 py-1.5 rounded-full border border-transparent hover:text-slate-900 dark:hover:text-zinc-100 transition-colors"}`}
            >
              Settings <ChevronDown size={14} className={`transition-transform ${isSettingsOpen ? 'rotate-180' : ''}`} />
            </button>

            {isSettingsOpen && (
              <div className="absolute left-0 top-full mt-2 w-48 bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl py-2 animate-in fade-in zoom-in-95 overflow-hidden">
                <Link to="/countries" onClick={() => setIsSettingsOpen(false)} className="block px-4 py-2 text-sm font-medium text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">Countries</Link>
                <Link to="/raw" onClick={() => setIsSettingsOpen(false)} className="block px-4 py-2 text-sm font-medium text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">Raw Data Lab</Link>
                <Link to="/assets" onClick={() => setIsSettingsOpen(false)} className="block px-4 py-2 text-sm font-medium text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">Active Pool</Link>
                <Link to="/insights" onClick={() => setIsSettingsOpen(false)} className="block px-4 py-2 text-sm font-medium text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">Insights</Link>
                <div className="h-px bg-slate-100 dark:bg-zinc-800 my-1"></div>
                <Link to="/settings" onClick={() => setIsSettingsOpen(false)} className="block px-4 py-2 text-sm font-bold text-slate-900 dark:text-zinc-100 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">System Settings</Link>
              </div>
            )}
          </div>
        )}
      </div>

      {/* User Actions */}
      <div className="flex items-center gap-4">

        {/* Live Sync WebSocket Status */}
        <div className="relative group flex items-center justify-center cursor-help">
          {wsStatus === 'connected' ? (
            <Wifi className="h-4 w-4 text-emerald-500" />
          ) : wsStatus === 'connecting' ? (
            <Loader2 className="h-4 w-4 text-amber-500 animate-spin" />
          ) : (
            <WifiOff className="h-4 w-4 text-red-500 animate-pulse" />
          )}

          {/* Tooltip */}
          <div className="absolute top-full mt-3 left-1/2 -translate-x-1/2 px-2.5 py-1 bg-slate-900 dark:bg-zinc-100 text-white dark:text-slate-900 text-[10px] font-bold uppercase tracking-wider rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none shadow-lg">
            Live Sync: {wsStatus}
          </div>
        </div>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors relative flex items-center"
          >
            <Bell className="h-4 w-4" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.8)] border-2 border-white dark:border-zinc-950"></span>
            )}
          </button>

          {showNotifications && (
            <div className="absolute right-0 top-full mt-4 w-80 bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl overflow-hidden animate-in fade-in slide-in-from-top-2">
              <div className="bg-slate-50 dark:bg-zinc-900/50 p-4 border-b border-slate-200 dark:border-zinc-800 flex justify-between items-center">
                <h3 className="font-semibold text-sm">Inbox</h3>
                {unreadCount > 0 && (
                  <button onClick={markNotificationsRead} className="text-xs text-blue-500 hover:text-blue-600 font-medium">Mark all read</button>
                )}
              </div>
              <div className="max-h-80 overflow-y-auto">
                {unreadCount === 0 ? (
                  <div className="p-8 text-center text-slate-500 text-sm">You're all caught up! 🎉</div>
                ) : (
                  notifications.map((n: any) => (
                    <div key={n.id} className={`p-4 border-b border-slate-100 dark:border-zinc-800 flex gap-3 ${n.type === 'REMOVAL' ? 'bg-red-50/50 dark:bg-red-950/20' : ''}`}>
                      <div className="text-lg">{n.type === 'REMOVAL' ? '🛑' : '✅'}</div>
                      <div>
                        <p className="text-sm font-medium mb-1">{n.message}</p>
                        <span className="text-xs text-slate-400">{new Date(n.created_at).toLocaleString()}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Theme Toggle */}
        <div className="relative" ref={themeRef}>
          <button
            onClick={() => setIsThemeOpen(!isThemeOpen)}
            className="relative w-8 h-8 flex items-center justify-center rounded-full text-slate-500 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
          >
            <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
            <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
          </button>

          {isThemeOpen && (
            <div className="absolute right-0 top-full mt-2 w-32 bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg shadow-lg py-1 animate-in fade-in zoom-in-95 overflow-hidden">
              <button onClick={() => {setTheme("light"); setIsThemeOpen(false)}} className="w-full flex items-center px-3 py-2 text-sm hover:bg-slate-100 dark:hover:bg-zinc-800"><Sun className="mr-2 h-4 w-4" /> Light</button>
              <button onClick={() => {setTheme("dark"); setIsThemeOpen(false)}} className="w-full flex items-center px-3 py-2 text-sm hover:bg-slate-100 dark:hover:bg-zinc-800"><Moon className="mr-2 h-4 w-4" /> Dark</button>
              <button onClick={() => {setTheme("system"); setIsThemeOpen(false)}} className="w-full flex items-center px-3 py-2 text-sm hover:bg-slate-100 dark:hover:bg-zinc-800"><Laptop className="mr-2 h-4 w-4" /> System</button>
            </div>
          )}
        </div>

        {/* User Profile */}
        <div className="relative" ref={userRef}>
          <button onClick={() => setIsUserOpen(!isUserOpen)} className="ml-2 relative cursor-pointer hover:opacity-80 transition-opacity outline-none">
            {currentUser?.avatar_url ? (
              <img src={currentUser.avatar_url} alt="Profile" className="h-8 w-8 rounded-full border border-slate-300 dark:border-zinc-700 ring-2 ring-white dark:ring-zinc-900 object-cover" />
            ) : (
              <div className="h-8 w-8 rounded-full bg-gradient-to-tr from-emerald-500 to-indigo-500 border border-slate-300 dark:border-zinc-800 ring-2 ring-white dark:ring-zinc-900 flex items-center justify-center text-white">
                <UserIcon className="h-4 w-4" />
              </div>
            )}
          </button>

          {isUserOpen && (
            <div className="absolute right-0 top-full mt-2 w-56 bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl py-2 animate-in fade-in zoom-in-95 overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-200 dark:border-zinc-800 mb-2">
                <p className="text-sm font-semibold text-slate-900 dark:text-zinc-100">{currentUser?.name || 'User'}</p>
                <p className="text-xs text-slate-500 dark:text-zinc-400 truncate">{currentUser?.email}</p>
                <span className="inline-flex w-fit items-center mt-2 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-emerald-100 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400">
                  {currentUser?.role}
                </span>
              </div>
              <button onClick={handleLogout} className="w-full flex items-center px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors">
                <LogOut className="mr-2 h-4 w-4" /> Log out
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}