import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./components/ThemeProvider";
import { AppProvider, useAppContext } from "./context/AppContext";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import SettingsView from "./pages/SettingsView";
import CalendarView from "./pages/CalendarView";
import AssetsView from "./pages/AssetsView";
import RawAssetsView from "./pages/RawAssetsView";

function AppContent() {
  const { wsStatus } = useAppContext();

  return (
    <BrowserRouter>
      <div className="bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 min-h-screen transition-colors">
        {!wsStatus && (
          <div className="fixed inset-0 z-[60] flex items-center justify-center bg-emerald-500/10 backdrop-blur-sm">
            <span className="text-sm font-medium text-slate-900 dark:text-zinc-100 animate-pulse">Connecting to server...</span>
          </div>
        )}

        <nav className="fixed top-6 left-1/2 -translate-x-1/2 z-50 flex items-center justify-between w-[95%] max-w-5xl px-6 py-3 bg-white/70 dark:bg-zinc-950/60 backdrop-blur-xl border border-slate-200 dark:border-zinc-800/80 rounded-full shadow-xl dark:shadow-2xl transition-colors">
          <a href="/dashboard" className="flex items-center gap-3 cursor-pointer group">
            <div className="bg-emerald-500/10 p-2 rounded-full border border-emerald-500/20 group-hover:bg-emerald-500/20 transition-colors">
              <SprayCan className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            </div>
            <span className="font-bold tracking-widest text-sm text-slate-900 dark:text-zinc-100 uppercase">Isha</span>
          </a>

          <div className="hidden md:flex items-center gap-2 text-sm font-medium">
            <Link to="/planner" className={navClass("/planner")}>Planner</Link>
            <Link to="/calendar" className={navClass("/calendar")}>Holidays</Link>
            <Link to="/tests" className={navClass("/tests")}>Tests</Link>
            <Link to="/assets" className={navClass("/assets")}>Assets</Link>
            <Link to="/raw" className={navClass("/raw")}>Raw Data</Link>
          </div>

          <div className="flex items-center gap-4">
            <button onClick={handleLogout} className="text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors"><LogOut className="h-4 w-4" /></button>
          </div>
        </nav>

        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/settings" element={<SettingsView />} />
          <Route path="/calendar" element={<CalendarView />} />
          <Route path="/assets" element={<AssetsView />} />
          <Route path="/raw" element={<RawAssetsView />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default function App() {
  return (
    <ThemeProvider defaultTheme="system">
      <AppProvider>
        <AppContent />
      </AppProvider>
    </ThemeProvider>
  );
}