import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from "react-router-dom";
import { ThemeProvider } from "./components/ThemeProvider";
import { AppProvider, useAppContext } from "./context/AppContext";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import SettingsView from "./pages/SettingsView";
import CalendarView from "./pages/CalendarView";
import AssetsView from "./pages/AssetsView";
import RawAssetsView from "./pages/RawAssetsView";
import AssetDetailView from "./pages/AssetDetailView";
import TestsView from "./pages/TestsView";
import Planner from "./pages/Planner";
import CountriesView from "./pages/CountriesView";
import { SprayCan, LogOut } from "lucide-react";

function AppContent() {
  const { wsStatus, handleLogout, currentUser } = useAppContext();

  // To support your navClass logic
  const location = useLocation();
  const currentPath = location.pathname;

  const navClass = (path: string) => {
    const isActive = currentPath === path;
    return isActive
      ? "text-slate-900 dark:text-zinc-100 px-4 py-1.5 rounded-full bg-slate-200/50 dark:bg-zinc-800/50 border border-slate-300/50 dark:border-zinc-700/50"
      : "text-slate-500 dark:text-zinc-400 px-4 py-1.5 rounded-full border border-transparent hover:text-slate-900 dark:hover:text-zinc-100 transition-colors";
  };

  return (
    <div className="bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 min-h-screen transition-colors">
      <div className="fixed top-[-20%] left-[-10%] w-[50vw] h-[50vh] rounded-full bg-emerald-500/10 dark:bg-emerald-500/5 blur-[120px] pointer-events-none z-0" />
      <div className="fixed bottom-[-20%] right-[-10%] w-[50vw] h-[50vh] rounded-full bg-indigo-500/10 dark:bg-indigo-500/5 blur-[120px] pointer-events-none z-0" />
      {currentUser && wsStatus !== 'connected' && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-emerald-500/10 backdrop-blur-sm">
          <span className="text-sm font-medium text-slate-900 dark:text-zinc-100 animate-pulse">Connecting to server...</span>
        </div>
      )}


      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings" element={<SettingsView />} />
        <Route path="/calendar" element={<CalendarView />} />
        <Route path="/planner" element={<Planner />} />
        <Route path="/assets" element={<AssetsView />} />
        <Route path="/raw" element={<RawAssetsView />} />
        <Route path="/raw/:id" element={<AssetDetailView />} />
        <Route path="/tests" element={<TestsView />} />
        <Route path="/countries" element={<CountriesView />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider defaultTheme="system">
      {/* FIX: BrowserRouter is now at the absolute top level!
        This means AppProvider (and its useNavigate hook) is now safely inside the router context.
      */}
      <BrowserRouter>
        <AppProvider>
          <AppContent />
        </AppProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}