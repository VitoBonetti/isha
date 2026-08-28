import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { ThemeProvider } from "./components/ThemeProvider";
import { AppProvider, useAppContext } from "./context/AppContext";
import Dashboard from "./pages/Dashboard";
import CalendarView from "./pages/CalendarView";
import AssetsView from "./pages/AssetsView";
import RawAssetsView from "./pages/RawAssetsView";
import AssetDetailView from "./pages/AssetDetailView";
import TestsView from "./pages/TestsView";
import Planner from "./pages/Planner";
import CountriesView from "./pages/CountriesView";
import InsightsView from "./pages/InsightsView";
import TestDetailsView from "./pages/TestDetailsView";
import VulnAnalysisView from "./pages/VulnAnalysisView"
import ValidatingVulnsView from "./pages/ValidatingVulnsView";
import AssetReconciliationView from './pages/settings/AssetReconciliationView';
import ControlPanelLayout from './layouts/ControlPanelLayout';
import ControlPanelHome from './pages/settings/ControlPanelHome';
import UsersSettings from './pages/settings/UsersSettings';
import LocationsSettings from './pages/settings/LocationsSettings';
import AssetTypesSettings from './pages/settings/AssetTypesSettings';
import ServicesSettings from './pages/settings/ServicesSettings';
import CategoriesSettings from './pages/settings/CategoriesSettings';
import RegionsSettings from './pages/settings/RegionsSettings';
import CountriesSettings from './pages/settings/CountriesSettings';
import ApiKeysSettings from './pages/settings/ApiKeysSettings';
import SystemLogsSettings from './pages/settings/SystemLogsSettings';
import ServiceNowSyncSettings from './pages/settings/ServiceNowSyncSettings';
import DangerZoneSettings from './pages/settings/DangerZoneSettings';
import ContactsSettings from './pages/settings/ContactsSettings';
import Kiss24SyncSettings from './pages/settings/Kiss24SyncSettings';
import AssetsLayout from './layouts/AssetsLayout';

function AppContent() {
  return (
    <div className="bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 min-h-screen transition-colors">
      <div className="fixed top-[-20%] left-[-10%] w-[50vw] h-[50vh] rounded-full bg-emerald-500/10 dark:bg-emerald-500/5 blur-[120px] pointer-events-none z-0" />
      <div className="fixed bottom-[-20%] right-[-10%] w-[50vw] h-[50vh] rounded-full bg-indigo-500/10 dark:bg-indigo-500/5 blur-[120px] pointer-events-none z-0" />

      <Routes>
        {/* Core Application */}
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/calendar" element={<CalendarView />} />
        <Route path="/planner" element={<Planner />} />
        <Route path="/tests" element={<TestsView />} />
        <Route path="/tests/:id" element={<TestDetailsView />} />
        <Route path="/tests/:id/analysis" element={<VulnAnalysisView />} />
        <Route path="/validating" element={<ValidatingVulnsView />} />

        {/* Modular Assets & Analytics Area */}
        <Route path="/assets" element={<AssetsLayout />}>
          <Route index element={<Navigate to="raw" replace />} />
          <Route path="raw" element={<RawAssetsView />} />
          <Route path="raw/:id" element={<AssetDetailView />} />
          <Route path="pool" element={<AssetsView />} />
          <Route path="analytics" element={<CountriesView />} />
          <Route path="insights" element={<InsightsView />} />
        </Route>

        {/* Modular Control Panel */}
        <Route path="/settings" element={<ControlPanelLayout />}>
          <Route index element={<ControlPanelHome />} />
          <Route path="users" element={<UsersSettings />} />
          <Route path="locations" element={<LocationsSettings />} />
          <Route path="asset-types" element={<AssetTypesSettings />} />
          <Route path="services" element={<ServicesSettings />} />
          <Route path="categories" element={<CategoriesSettings />} />
          <Route path="regions" element={<RegionsSettings />} />
          <Route path="countries" element={<CountriesSettings />} />
          <Route path="contacts" element={<ContactsSettings />} />
          <Route path="kiss24" element={<Kiss24SyncSettings />} />
          <Route path="servicenow" element={<ServiceNowSyncSettings />} />
          <Route path="reconciliation" element={<AssetReconciliationView />} />
          <Route path="api-keys" element={<ApiKeysSettings />} />
          <Route path="logs" element={<SystemLogsSettings />} />
          <Route path="danger" element={<DangerZoneSettings />} />
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider defaultTheme="system">
      <BrowserRouter>
        <AppProvider>
          <AppContent />
        </AppProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}