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
    <>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<Dashboard />} />

        {/* Placeholder Routes so clicking the dashboard cards doesn't crash */}
        <Route path="/planner" element={<div className="p-20 text-center">Planner Route Pending</div>} />
        <Route path="/assets" element={<AssetsView />} />
        <Route path="/raw" element={<RawAssetsView />} />
        <Route path="/tests" element={<div className="p-20 text-center">Tests Route Pending</div>} />
        <Route path="/countries" element={<div className="p-20 text-center">Countries Route Pending</div>} />
        <Route path="/assets" element={<AssetsView />} />
        <Route path="/raw" element={<RawAssetsView />} />
        <Route path="/insights" element={<div className="p-20 text-center">Insights Route Pending</div>} />
        <Route path="/settings" element={<SettingsView />} />

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>

      {/* WebSocket Status Indicator */}
      <div className="fixed bottom-6 left-6 z-50 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md px-4 py-2 rounded-full shadow-lg border border-slate-200 dark:border-zinc-800 flex items-center gap-2 text-xs font-bold text-slate-600 dark:text-zinc-300">
        <span className={`w-2.5 h-2.5 rounded-full transition-all duration-300 ${
          wsStatus === 'connected' ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' :
          wsStatus === 'connecting' ? 'bg-amber-500 animate-pulse' : 'bg-red-500'
        }`}></span>
        {wsStatus === 'connected' ? 'Live Sync Active' : wsStatus === 'connecting' ? 'Reconnecting...' : 'Offline'}
      </div>
    </>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AppProvider>
          <AppContent />
        </AppProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}