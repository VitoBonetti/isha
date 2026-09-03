import { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation, Link } from "react-router-dom";
import axios from "axios";
import TopNav from "../components/TopNav";
import SecureNoteModal from "../components/Modals/SecureNoteModal";
import ConfirmModal from "../components/Modals/ConfirmModal";
import toast, { Toaster } from "react-hot-toast";
import { ChevronLeft, Save, ChevronDown, CalendarClock, CalendarCheck, ChevronRight, Database, Users, Shield, Code, MapPin, Server, Activity, Calendar, Edit2, FolderOpen, FolderPlus, Lock, LockOpen, Zap, Presentation, FileDown, CheckSquare, History, ListChecks, Mail, CheckCircle, CircleFadingPlus, ExternalLink, Cable } from "lucide-react";
import { useAppContext } from "../context/AppContext";
import RequirementsModal from "../components/Modals/RequirementsModal";
import IntroEmailModal from "../components/Modals/IntroEmailModal";
import FinalEmailModal from "../components/Modals/FinalEmailModal";
import MeetingParticipantsModal from "../components/Modals/MeetingParticipantsModal";
import Kiss24ControlPanel from "../components/Kiss24ControlPanel";

export default function TestDetailsView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { currentUser } = useAppContext();
  const isAdmin = currentUser?.role === 'admin';
  const isReadOnly = currentUser?.role === 'read_only';

  const backPath = location.state?.from || "/tests";
  const backLabel = location.state?.label || "Test Registry";

  const [loading, setLoading] = useState(true);

  // Accordion States
  const [isTargetsOpen, setIsTargetsOpen] = useState(true);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isAssetContactsOpen, setIsAssetContactsOpen] = useState(false);
  const [isCountryContactsOpen, setIsCountryContactsOpen] = useState(false);

  // Secure Vault States
  const [secretTarget, setSecretTarget] = useState<any>(null);
  const [secretConfirmOpen, setSecretConfirmOpen] = useState<any>(null);

  // Kiss24 Control Panel
  const [isKiss24PanelOpen, setIsKiss24PanelOpen] = useState(false);

  // Data States
  const [test, setTest] = useState<any>(null);
  const [services, setServices] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);

  // Analysis
  const [analysisPromptOpen, setAnalysisPromptOpen] = useState(false);
  const [analysisDate, setAnalysisDate] = useState("");
  const [hasAnalysis, setHasAnalysis] = useState(false);

  // Meeting
  const [isParticipantsModalOpen, setIsParticipantsModalOpen] = useState(false);
  const [pendingMeetingType, setPendingMeetingType] = useState("");
  const [defaultEmails, setDefaultEmails] = useState("");

  // Requirements Modal
  const [isRequirementsOpen, setIsRequirementsOpen] = useState(false);
  const STANDARD_MILESTONES = [
    "Information Email Sent",
    "Intake Meeting Planned",
    "Requirements",
    "Validate Finding",
    "Generate Presentation",
    "Restitution Meeting Planned",
    "Generate Report PDF",
    "Final Email Sent"
  ];
  const [milestones, setMilestones] = useState<Record<string, boolean>>({});

  const [isIntroEmailOpen, setIsIntroEmailOpen] = useState(false);
  const [isFinalEmailOpen, setIsFinalEmailOpen] = useState(false);
  const refreshMilestones = async () => {
    try {
      const resMiles = await axios.get(`/api/tests/${id}/milestones`);
      setMilestones(resMiles.data);
    } catch (err) {
      console.error("Failed to refresh milestones", err);
    }
  };

  const handleVerifyFindings = async () => {
    try {
      // Check if it exists
      const res = await axios.get(`/api/tests/${id}/analysis`);
      setAnalysisDate(res.data.timestamp);
      setAnalysisPromptOpen(true); // Pop the modal to ask Read vs Regenerate
    } catch (error: any) {
      if (error.response?.status === 404) {
        // Trigger fresh generation
        const toastId = toast.loading("Starting Vulnerability Analysis...");
        try {
          await axios.post(`/api/tests/${id}/analysis`);
          toast.dismiss(toastId);
          toast.success("Analysis started! You will be notified when ready.");
        } catch (e) {
          toast.dismiss(toastId);
          toast.error("Failed to start analysis.");
        }
      }
    }
  };

  // Format Helper for DB Status to Frontend Status
  const dbToFrontendStatus = (dbStatus: string) => {
    const map: Record<string, string> = {
      "NOT_PLANNED": "Not Planned",
      "SCHEDULED": "Scheduled",
      "IN_PROGRESS": "In Progress",
      "COMPLETED": "Completed",
      "STOPPED": "Stopped"
    };
    return map[dbStatus] || "Not Planned";
  };

  const fetchTest = async () => {
    try {
      const resTest = await axios.get(`/api/tests/${id}`);
      const tData = resTest.data;
      tData.status = dbToFrontendStatus(tData.status);
      setTest(tData);
    } catch (err) {
      toast.error("Failed to refresh test data");
    }
  };

  useEffect(() => {
    // 1. Core Data Fetching Function
    const fetchCoreData = () => {
      Promise.all([
        axios.get(`/api/tests/${id}`),
        axios.get('/api/services/'),
        axios.get('/api/board/categories/?year=All'),
        axios.get(`/api/tests/${id}/milestones`)
      ]).then(([resTest, resS, resCat, resMiles]) => {
        const tData = resTest.data;
        tData.status = dbToFrontendStatus(tData.status);
        setTest(tData);
        setServices(resS.data);
        setCategories(resCat.data);
        setMilestones(resMiles.data);
      }).catch(() => {
        toast.error("Failed to load test details");
        navigate("/tests");
      }).finally(() => setLoading(false));
    };

    // Initial load
    fetchCoreData();

    // 2. Background Analysis Check
    const checkAnalysis = () => {
      axios.get(`/api/tests/${id}/analysis`)
        .then(() => setHasAnalysis(true))
        .catch(() => setHasAnalysis(false));
    };
    checkAnalysis();

    // --- LISTEN FOR WEBSOCKET UPDATES ---
    // TopNav fires this event when ANY background task finishes!
    window.addEventListener('refresh_test_data', fetchCoreData);
    window.addEventListener('refresh_test_data', checkAnalysis);

    return () => {
      window.removeEventListener('refresh_test_data', fetchCoreData);
      window.removeEventListener('refresh_test_data', checkAnalysis);
    };

  }, [id, navigate]);

  if (loading || !test) return <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 flex items-center justify-center">Loading...</div>;

  const currentYear = new Date().getFullYear();
  const testYear = test?.start_year ? Number(test.start_year) : currentYear;

  const filteredCategories = categories
    .filter(c => {
       // 1. Must match the selected service lane
       if (String(c.service_lane_id) !== String(test?.service_lane_id)) return false;

       const gYear = Number(c.goal_year);

       // 2. Show categories for the Real Current Year OR the Test's Scheduled Year
       const matchesYear =
         gYear === currentYear ||
         gYear === currentYear + 1 ||
         gYear === testYear ||
         gYear === testYear + 1;

       // 3. Always keep the specifically assigned category visible, even if it is old
       const isAssignedCat = test?.category_id && String(c.id) === String(test.category_id);

       return matchesYear || isAssignedCat;
    })
    .sort((a, b) => Number(a.goal_year || 0) - Number(b.goal_year || 0));

  // --- ACTIONS ---
  const handleToggleMilestone = async (stepName: string) => {
    const currentState = milestones[stepName] || false;
    const newState = !currentState;

    // Optimistic update
    setMilestones(prev => ({ ...prev, [stepName]: newState }));

    try {
      await axios.put(`/api/tests/${id}/milestones`, { step_name: stepName, is_completed: newState });
    } catch (error) {
      toast.error("Failed to update milestone");
      // Revert on failure
      setMilestones(prev => ({ ...prev, [stepName]: currentState }));
    }
  };


  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) return;
    try {
      const payload = {
        name: test.name,
        service_lane_id: test.service_lane_id,
        category_id: test.category_id || null,
        credits_per_week: test.credits_per_week,
        duration_weeks: test.duration_weeks,
        status: test.status,
        is_tentative: test.is_tentative,
        kiss24: test.kiss24 || null
      };
      await axios.put(`/api/tests/${id}`, payload);
      toast.success("Test updated successfully");
      fetchTest();
    } catch (error) {
      toast.error("Failed to update test");
    }
  };

  const handleCreateWorkspace = async () => {
    const toastId = toast.loading("Provisioning workspace...");
    try {
      await axios.post(`/api/tests/${id}/workspace`);
      toast.dismiss(toastId);
      toast.success("Workspace creation started! It will update automatically.");
    } catch (error) {
      toast.dismiss(toastId);
      toast.error("Failed to create workspace.");
    }
  };

  const handleGeneratePresentation = async () => {
    const toastId = toast.loading("Queuing presentation generation...");
    try {
      await axios.post(`/api/tests/${id}/presentation`);
      toast.dismiss(toastId);
      toast.success("Presentation generation started! You will be notified when ready.");
    } catch (error: any) {
      toast.dismiss(toastId);
      toast.error(error.response?.data?.detail || "Failed to trigger presentation.");
    }
  };

  const handleGenerateReport = async () => {
    const toastId = toast.loading("Queuing report generation...");
    try {
      await axios.post(`/api/tests/${id}/report`);
      toast.dismiss(toastId);
      toast.success("PDF Report generation started! You will be notified when ready.");
    } catch (error: any) {
      toast.dismiss(toastId);
      toast.error(error.response?.data?.detail || "Failed to trigger report.");
    }
  };

  const handleOpenParticipants = async (meetingType: string) => {
    const toastId = toast.loading("Fetching default participants...");
    try {
      const res = await axios.get(`/api/luigi/${id}/meeting-participants`);
      setDefaultEmails(res.data.emails.join(", "));
      setPendingMeetingType(meetingType);
      setIsParticipantsModalOpen(true);
     toast.dismiss(toastId);
    } catch (error) {
      toast.dismiss(toastId);
      toast.error("Failed to fetch participants.");
    }
  };

  const handleConfirmParticipants = async (emails: string[]) => {
    setIsParticipantsModalOpen(false);
    const toastId = toast.loading(`Asking Luigi to find slots for the ${pendingMeetingType}...`);
    try {
      await axios.post(`/api/luigi/${id}/request-meeting-proposals`, {
        meeting_type: pendingMeetingType,
        emails: emails // We now send the edited JSON list!
      });
      toast.dismiss(toastId);
      toast.success("Luigi is analyzing calendars! You'll be notified shortly.");
    } catch (error) {
      toast.dismiss(toastId);
      toast.error("Failed to request meeting.");
    }
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
  };

  const inputClasses = isAdmin
    ? "w-full mt-1 p-2.5 border border-slate-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
    : "w-full mt-1 p-2.5 border border-transparent rounded-lg bg-slate-50 dark:bg-zinc-950/50 text-slate-900 dark:text-zinc-100 outline-none cursor-default font-medium appearance-none";

  const getStatusPill = (status: string) => {
    const s = status.toUpperCase();
    if (s === "COMPLETED") return <span className="px-3 py-1 rounded-full text-xs font-black uppercase tracking-wider bg-emerald-100 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20">Completed</span>;
    if (s === "STOPPED") return <span className="px-3 py-1 rounded-full text-xs font-black uppercase tracking-wider bg-red-100 text-red-800 dark:bg-red-500/10 dark:text-red-400 border border-red-200 dark:border-red-500/20">Stopped</span>;
    if (s === "NOT_PLANNED" || s === "NOT PLANNED") return <span className="px-3 py-1 rounded-full text-xs font-black uppercase tracking-wider bg-slate-100 text-slate-800 dark:bg-zinc-800 dark:text-zinc-400 border border-slate-200 dark:border-zinc-700">Backlog</span>;
    return <span className="px-3 py-1 rounded-full text-xs font-black uppercase tracking-wider bg-blue-100 text-blue-800 dark:bg-blue-500/10 dark:text-blue-400 border border-blue-200 dark:border-blue-500/20">Active Schedule</span>;
  };

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100">
      <TopNav />
      <Toaster position="bottom-right" />

      {/* SECURE NOTE MODALS */}
      <ConfirmModal
        isOpen={!!secretConfirmOpen}
        variant="secure"
        title="Access Secure Vault"
        message="You are about to decrypt sensitive credentials. Proceed?"
        confirmText="Decrypt & Open"
        onConfirm={() => { setSecretTarget(secretConfirmOpen); setSecretConfirmOpen(null); }}
        onCancel={() => setSecretConfirmOpen(null)}
      />
      {secretTarget && <SecureNoteModal test={secretTarget} onClose={() => { setSecretTarget(null); fetchTest(); }} />}

      <div className="pt-28 md:pt-32 pb-12 px-4 md:px-6 w-full max-w-[1600px] mx-auto overflow-hidden">

        {/* Top Toolbar */}
        <div className="flex justify-between items-center mb-4 md:mb-6">
          <button onClick={() => navigate(backPath)} className="flex items-center gap-1 md:gap-2 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white transition-colors font-medium">
            <ChevronLeft size={16} /> <span className="hidden sm:inline">Back to</span> {backLabel}
          </button>
        </div>

        {/* TWO-COLUMN WIDE LAYOUT */}
        <div className="flex flex-col lg:flex-row gap-6 md:gap-8 items-start w-full">

          {/* LEFT COLUMN: Test Form (2/3 width) */}
          <div className="w-full lg:w-2/3 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 md:p-8 shadow-sm">

            {/* Header Section */}
            <div className="flex flex-col md:flex-row justify-between items-start gap-4 md:gap-0 mb-6 md:mb-8 border-b border-slate-100 dark:border-zinc-800 pb-6">
              <div className="flex-1 w-full md:pr-4">
                <div className="flex flex-col xl:flex-row xl:items-center gap-2 xl:gap-4">
                  <h1 className="text-xl md:text-2xl font-bold flex items-start md:items-center gap-2">
                    <Activity className="text-indigo-500 flex-shrink-0 mt-1 md:mt-0" />
                    <span className="break-words">{test.name}</span>
                  </h1>

                  {/* WORKSPACE & VAULT BUTTONS */}
                  <div className="flex items-center gap-2 mt-2 xl:mt-0">
                    {test.auto_provision_workspace && (
                      <>
                        {test.drive_folder_url ? (
                          <a href={test.drive_folder_url} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 text-blue-600 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 border border-blue-200 dark:border-blue-900/50 rounded-lg transition-colors flex items-center gap-2 text-xs font-bold" title="Open Workspace">
                            <FolderOpen size={14} /> <span className="hidden sm:inline">Workspace</span>
                          </a>
                        ) : !isReadOnly && (
                          <button onClick={handleCreateWorkspace} className="px-3 py-1.5 text-slate-500 bg-slate-100 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors flex items-center gap-2 text-xs font-bold">
                            <FolderPlus size={14} /> <span className="hidden sm:inline">Create Workspace</span>
                          </button>
                        )}
                        {!isReadOnly && (
                          <button onClick={() => setSecretConfirmOpen(test)} className={`px-3 py-1.5 rounded-lg border transition-colors flex items-center gap-2 text-xs font-bold ${test.has_secret ? 'text-indigo-600 bg-indigo-50 border-indigo-200 dark:bg-indigo-900/30 dark:border-indigo-900/50' : 'text-slate-500 bg-slate-100 border-slate-200 dark:bg-zinc-800 dark:border-zinc-700 hover:text-indigo-600'}`}>
                            {test.has_secret ? <><Lock size={14} /><span className="hidden sm:inline">View Secret</span></> : <><LockOpen size={14} /><span className="hidden sm:inline">Add Secret</span></>}
                          </button>
                        )}
                        {hasAnalysis && (
                          <Link to={`/tests/${test.id}/analysis`} className="px-3 py-1.5 text-teal-600 bg-teal-50 dark:bg-teal-900/20 border border-teal-200 dark:border-teal-900/50 hover:bg-teal-100 dark:hover:bg-teal-900/40 rounded-lg transition-colors flex items-center gap-2 text-xs font-bold" title="Open Analysis">
                            <ListChecks size={14} /> <span className="hidden sm:inline">View Analysis</span>
                          </Link>
                        )}
                      </>
                    )}
                  </div>
                </div>

                {/* Admin Only: Links to underlying assets */}
                {isAdmin && test.assets && test.assets.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-4">
                    <span className="text-xs font-bold text-slate-400 flex items-center mr-1">Linked Assets:</span>
                    {test.assets.map((a: any) => (
                      <Link
                        key={a.asset_id}
                        to={`/assets/raw/${a.raw_asset_id}`}
                        state={{ from: `/tests/${test.id}`, label: 'Test Details' }}
                        className="flex items-center gap-1 px-2 py-1 rounded bg-slate-100 hover:bg-emerald-50 text-slate-600 hover:text-emerald-600 dark:bg-zinc-800 dark:hover:bg-emerald-900/30 dark:text-zinc-300 dark:hover:text-emerald-400 text-xs font-medium border border-slate-200 dark:border-zinc-700 transition-colors"
                      >
                        <Database size={12} /> {a.asset_name}
                      </Link>
                    ))}
                  </div>
                )}

                <div className="text-slate-500 text-xs md:text-sm mt-4 flex flex-col gap-2">
                  <span className="font-mono break-all">Test ID: {test.id}</span>
                  <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-6 mt-1">
                    {test.start_week && test.start_year ? (
                      <span className="flex items-center gap-1.5 font-bold text-slate-700 dark:text-zinc-300">
                        <Calendar size={14} className="text-indigo-500"/> Wk {test.start_week}, {test.start_year}
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 font-bold text-slate-500 italic">
                        <Calendar size={14} className="text-slate-400"/> Unscheduled
                      </span>
                    )}
                    <span className="flex items-center gap-1.5 font-bold text-slate-700 dark:text-zinc-300">
                      <Users size={14} className="text-blue-500"/> Team: {test.assigned_pentesters}
                    </span>
                  </div>
                </div>
              </div>

              {/* Status Badges */}
              <div className="flex flex-row md:flex-col flex-wrap items-start md:items-end gap-2 shrink-0 w-full md:w-auto mt-2 md:mt-0">
                {getStatusPill(test.status)}
                {test.is_tentative && (
                  <span className="px-3 py-1 bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-400 font-bold text-xs rounded-full uppercase tracking-wider border border-amber-200 dark:border-amber-500/20 shadow-sm mt-1">
                    Tentative (TBC)
                  </span>
                )}
              </div>
            </div>

            <form onSubmit={handleUpdate} className="space-y-6 md:space-y-8">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-6">
                <div className="sm:col-span-2">
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Test Name</label>
                  <input required disabled={!isAdmin} className={inputClasses} value={test.name} onChange={e => setTest({...test, name: e.target.value})} />
                </div>

                <div>
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Service Lane</label>
                  <select required disabled={!isAdmin} className={inputClasses} value={test.service_lane_id} onChange={e => setTest({...test, service_lane_id: e.target.value, category_id: ""})}>
                    {services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>

                <div>
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 flex items-center gap-1.5">
                    Forecast Category
                    {isAdmin && <span className="text-[10px] bg-slate-100 dark:bg-zinc-800 text-slate-500 px-2 py-0.5 rounded-full font-normal">(Updates Linked Asset)</span>}
                  </label>
                  <select disabled={!isAdmin || !test.service_lane_id} className={inputClasses} value={test.category_id || ""} onChange={e => setTest({...test, category_id: e.target.value})}>
                    <option value="">-- None --</option>
                    {filteredCategories.map(c => <option key={c.id} value={c.id}>{c.name} - {c.goal_year || 'Not Set'}</option>)}
                  </select>
                </div>

                <div>
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Credits Per Week</label>
                  <input type="number" step="0.5" min="0.5" required disabled={!isAdmin} className={inputClasses} value={test.credits_per_week} onChange={e => setTest({...test, credits_per_week: parseFloat(e.target.value)})} />
                </div>

                <div>
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Duration (Weeks)</label>
                  <input type="number" step="0.5" min="0.5" required disabled={!isAdmin} className={inputClasses} value={test.duration_weeks} onChange={e => setTest({...test, duration_weeks: parseFloat(e.target.value)})} />
                </div>

                <div className="sm:col-span-2">
                  <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 flex items-center gap-1.5">
                    KISS24 Test UUID
                    {isAdmin && <span className="text-[10px] bg-slate-100 dark:bg-zinc-800 text-slate-500 px-2 py-0.5 rounded-full font-normal">(Required for Report Generation)</span>}
                  </label>
                  <input
                    disabled={!isAdmin}
                    className={`${inputClasses} font-mono text-sm`}
                    placeholder="e.g. 123e4567-e89b-12d3-a456-426614174000"
                    value={test.kiss24 || ""}
                    onChange={e => setTest({...test, kiss24: e.target.value})}
                  />
                </div>

                {isAdmin && (
                  <div className="sm:col-span-2 flex items-center gap-3 p-4 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors">
                    <input type="checkbox" className="h-4 w-4 rounded text-indigo-500 border-slate-300" checked={test.is_tentative} onChange={e => setTest({...test, is_tentative: e.target.checked})} />
                    <span className="text-sm font-bold text-slate-700 dark:text-zinc-300">Mark Schedule as Tentative (TBC)</span>
                  </div>
                )}
              </div>

              {isAdmin && (
                <div className="flex justify-end pt-6 md:pt-8 border-t border-slate-100 dark:border-zinc-800 animate-in fade-in slide-in-from-bottom-2">
                  <button type="submit" className="w-full md:w-auto flex justify-center items-center gap-2 px-6 py-2.5 text-sm font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg shadow-sm transition-colors">
                    <Save size={16} /> Save Changes
                  </button>
                </div>
              )}
            </form>
          </div>

          {/* RIGHT COLUMN: Action Menu & Accordions (1/3 width) */}
          <div className="w-full lg:w-1/3 flex flex-col gap-4">
            {/* --- KISS24 INTEGRATION WIDGET --- */}
            <button
              onClick={() => setIsKiss24PanelOpen(true)}
              className="w-full flex items-center justify-between p-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white rounded-2xl shadow-md transition-all outline-none group"
            >
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-white/20 rounded-xl shadow-sm">
                  <Cable size={20} className="text-white" />
                </div>
                <div className="text-left">
                  <h3 className="font-extrabold text-sm md:text-base tracking-wide">Keep Secure 24</h3>
                  <p className="text-[10px] md:text-xs text-blue-100 font-medium mt-0.5">Manage Vulns & Sync Platform</p>
                </div>
              </div>
              <div className="p-2 bg-white/10 rounded-full group-hover:bg-white/20 transition-colors">
                <ChevronRight size={18} className="text-white" />
              </div>
            </button>
            {/* ------------------------------------------ */}
            {/* ACTION MENU (Report Generators) */}
            {test.auto_provision_workspace && !isReadOnly && (
              <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 md:p-5 shadow-sm mb-2">

                {/* 5-Column Grid for Square Buttons */}
                <div className="grid grid-cols-8 gap-2 md:gap-3">
                  {isAdmin ? (
                    <button
                      onClick={(e) => { e.stopPropagation(); setIsIntroEmailOpen(true); }}
                      title="Send Intro Email"
                      className="aspect-square flex flex-col items-center justify-center gap-1 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/40 text-blue-600 dark:text-blue-400 rounded-xl transition-colors border border-blue-200 dark:border-blue-900/30 p-2 shadow-sm"
                    >
                      <Mail size={16} className="shrink-0" />
                    </button>
                  ) : (
                    <button
                      disabled
                      title="Send Intro Email (Admin Only)"
                      className="aspect-square flex flex-col items-center justify-center gap-1 bg-slate-100 dark:bg-zinc-800/50 text-slate-400 dark:text-zinc-600 rounded-xl border border-slate-200 dark:border-zinc-800 p-2 shadow-sm cursor-not-allowed opacity-70"
                    >
                      <CircleFadingPlus size={16} className="shrink-0" />
                    </button>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); handleOpenParticipants('Intake Meeting Planned'); }}
                    title="Schedule Intake Meeting"
                    className="aspect-square flex flex-col items-center justify-center gap-1 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/40 text-red-600 dark:text-red-400 rounded-xl transition-colors border border-red-200 dark:border-red-900/30 p-2 shadow-sm"
                  >
                    <CalendarClock size={16} className="shrink-0" />
                  </button>
                  <button
                   onClick={(e) => { e.stopPropagation(); setIsRequirementsOpen(true); }}
                   title="Test Requirements"
                   className="aspect-square flex flex-col items-center justify-center gap-1 bg-fuchsia-50 dark:bg-fuchsia-900/20 hover:bg-fuchsia-100 dark:hover:bg-fuchsia-900/40 text-fuchsia-600 dark:text-fuchsia-400 rounded-xl transition-colors border border-fuchsia-200 dark:border-fuchsia-900/30 p-2 shadow-sm"
                   >
                    <CheckSquare size={16} className="shrink-0" />
                  </button>
                  <button
                   onClick={(e) => { e.stopPropagation(); handleVerifyFindings(); }}
                   title="Vulnerabilities Analysis"
                   className="aspect-square flex flex-col items-center justify-center gap-1 bg-teal-50 dark:bg-teal-900/20 hover:bg-teal-100 dark:hover:bg-teal-900/40 text-teal-600 dark:text-teal-400 rounded-xl transition-colors border border-teal-200 dark:border-teal-900/30 p-2 shadow-sm"
                   >
                    <ListChecks size={16} className="shrink-0" />
                  </button>
                  <button
                    onClick={handleGeneratePresentation}
                    title="Generate Presentation"
                    className="aspect-square flex flex-col items-center justify-center gap-1 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/40 text-blue-600 dark:text-blue-400 rounded-xl transition-colors border border-blue-200 dark:border-blue-900/30 p-2 shadow-sm"
                  >
                    <Presentation size={16} className="shrink-0" />
                  </button>
                  {/* Placeholders for future buttons */}
                  <button
                    onClick={(e) => { e.stopPropagation(); handleOpenParticipants('Restitution Meeting Planned'); }}
                    title="Schedule Restitution Meeting"
                    className="aspect-square flex flex-col items-center justify-center gap-1 bg-orange-50 dark:bg-orange-900/20 hover:bg-orange-100 dark:hover:bg-orange-900/40 text-orange-600 dark:text-orange-400 rounded-xl transition-colors border border-orange-200 dark:border-orange-900/30 p-2 shadow-sm"
                  >
                    <CalendarCheck size={16} className="shrink-0" />
                  </button>
                  <button
                    onClick={handleGenerateReport}
                    title="Generate PDF Report"
                    className="aspect-square flex flex-col items-center justify-center gap-1 bg-purple-50 dark:bg-purple-900/20 hover:bg-purple-100 dark:hover:bg-purple-900/40 text-purple-600 dark:text-purple-400 rounded-xl transition-colors border border-purple-200 dark:border-purple-900/30 p-2 shadow-sm"
                  >
                    <FileDown size={16} className="shrink-0" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); setIsFinalEmailOpen(true); }}
                    title="Send Final Email"
                    className="aspect-square flex flex-col items-center justify-center gap-1 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/40 text-blue-600 dark:text-blue-400 rounded-xl transition-colors border border-blue-200 dark:border-blue-900/30 p-2 shadow-sm"
                  >
                    <CheckCircle size={16} className="shrink-0" />
                  </button>

                </div>
              </div>
            )}

            {/* REAL MILESTONES TRACKING */}
            <div>
              <button onClick={() => setIsTargetsOpen(!isTargetsOpen)} className="flex items-center gap-2 md:gap-3 w-full text-left font-bold text-slate-800 dark:text-zinc-200 bg-white dark:bg-zinc-900 p-4 md:p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm hover:border-slate-300 dark:hover:border-zinc-700 transition-colors outline-none">
                {isTargetsOpen ? <ChevronDown size={20} className="text-slate-400 flex-shrink-0" /> : <ChevronRight size={20} className="text-slate-400 flex-shrink-0" />}
                <CheckSquare size={18} className="text-emerald-500 flex-shrink-0 md:h-5 md:w-5" />
                <span className="truncate flex-1">Milestones Tracking</span>

                {/* Status Pill on the collapsed header */}
                <span className="text-[10px] md:text-xs font-black bg-slate-100 dark:bg-zinc-800 text-slate-500 px-2 py-1 rounded-md">
                  {STANDARD_MILESTONES.filter(m => milestones[m]).length} / {STANDARD_MILESTONES.length}
                </span>
              </button>

              {isTargetsOpen && (
                <div className="mt-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 md:p-6 shadow-sm animate-in fade-in slide-in-from-top-2">

                  {/* Progress Bar */}
                  <div className="mb-5">
                    <div className="flex justify-between text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                      <span>Progress</span>
                      <span className={STANDARD_MILESTONES.filter(m => milestones[m]).length === STANDARD_MILESTONES.length ? "text-emerald-500" : "text-blue-500"}>
                        {Math.round((STANDARD_MILESTONES.filter(m => milestones[m]).length / STANDARD_MILESTONES.length) * 100)}%
                      </span>
                    </div>
                    <div className="w-full bg-slate-100 dark:bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                      <div
                        className={`h-full transition-all duration-500 ${STANDARD_MILESTONES.filter(m => milestones[m]).length === STANDARD_MILESTONES.length ? "bg-emerald-500" : "bg-blue-500"}`}
                        style={{ width: `${(STANDARD_MILESTONES.filter(m => milestones[m]).length / STANDARD_MILESTONES.length) * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Checklist */}
                  <div className="space-y-3">
                    {STANDARD_MILESTONES.map((step) => (
                      <label key={step} className="flex items-start gap-3 cursor-pointer group">
                        <input
                          type="checkbox"
                          checked={milestones[step] || false}
                          onChange={() => handleToggleMilestone(step)}
                          className="mt-0.5 w-4 h-4 rounded text-emerald-500 border-slate-300 dark:border-zinc-700 bg-slate-50 dark:bg-zinc-950 focus:ring-emerald-500 transition-colors cursor-pointer"
                        />
                        <span className={`text-sm font-bold transition-colors ${milestones[step] ? 'text-slate-400 dark:text-zinc-500 line-through' : 'text-slate-800 dark:text-zinc-200 group-hover:text-blue-600 dark:group-hover:text-blue-400'}`}>
                          {step}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* ASSET CONTACTS (Aggregated) */}
            <div>
              <button onClick={() => setIsAssetContactsOpen(!isAssetContactsOpen)} className="flex items-center gap-2 md:gap-3 w-full text-left font-bold text-slate-800 dark:text-zinc-200 bg-white dark:bg-zinc-900 p-4 md:p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm hover:border-slate-300 dark:hover:border-zinc-700 transition-colors outline-none">
                {isAssetContactsOpen ? <ChevronDown size={20} className="text-slate-400 flex-shrink-0" /> : <ChevronRight size={20} className="text-slate-400 flex-shrink-0" />}
                <Server size={18} className="text-indigo-500 flex-shrink-0 md:h-5 md:w-5" />
                <span className="truncate">Linked Asset Contacts</span>
                <span className="ml-auto text-[10px] md:text-xs bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded-full text-slate-500 whitespace-nowrap">{test.asset_contacts?.length || 0} contacts</span>
              </button>
              {isAssetContactsOpen && (
                <div className="mt-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 md:p-6 shadow-sm animate-in fade-in slide-in-from-top-2">
                  {test.asset_contacts && test.asset_contacts.length > 0 ? (
                    <div className="relative border-l border-slate-200 dark:border-zinc-800 ml-2 md:ml-3 space-y-6">
                      {test.asset_contacts.map((c: any, idx: number) => (
                        <div key={idx} className="relative pl-5 md:pl-6">
                          <div className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-indigo-500 ring-4 ring-white dark:ring-zinc-900"></div>
                          <div className="flex flex-col mb-1">
                            <span className="font-bold text-sm text-slate-900 dark:text-zinc-100">{c.full_name || 'No Name Provided'}</span>
                            <span className="text-[10px] md:text-xs font-mono text-slate-500">{c.email}</span>
                          </div>
                          <div className="flex gap-2 mt-1.5 flex-wrap">
                            {c.is_stakeholder && <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 text-[9px] font-extrabold uppercase tracking-wider text-amber-700 dark:text-amber-400"><Shield size={10}/> Stakeholder</span>}
                            {c.is_developer && <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 text-[9px] font-extrabold uppercase tracking-wider text-indigo-700 dark:text-indigo-400"><Code size={10}/> Developer</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-slate-500 py-4 md:py-6 text-sm">No specific contacts assigned to the linked assets.</div>
                  )}
                </div>
              )}
            </div>

            {/* COUNTRY CONTACTS (Aggregated) */}
            <div>
              <button onClick={() => setIsCountryContactsOpen(!isCountryContactsOpen)} className="flex items-center gap-2 md:gap-3 w-full text-left font-bold text-slate-800 dark:text-zinc-200 bg-white dark:bg-zinc-900 p-4 md:p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm hover:border-slate-300 dark:hover:border-zinc-700 transition-colors outline-none">
                {isCountryContactsOpen ? <ChevronDown size={20} className="text-slate-400 flex-shrink-0" /> : <ChevronRight size={20} className="text-slate-400 flex-shrink-0" />}
                <MapPin size={18} className="text-amber-500 flex-shrink-0 md:h-5 md:w-5" />
                <span className="truncate">Linked Market Contacts</span>
                <span className="ml-auto text-[10px] md:text-xs bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded-full text-slate-500 whitespace-nowrap">{test.country_contacts?.length || 0} contacts</span>
              </button>
              {isCountryContactsOpen && (
                <div className="mt-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 md:p-6 shadow-sm animate-in fade-in slide-in-from-top-2">
                  {test.country_contacts && test.country_contacts.length > 0 ? (
                    <div className="relative border-l border-slate-200 dark:border-zinc-800 ml-2 md:ml-3 space-y-6">
                      {test.country_contacts.map((c: any, idx: number) => (
                        <div key={idx} className="relative pl-5 md:pl-6">
                          <div className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-amber-500 ring-4 ring-white dark:ring-zinc-900"></div>
                          <div className="flex flex-col mb-1">
                            <span className="font-bold text-sm text-slate-900 dark:text-zinc-100">{c.full_name || 'No Name Provided'}</span>
                            <span className="text-[10px] md:text-xs font-mono text-slate-500">{c.email}</span>
                          </div>
                          <div className="flex gap-2 mt-1.5 flex-wrap">
                            {c.is_stakeholder && <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 text-[9px] font-extrabold uppercase tracking-wider text-amber-700 dark:text-amber-400"><Shield size={10}/> Stakeholder</span>}
                            {c.is_developer && <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 text-[9px] font-extrabold uppercase tracking-wider text-indigo-700 dark:text-indigo-400"><Code size={10}/> Developer</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-slate-500 py-4 md:py-6 text-sm">No contacts assigned for the linked regions.</div>
                  )}
                </div>
              )}
            </div>

            {/* TEST HISTORY */}
            <div>
              <button onClick={() => setIsHistoryOpen(!isHistoryOpen)} className="flex items-center gap-2 md:gap-3 w-full text-left font-bold text-slate-800 dark:text-zinc-200 bg-white dark:bg-zinc-900 p-4 md:p-5 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm hover:border-slate-300 dark:hover:border-zinc-700 transition-colors outline-none">
                {isHistoryOpen ? <ChevronDown size={20} className="text-slate-400 flex-shrink-0" /> : <ChevronRight size={20} className="text-slate-400 flex-shrink-0" />}
                <History size={18} className="text-blue-500 flex-shrink-0 md:h-5 md:w-5" />
                <span className="truncate">Test History</span>
                <span className="ml-auto text-[10px] md:text-xs bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded-full text-slate-500 whitespace-nowrap">{test.history?.length || 0} events</span>
              </button>
              {isHistoryOpen && (
                <div className="mt-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 md:p-6 shadow-sm animate-in fade-in slide-in-from-top-2">
                  {test.history && test.history.length > 0 ? (
                    <div className="relative border-l border-slate-200 dark:border-zinc-800 ml-2 md:ml-3 space-y-6">
                      {test.history.map((h: any) => (
                        <div key={h.id} className="relative pl-5 md:pl-6">
                          <div className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-blue-500 ring-4 ring-white dark:ring-zinc-900"></div>
                          <div className="flex flex-col md:flex-row md:justify-between items-start mb-1 gap-1 md:gap-0">
                            <span className="font-bold text-sm text-slate-900 dark:text-zinc-100">{h.action}</span>
                            <span className="text-[10px] md:text-xs font-mono text-slate-400">{formatDate(h.timestamp)}</span>
                          </div>
                          <div className="text-sm text-slate-600 dark:text-zinc-400 break-words">{h.details}</div>
                          <div className="text-[10px] md:text-xs text-slate-400 mt-1 font-medium">By: {h.user_name || 'System'}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-slate-500 py-4 md:py-6 text-sm">No history recorded for this test yet.</div>
                  )}
                </div>
              )}
            </div>

          </div>
        </div>
      </div>
      <ConfirmModal
        isOpen={analysisPromptOpen}
        title="Analysis Already Exists"
        message={`An analysis was generated on ${new Date(analysisDate).toLocaleString()}. Do you want to read it, or generate a fresh one?`}
        confirmText="Read Existing"
        cancelText="Generate New"
        onConfirm={async () => {
          setAnalysisPromptOpen(false);
          navigate(`/tests/${id}/analysis`);
        }}
        onCancel={async () => {
          setAnalysisPromptOpen(false);
          const toastId = toast.loading("Queuing new analysis...");
          try {
            await axios.post(`/api/tests/${id}/analysis`);
            toast.dismiss(toastId);
            toast.success("Analysis started! You will be notified when ready.");
          } catch (e) {
            toast.dismiss(toastId);
            toast.error("Failed to start analysis.");
          }
        }}
      />
      <RequirementsModal
        isOpen={isRequirementsOpen}
        testId={id as string}
        onClose={() => setIsRequirementsOpen(false)}
        onSuccess={refreshMilestones}
      />
      <IntroEmailModal
        isOpen={isIntroEmailOpen}
        testId={id as string}
        onClose={() => setIsIntroEmailOpen(false)}
        onSuccess={refreshMilestones}
      />
      <FinalEmailModal
        isOpen={isFinalEmailOpen}
        testId={id as string}
        onClose={() => setIsFinalEmailOpen(false)}
        onSuccess={refreshMilestones}
      />
      <MeetingParticipantsModal
        isOpen={isParticipantsModalOpen}
        meetingType={pendingMeetingType}
        initialEmails={defaultEmails}
        onClose={() => setIsParticipantsModalOpen(false)}
        onConfirm={handleConfirmParticipants}
      />
      <Kiss24ControlPanel
        isOpen={isKiss24PanelOpen}
        onClose={() => setIsKiss24PanelOpen(false)}
        test={test}
        onRefresh={() => window.dispatchEvent(new Event('refresh_test_data'))}
      />
    </div>
  );
}