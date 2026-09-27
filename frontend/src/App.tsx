import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { ThemeProvider } from "./components/ThemeProvider";
import { AppProvider, useAppContext } from "./context/AppContext";
import ControlPanelLayout from './layouts/ControlPanelLayout';
import AssetsLayout from './layouts/AssetsLayout';
import SyncLayout from './layouts/SyncLayout';
import Dashboard from "./pages/Dashboard";
import CalendarView from "./pages/CalendarView";
import TestsView from "./pages/TestsView";
import Planner from "./pages/Planner";
import TestDetailsView from "./pages/TestDetailsView";
import VulnAnalysisView from "./pages/VulnAnalysisView"
import ValidatingVulnsView from "./pages/ValidatingVulnsView";
import RagChatPage from './pages/assets/RagChatPage';
import AssetsView from "./pages/assets/AssetsView";
import RawAssetsView from "./pages/assets/RawAssetsView";
import AssetDetailView from "./pages/assets/AssetDetailView";
import CountriesView from "./pages/assets/CountriesView";
import InsightsView from "./pages/assets/InsightsView";
import DocumentsView from "./pages/assets/DocumentsView";
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
import DangerZoneSettings from './pages/settings/DangerZoneSettings';
import ContactsSettings from './pages/settings/ContactsSettings';
import AssetCriteriaSettings from './pages/settings/AssetCriteriaSettings';
import AssetReconciliationView from './pages/sync/AssetReconciliationView';
import ServiceNowSyncSettings from './pages/sync/ServiceNowSyncSettings';
import Kiss24SyncSettings from './pages/sync/Kiss24SyncSettings';
import TestReconciliationView from './pages/sync/TestReconciliationView';
import ScheduledTasksView from "./pages/sync/ScheduledTasksView";

// --- ROUTE GUARD COMPONENT ---
// Rejects users who do not have an explicitly allowed role
const RoleGuard = ({ allowedRoles }: { allowedRoles: string[] }) => {
  const { currentUser } = useAppContext();

  if (currentUser && !allowedRoles.includes(currentUser.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
};

function AppContent() {
  return (
    <div className="bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 min-h-screen transition-colors">
      <div className="fixed top-[-20%] left-[-10%] w-[50vw] h-[50vh] rounded-full bg-emerald-500/10 dark:bg-emerald-500/5 blur-[120px] pointer-events-none z-0" />
      <div className="fixed bottom-[-20%] right-[-10%] w-[50vw] h-[50vh] rounded-full bg-indigo-500/10 dark:bg-indigo-500/5 blur-[120px] pointer-events-none z-0" />

      <Routes>
        {/* Core Application - Accessible by Everyone */}
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/planner" element={<Planner />} />
        <Route path="/tests" element={<TestsView />} />
        <Route path="/tests/:id" element={<TestDetailsView />} />
        <Route path="/tests/:id/analysis" element={<VulnAnalysisView />} />

        {/* Pentesters, Admins, & Read-Only (Maintainer Blocked) */}
        <Route element={<RoleGuard allowedRoles={['admin', 'pentester', 'read_only']} />}>
          <Route path="/calendar" element={<CalendarView />} />
        </Route>
        <Route element={<RoleGuard allowedRoles={['admin', 'pentester']} />}>
          <Route path="/validating" element={<ValidatingVulnsView />} />
        </Route>

        {/* Modular Assets & Analytics Area */}
        <Route path="/assets" element={<AssetsLayout />}>
          {/* Default to pool instead of raw, since maintainers can't access raw */}
          <Route index element={<Navigate to="pool" replace />} />

          {/* Admin, Maintainer, Read-Only (Pentester Blocked from viewing unassigned inventory) */}
          <Route element={<RoleGuard allowedRoles={['admin', 'maintainer', 'read_only']} />}>
            <Route path="pool" element={<AssetsView />} />
          </Route>

          {/* Admin & Maintainer & Read-Only  */}
          <Route element={<RoleGuard allowedRoles={['admin', 'maintainer', 'read_only']} />}>
            <Route path="raw/:id" element={<AssetDetailView />} />
          </Route>

          {/* Admin & Read-Only  Raw and Analytics */}
          <Route element={<RoleGuard allowedRoles={['admin', 'read_only']} />}>
            <Route path="raw" element={<RawAssetsView />} />
            <Route path="analytics" element={<CountriesView />} />
            <Route path="insights" element={<InsightsView />} />
            <Route path="documents" element={<DocumentsView />} />
          </Route>
          {/* Admin Only  Rag */}
          <Route element={<RoleGuard allowedRoles={['admin']} />}>
            <Route path="rag" element={<RagChatPage />} />
            <Route path="rag/share/:sharedSessionId" element={<RagChatPage />} />
          </Route>
        </Route>

        {/* Modular sync Panel */}
        <Route path="/sync" element={<SyncLayout />}>
          <Route element={<RoleGuard allowedRoles={['admin']} />}>
            <Route path="kiss24" element={<Kiss24SyncSettings />} />
            <Route path="servicenow" element={<ServiceNowSyncSettings />} />
            <Route path="asset-reconciliation" element={<AssetReconciliationView />} />
            <Route path="test-reconciliation" element={<TestReconciliationView />} />
            <Route path="scheduled-tasks" element={<ScheduledTasksView />} />
          </Route>
        </Route>

        {/* Modular Control Panel */}
        <Route path="/settings" element={<ControlPanelLayout />}>
          <Route element={<RoleGuard allowedRoles={['admin', 'read_only']} />}>
            <Route index element={<ControlPanelHome />} />
            <Route path="users" element={<UsersSettings />} />
            <Route path="locations" element={<LocationsSettings />} />
            <Route path="asset-types" element={<AssetTypesSettings />} />
            <Route path="asset-criteria" element={<AssetCriteriaSettings />} />
            <Route path="services" element={<ServicesSettings />} />
            <Route path="categories" element={<CategoriesSettings />} />
            <Route path="regions" element={<RegionsSettings />} />
            <Route path="countries" element={<CountriesSettings />} />
            <Route path="contacts" element={<ContactsSettings />} />
            <Route path="logs" element={<SystemLogsSettings />} />
          </Route>
          <Route element={<RoleGuard allowedRoles={['admin']} />}>
            <Route path="api-keys" element={<ApiKeysSettings />} />
            <Route path="danger" element={<DangerZoneSettings />} />
          </Route>
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