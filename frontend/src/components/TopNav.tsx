import { useState, useRef, useEffect } from 'react';
import { Link, useLocation } from "react-router-dom";
import toast from 'react-hot-toast';
import { useAppContext } from '../context/AppContext';
import { useTheme } from './ThemeProvider';
import ApiKeysModal from './Modals/ApiKeysModal';
import MeetingProposalsModal from './Modals/MeetingProposalsModal';
import Kiss24KeyModal from './Modals/Kiss24KeyModal';
import {
  Sun, Moon, Laptop, LogOut, User as UserIcon, Bell,
  SprayCan, Snail, SunMoon, Fingerprint, Rabbit, Cat, Shell, Turtle, Radar, HandMetal, Drum, TentTree,
  Wifi, WifiOff, Loader2, ChevronDown, Key, LockOpen, Lock, Menu, X, Feather, PawPrint, Origami
} from 'lucide-react';

export default function TopNav() {
  const { currentUser, handleLogout, notifications, showNotifications, setShowNotifications, markNotificationsRead, wsStatus, fetchNotifications } = useAppContext();
  const { setTheme } = useTheme();
  const location = useLocation();
  const currentPath = location.pathname;

  const [isThemeOpen, setIsThemeOpen] = useState(false);
  const [isUserOpen, setIsUserOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isApiModalOpen, setIsApiModalOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isKiss24KeyModalOpen, setIsKiss24KeyModalOpen] = useState(false);

  const themeRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);
  const notificationRef = useRef<HTMLDivElement>(null);
  const mobileMenuRef = useRef<HTMLDivElement>(null);

  const [meetingProposalData, setMeetingProposalData] = useState<any>(null);
  const [isMeetingModalOpen, setIsMeetingModalOpen] = useState(false);

  // Rotating Logo Icons Logic
  const logoIcons = [SprayCan, Snail, SunMoon, Fingerprint, Rabbit, Cat, Shell, Turtle, Radar, HandMetal, Drum, TentTree, Wifi, WifiOff, LockOpen, Lock, Feather, PawPrint, Origami];
  const ICON_ROTATION_TIME = 1000 * 60 * 5;
  const iconIndex = Math.floor(Date.now() / ICON_ROTATION_TIME) % logoIcons.length;
  const LogoIcon = logoIcons[iconIndex];

  useEffect(() => {
    // 1. Click Outside Logic
    const handleClickOutside = (event: MouseEvent) => {
      if (themeRef.current && !themeRef.current.contains(event.target as Node)) setIsThemeOpen(false);
      if (userRef.current && !userRef.current.contains(event.target as Node)) setIsUserOpen(false);
      if (settingsRef.current && !settingsRef.current.contains(event.target as Node)) setIsSettingsOpen(false);
      if (notificationRef.current && !notificationRef.current.contains(event.target as Node)) setShowNotifications(false);
      if (mobileMenuRef.current && !mobileMenuRef.current.contains(event.target as Node)) setIsMobileMenuOpen(false);
    };

    document.addEventListener('mousedown', handleClickOutside);

    // 2. Custom Event Listener
    const handleRefreshNotifications = () => {
      if (typeof fetchNotifications === 'function') {
        fetchNotifications();
      }
    };
    window.addEventListener('refresh_notifications', handleRefreshNotifications);

    // 3. GLOBAL WEBSOCKET FOR TOASTS & NOTIFICATIONS
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/board`;
    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Auto-refresh the notification bell for ANY board changes
        if (data.action === 'REFRESH_BOARD' || data.action === 'REPORT_READY') {
          handleRefreshNotifications();
          window.dispatchEvent(new Event('refresh_test_data'));
        }

        // Handle targeted success toasts (with clickable links!)
        if (['REPORT_READY', 'PRESENTATION_READY'].includes(data.action) && data.email === currentUser?.email) {
          toast.success(
            (t) => (
              <div className="flex flex-col gap-1">
                <span className="font-medium text-sm">{data.message}</span>
                {data.link && (
                  <Link to={data.link} onClick={() => toast.dismiss(t.id)} className="text-xs text-blue-600 dark:text-blue-400 font-bold hover:underline">
                    Click here to view
                  </Link>
                )}
              </div>
            ),
            { duration: 8000 }
          );
        }
        // --- Catch Meeting Proposals ---
        else if (data.action === 'MEETING_PROPOSALS_READY' && data.email === currentUser?.email) {
          toast.success("Luigi found available meeting slots!", { duration: 5000 });
          // INSTEAD OF DISPATCHING AN EVENT, WE JUST OPEN THE MODAL DIRECTLY!
          setMeetingProposalData(data);
          setIsMeetingModalOpen(true);
        }
        // Handle targeted error toasts
        else if (['REPORT_FAILED', 'PRESENTATION_FAILED'].includes(data.action) && data.email === currentUser?.email) {
          toast.error(data.message, { duration: 8000 });
        }
      } catch (e) { console.error(e); }
    };

    setIsMobileMenuOpen(false);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('refresh_notifications', handleRefreshNotifications);
      socket.close();
    };
  }, [fetchNotifications, location.pathname, currentUser?.email]);

  const navClass = (path: string) => {
    const isActive = currentPath === path;
    return isActive
      ? "text-slate-900 dark:text-zinc-100 px-4 py-1.5 rounded-full bg-slate-200/50 dark:bg-zinc-800/50 border border-slate-300/50 dark:border-zinc-700/50"
      : "text-slate-500 dark:text-zinc-400 px-4 py-1.5 rounded-full border border-transparent hover:text-slate-900 dark:hover:text-zinc-100 transition-colors";
  };

  const mobileNavClass = (path: string) => {
    const isActive = currentPath === path || (path !== '/' && currentPath.startsWith(path));
    return isActive
      ? "block px-4 py-3 rounded-xl bg-slate-100 dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 font-bold"
      : "block px-4 py-3 rounded-xl hover:bg-slate-50 dark:hover:bg-zinc-900 text-slate-600 dark:text-zinc-400 font-medium transition-colors";
  };

  const unreadCount = notifications?.length || 0;
  const userInitial = currentUser?.name ? currentUser.name.charAt(0).toUpperCase() : "";

  const renderMessageWithLinks = (text: string) => {
    if (!text) return null;
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = text.split(urlRegex);

    return parts.map((part, i) => {
      if (part.match(urlRegex)) {
        return (
          <a
            key={i}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-500 hover:text-blue-600 hover:underline font-bold"
            onClick={(e) => e.stopPropagation()}
          >
            {part}
          </a>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <>
    <nav className="fixed top-6 left-1/2 -translate-x-1/2 z-50 flex items-center justify-between w-[95%] max-w-5xl px-4 md:px-6 py-3 bg-white/70 dark:bg-zinc-950/60 backdrop-blur-xl border border-slate-200 dark:border-zinc-800/80 rounded-full shadow-xl dark:shadow-2xl transition-colors">

      {/* Left Section: Mobile Menu Toggle & Logo */}
      <div className="flex items-center gap-2 md:gap-3">
        <button
          className="md:hidden p-1.5 text-slate-500 hover:text-slate-900 dark:text-zinc-400 dark:hover:text-zinc-100 transition-colors"
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        >
          {isMobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>

        <Link to="/dashboard" className="flex items-center gap-2 md:gap-3 cursor-pointer group">
          <div className="bg-emerald-500/10 p-2 rounded-full border border-emerald-500/20 group-hover:bg-emerald-500/20 transition-colors">
            <LogoIcon className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          </div>
          <span className="hidden sm:inline font-bold tracking-widest text-sm text-slate-900 dark:text-zinc-100 uppercase">Mario</span>
        </Link>
      </div>

      {/* Desktop Nav Links (Hidden on mobile) */}
      <div className="hidden md:flex items-center gap-2 text-sm font-medium">
        <Link to="/planner" className={navClass("/planner")}>Planner</Link>
        <Link to="/calendar" className={navClass("/calendar")}>Holidays</Link>
        <Link to="/tests" className={navClass("/tests")}>Tests</Link>

        {currentUser?.role === 'admin' && (
          <div className="relative" ref={settingsRef}>
            <button
              onClick={() => setIsSettingsOpen(!isSettingsOpen)}
              className={`flex items-center gap-1.5 ${['/settings', '/raw', '/assets', '/countries', '/insights', '/contacts'].some(p => currentPath.startsWith(p)) ? "text-slate-900 dark:text-zinc-100 px-4 py-1.5 rounded-full bg-slate-200/50 dark:bg-zinc-800/50 border border-slate-300/50 dark:border-zinc-700/50" : "text-slate-500 dark:text-zinc-400 px-4 py-1.5 rounded-full border border-transparent hover:text-slate-900 dark:hover:text-zinc-100 transition-colors"}`}
            >
              Settings <ChevronDown size={14} className={`transition-transform ${isSettingsOpen ? 'rotate-180' : ''}`} />
            </button>

            {isSettingsOpen && (
              <div className="absolute left-0 top-full mt-2 w-48 bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl py-2 animate-in fade-in zoom-in-95 overflow-hidden">
                <Link to="/raw" onClick={() => setIsSettingsOpen(false)} className="block px-4 py-2 text-sm font-medium text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">Raw Data Lab</Link>
                <Link to="/assets" onClick={() => setIsSettingsOpen(false)} className="block px-4 py-2 text-sm font-medium text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">Active Pool</Link>
                <Link to="/contacts" onClick={() => setIsSettingsOpen(false)} className="block px-4 py-2 text-sm font-medium text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">Contacts</Link>
                <Link to="/countries" onClick={() => setIsSettingsOpen(false)} className="block px-4 py-2 text-sm font-medium text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">Analytics</Link>
                <Link to="/insights" onClick={() => setIsSettingsOpen(false)} className="block px-4 py-2 text-sm font-medium text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">Insights</Link>
                <div className="h-px bg-slate-100 dark:bg-zinc-800 my-1"></div>
                <Link to="/settings" onClick={() => setIsSettingsOpen(false)} className="block px-4 py-2 text-sm font-bold text-slate-900 dark:text-zinc-100 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">System Settings</Link>
              </div>
            )}
          </div>
        )}
      </div>

      {/* User Actions */}
      <div className="flex items-center gap-2 md:gap-4">

        {/* Live Sync WebSocket Status */}
        <div className="relative group flex items-center justify-center cursor-help">
          {wsStatus === 'connected' ? (
            <Wifi className="h-4 w-4 text-emerald-500" />
          ) : wsStatus === 'connecting' ? (
            <Loader2 className="h-4 w-4 text-amber-500 animate-spin" />
          ) : (
            <WifiOff className="h-4 w-4 text-red-500 animate-pulse" />
          )}

          <div className="absolute top-full mt-3 right-0 md:right-auto md:left-1/2 md:-translate-x-1/2 w-max px-2.5 py-1 bg-slate-900 dark:bg-zinc-100 text-white dark:text-slate-900 text-[10px] font-bold uppercase tracking-wider rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none shadow-lg z-50">
            Live Sync: {wsStatus}
          </div>
        </div>

        {/* Notifications */}
        <div className="relative" ref={notificationRef}>
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors relative flex items-center p-1"
          >
            <Bell className="h-4 w-4" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.8)] border-2 border-white dark:border-zinc-950"></span>
            )}
          </button>

          {showNotifications && (
            <div className="absolute right-0 md:-right-4 top-full mt-4 w-72 md:w-80 bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl overflow-hidden animate-in fade-in slide-in-from-top-2">
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
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium mb-1 whitespace-pre-wrap break-words leading-relaxed">
                          {renderMessageWithLinks(n.message)}
                        </p>
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
            className="relative w-7 h-7 md:w-8 md:h-8 flex items-center justify-center rounded-full text-slate-500 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
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
          <button onClick={() => setIsUserOpen(!isUserOpen)} className="ml-1 md:ml-2 relative cursor-pointer hover:opacity-80 transition-opacity outline-none">
            <div className="h-7 w-7 md:h-8 md:w-8 rounded-full bg-gradient-to-tr from-emerald-500 to-indigo-500 border border-slate-300 dark:border-zinc-800 ring-2 ring-white dark:ring-zinc-900 flex items-center justify-center text-white font-semibold text-xs md:text-sm">
              {userInitial}
            </div>
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
              <button onClick={() => { setIsUserOpen(false); setIsApiModalOpen(true); }} className="w-full flex items-center px-4 py-2 text-sm text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">
                <Key className="mr-2 h-4 w-4" /> Developer API
              </button>
              <button onClick={() => { setIsUserOpen(false); setIsKiss24KeyModalOpen(true); }} className="w-full flex items-center px-4 py-2 text-sm text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">
                <Key className="mr-2 h-4 w-4" /> KISS24 API Key
              </button>
              <div className="h-px bg-slate-100 dark:bg-zinc-800 my-1"></div>
              <button onClick={handleLogout} className="w-full flex items-center px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors">
                <LogOut className="mr-2 h-4 w-4" /> Log out
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {isMobileMenuOpen && (
        <div
          ref={mobileMenuRef}
          className="md:hidden absolute top-full left-0 right-0 mt-4 bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-xl p-4 flex flex-col gap-2 animate-in fade-in slide-in-from-top-4 origin-top z-40"
        >
          <Link to="/planner" className={mobileNavClass("/planner")}>Planner</Link>
          <Link to="/calendar" className={mobileNavClass("/calendar")}>Holidays</Link>
          <Link to="/tests" className={mobileNavClass("/tests")}>Tests</Link>

          {currentUser?.role === 'admin' && (
            <>
              <div className="h-px bg-slate-200 dark:bg-zinc-800 my-2"></div>
              <span className="text-[10px] font-extrabold text-slate-400 dark:text-zinc-500 uppercase tracking-wider px-4 mb-1">Admin Settings</span>
              <Link to="/raw" className={mobileNavClass("/raw")}>Raw Data Lab</Link>
              <Link to="/assets" className={mobileNavClass("/assets")}>Active Pool</Link>
              <Link to="/contacts" className={mobileNavClass("/contacts")}>Contacts</Link>
              <Link to="/countries" className={mobileNavClass("/countries")}>Analytics</Link>
              <Link to="/insights" className={mobileNavClass("/insights")}>Insights</Link>
              <Link to="/settings" className={mobileNavClass("/settings")}>System Settings</Link>
            </>
          )}
        </div>
      )}
    </nav>
      <ApiKeysModal
        isOpen={isApiModalOpen}
        onClose={() => setIsApiModalOpen(false)}
      />
      <MeetingProposalsModal
        isOpen={isMeetingModalOpen}
        testId={meetingProposalData?.test_id}
        testName={meetingProposalData?.test_name}
        proposalData={meetingProposalData}
        onClose={() => setIsMeetingModalOpen(false)}
        onSuccess={() => {
          window.dispatchEvent(new Event('refresh_test_data'));
        }}
      />
      <Kiss24KeyModal isOpen={isKiss24KeyModalOpen} onClose={() => setIsKiss24KeyModalOpen(false)} />
    </>
  );
}