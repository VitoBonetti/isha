import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import TopNav from '../components/TopNav';
import {
  RefreshCw, ExternalLink, ShieldAlert, Wand2, ArrowUpDown, ArrowUp, ArrowDown,
  Filter, ChevronLeft, ChevronRight, MessageSquareText, CheckCircle2, AlertCircle
} from 'lucide-react';
import { useAppContext } from '../context/AppContext';
import Kiss24KeyModal from '../components/Modals/Kiss24KeyModal';

// --- SUB-COMPONENT: Expandable Row ---
const VulnRow = ({ v, onUpdateField, isKeyReady }: { v: any, onUpdateField: (uuid: string, field: string, value: any) => void, isKeyReady: boolean }) => {
  const [issues, setIssues] = useState(v.other_issue || "");
  const [notes, setNotes] = useState(v.note || "");
  const [action, setAction] = useState(v.action_taken || "");
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // NEW: Expandable row state
  const [isExpanded, setIsExpanded] = useState(false);

  const triggerAiAnalysis = async (e: React.MouseEvent, uuid: string) => {
    e.stopPropagation(); // Prevent row expansion when clicking the wand
    setIsAnalyzing(true);
    setIsExpanded(true); // Auto-expand to show the user the result when it arrives!
    toast("Luigi is analyzing evidence...", { icon: '🪄' });
    try {
      await axios.post(`/api/kiss24/validating-vulns/${uuid}/analyze`);
    } catch (err) {
      toast.error("Failed to start AI analysis");
      setIsAnalyzing(false);
    }
  };

  useEffect(() => {
    setIsAnalyzing(false);
  }, [v.updated_at, v.ai_suggestion]);

  useEffect(() => {
    setIssues(v.other_issue || "");
    setNotes(v.note || "");
    setAction(v.action_taken || "");
  }, [v.other_issue, v.note, v.action_taken]);

  return (
    <>
      {/* SUMMARY ROW (Always Visible) */}
      <tr
        onClick={() => setIsExpanded(!isExpanded)}
        className={`hover:bg-slate-50 dark:hover:bg-zinc-800/50 cursor-pointer transition-colors ${isExpanded ? 'bg-slate-50 dark:bg-zinc-800/30' : ''}`}
      >
        <td className="p-4 text-slate-400">
          <ChevronRight size={18} className={`transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`} />
        </td>
        <td className="p-4">
          {v.id ? (
            <a href={`https://randstad.eu.vulnmanager.com/vulnerabilities/${v.uuid}/show`} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} className="text-indigo-600 dark:text-indigo-400 hover:underline font-bold flex items-center gap-1">
              {v.id} <ExternalLink size={12} />
            </a>
          ) : (
            <span className="font-mono text-xs text-slate-400">{v.uuid.slice(0, 8)}...</span>
          )}
          <div className="text-xs text-slate-500 truncate w-48 mt-1" title={v.description}>{v.description || 'Sync required'}</div>
        </td>
        <td className="p-4">
          <div className="flex flex-col gap-1.5 items-start">
            <span className={`px-2 py-1 rounded text-xs font-bold ${
              v.severity === 'Critical' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400 border border-purple-200 dark:border-purple-800' :
              v.severity === 'High' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 border border-red-200 dark:border-red-800' :
              v.severity === 'Medium' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 border border-amber-200 dark:border-amber-800' :
              'bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-zinc-300'
            }`}>
              {v.severity || 'N/A'}
            </span>
            {v.sub_state && (
              <span className="text-[9px] font-bold text-slate-500 dark:text-zinc-400 bg-slate-200 dark:bg-zinc-800 px-1.5 py-0.5 rounded uppercase tracking-wider">
                {v.sub_state}
              </span>
            )}
          </div>
        </td>
        <td className="p-4">
          <div className="font-medium text-xs">{v.asset || 'N/A'}</div>
          <div className="text-[10px] text-slate-400">{v.organization || ''} {v.test_id ? `| ${v.test_id}` : ''}</div>
        </td>
        <td className="p-4">
          <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${v.validating_team === 'DevoTeam' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300' : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'}`}>
            {v.validating_team}
          </span>
        </td>
        <td className="p-4 text-center" onClick={e => e.stopPropagation()}>
          <input type="checkbox" checked={v.need_credentials} onChange={(e) => onUpdateField(v.uuid, 'need_credentials', e.target.checked)} className="w-4 h-4 text-indigo-600 rounded cursor-pointer" />
        </td>
        <td className="p-4 text-center" onClick={e => e.stopPropagation()}>
          <input type="checkbox" checked={v.need_vpn} onChange={(e) => onUpdateField(v.uuid, 'need_vpn', e.target.checked)} className="w-4 h-4 text-indigo-600 rounded cursor-pointer" />
        </td>
        <td className="p-4 text-center" onClick={e => e.stopPropagation()}>
          <button
            onClick={(e) => triggerAiAnalysis(e, v.uuid)}
            disabled={!isKeyReady || isAnalyzing || !['Low', 'Info'].includes(v.severity)}
            className={`p-1.5 rounded-lg shrink-0 transition-all ${
              !isKeyReady
                ? 'bg-slate-100 dark:bg-zinc-800 text-slate-400 dark:text-zinc-500 cursor-not-allowed opacity-70'
                : isAnalyzing
                  ? 'bg-indigo-100 text-indigo-500 cursor-wait'
                  : v.ai_suggestion
                    ? 'bg-emerald-100 text-emerald-600 hover:bg-emerald-200 cursor-pointer shadow-sm'
                    : ['Low', 'Info'].includes(v.severity)
                      ? 'bg-indigo-50 hover:bg-indigo-100 text-indigo-600 cursor-pointer shadow-sm'
                      : 'bg-slate-100 dark:bg-zinc-800 text-slate-400 dark:text-zinc-500 cursor-not-allowed opacity-70'
            }`}
            title={!isKeyReady ? "Valid API Key Required" : v.ai_suggestion ? "Luigi has analyzed this! Click to run again." : "Ask Luigi to verify evidence"}
          >
            <Wand2 size={16} className={isAnalyzing ? "animate-spin" : ""} />
          </button>
        </td>
      </tr>

      {/* DETAILS DRAWER (Visible when Expanded) */}
      {isExpanded && (
        <tr>
          <td colSpan={8} className="p-0 border-b border-slate-200 dark:border-zinc-800">
            <div className="bg-slate-50/80 dark:bg-zinc-900/80 p-6 space-y-6 shadow-inner border-t border-slate-100 dark:border-zinc-800/50">

              {/* Text Areas Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                  <label className="flex items-center gap-1.5 text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2">
                    <AlertCircle size={14} /> Issues Discovered
                  </label>
                  <textarea
                    value={issues}
                    onChange={e => setIssues(e.target.value)}
                    onBlur={() => onUpdateField(v.uuid, 'other_issue', issues)}
                    rows={3}
                    className="w-full bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl p-3 text-sm outline-none focus:ring-2 focus:ring-indigo-500/50 transition-shadow resize-none custom-scrollbar"
                    placeholder="Document any issues encountered during validation..."
                  />
                </div>
                <div>
                  <label className="flex items-center gap-1.5 text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2">
                    <MessageSquareText size={14} /> Pentester Notes
                  </label>
                  <textarea
                    value={notes}
                    onChange={e => setNotes(e.target.value)}
                    onBlur={() => onUpdateField(v.uuid, 'note', notes)}
                    rows={3}
                    className="w-full bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl p-3 text-sm outline-none focus:ring-2 focus:ring-indigo-500/50 transition-shadow resize-none custom-scrollbar"
                    placeholder="General notes and observations..."
                  />
                </div>
                <div>
                  <label className="flex items-center gap-1.5 text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2">
                    <CheckCircle2 size={14} /> Action Taken
                  </label>
                  <textarea
                    value={action}
                    onChange={e => setAction(e.target.value)}
                    onBlur={() => onUpdateField(v.uuid, 'action_taken', action)}
                    rows={3}
                    className="w-full bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl p-3 text-sm outline-none focus:ring-2 focus:ring-indigo-500/50 transition-shadow resize-none custom-scrollbar"
                    placeholder="What action was taken? (e.g., Contacted developer, passed, failed)..."
                  />
                </div>
              </div>

              {/* Luigi Analysis Block */}
              {['Low', 'Info'].includes(v.severity) && (
                <div className={`p-4 rounded-xl border ${v.ai_suggestion ? 'bg-indigo-50/50 dark:bg-indigo-900/10 border-indigo-100 dark:border-indigo-900/30' : 'bg-white dark:bg-zinc-950 border-slate-200 dark:border-zinc-800 border-dashed'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <label className="flex items-center gap-2 text-xs font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">
                      <Wand2 size={14} /> Luigi Verification Analysis
                    </label>
                    {isAnalyzing && <span className="text-xs text-indigo-500 font-medium animate-pulse">Analyzing evidence...</span>}
                  </div>

                  {v.ai_suggestion ? (
                    <p className="text-sm text-slate-700 dark:text-zinc-300 leading-relaxed">
                      {v.ai_suggestion}
                    </p>
                  ) : (
                    <p className="text-sm text-slate-400 dark:text-zinc-600 italic">
                      No AI analysis has been run for this finding yet. Click the wand icon to request verification.
                    </p>
                  )}
                </div>
              )}

            </div>
          </td>
        </tr>
      )}
    </>
  );
};

// --- MAIN PAGE VIEW ---
export default function ValidatingVulnsView() {
  const { currentUser } = useAppContext();

  // Key Validation States
  const [isKeyValid, setIsKeyValid] = useState<boolean | null>(null);
  const [isValidatingKey, setIsValidatingKey] = useState(false);
  const [isKeyModalOpen, setIsKeyModalOpen] = useState(false);

  const [vulns, setVulns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  // Filter States
  const [filterSeverity, setFilterSeverity] = useState<string>('ALL');
  const [filterOrganization, setFilterOrganization] = useState<string>('ALL');
  const [filterTeam, setFilterTeam] = useState<string>('ALL');

  // Sort States
  type SortField = 'id' | 'severity' | 'validating_team' | 'need_credentials' | 'need_vpn';
  const [sortField, setSortField] = useState<SortField | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  // Pagination States
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);

  useEffect(() => {
    if (currentUser?.has_kiss24_key) {
      setIsValidatingKey(true);
      axios.get('/api/users/me/kiss24-key/validate')
        .then(res => setIsKeyValid(res.data.is_valid))
        .catch(() => setIsKeyValid(false))
        .finally(() => setIsValidatingKey(false));
    } else if (!currentUser?.has_kiss24_key) {
      setIsKeyValid(false);
    }
  }, [currentUser?.has_kiss24_key]);

  // Derived Boolean
  const isKeyReady = currentUser?.has_kiss24_key && isKeyValid !== false;

  const loadLocalData = async () => {
    try {
      const res = await axios.get('/api/kiss24/validating-vulns');
      setVulns(res.data);
    } catch (err) {
      toast.error("Failed to load local validation data");
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    const toastId = toast.loading("Syncing with Keep Secure 24...");
    try {
      const res = await axios.post('/api/kiss24/validating-vulns/sync');
      setVulns(res.data);
      toast.success("Validation queue synced!", { id: toastId });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Sync failed", { id: toastId });
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    loadLocalData();

    const handleWebSocketRefresh = () => {
      loadLocalData();
    };

    window.addEventListener('refresh_test_data', handleWebSocketRefresh);

    return () => {
      window.removeEventListener('refresh_test_data', handleWebSocketRefresh);
    };
  }, []);

  const uniqueOrganizations = useMemo(() => {
    const orgs = new Set<string>();
    vulns.forEach(v => {
      if (v.organization && v.organization !== 'Unknown') orgs.add(v.organization);
    });
    return Array.from(orgs).sort();
  }, [vulns]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const processedVulns = useMemo(() => {
    let result = [...vulns];
    if (filterSeverity !== 'ALL') result = result.filter(v => (v.severity || '').toLowerCase() === filterSeverity.toLowerCase());
    if (filterOrganization !== 'ALL') result = result.filter(v => v.organization === filterOrganization);
    if (filterTeam !== 'ALL') result = result.filter(v => v.validating_team === filterTeam);

    if (sortField) {
      const severityRank: Record<string, number> = { 'critical': 5, 'high': 4, 'medium': 3, 'low': 2, 'info': 1 };
      result.sort((a, b) => {
        let valA = a[sortField];
        let valB = b[sortField];

        if (sortField === 'severity') {
          valA = severityRank[(a.severity || '').toLowerCase()] || 0;
          valB = severityRank[(b.severity || '').toLowerCase()] || 0;
        }
        if (typeof valA === 'boolean') { valA = valA ? 1 : 0; valB = valB ? 1 : 0; }
        if (typeof valA === 'string') { valA = valA.toLowerCase(); valB = (valB || '').toLowerCase(); }

        if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
        if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
        return 0;
      });
    }
    return result;
  }, [vulns, filterSeverity, filterOrganization, filterTeam, sortField, sortDirection]);

  useEffect(() => { setCurrentPage(1); }, [filterSeverity, filterOrganization, filterTeam, pageSize]);

  const totalItems = processedVulns.length;
  const totalPages = Math.ceil(totalItems / pageSize) || 1;
  const paginatedVulns = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return processedVulns.slice(start, start + pageSize);
  }, [processedVulns, currentPage, pageSize]);

  const handleUpdateField = async (uuid: string, field: string, value: any) => {
    setVulns(prev => prev.map(v => v.uuid === uuid ? { ...v, [field]: value } : v));
    const vulnToUpdate = vulns.find(v => v.uuid === uuid);
    if (!vulnToUpdate) return;

    try {
      await axios.put(`/api/kiss24/validating-vulns/${uuid}`, { ...vulnToUpdate, [field]: value });
    } catch (err) {
      toast.error("Failed to save field");
      setVulns(prev => prev.map(v => v.uuid === uuid ? { ...v, [field]: vulnToUpdate[field] } : v));
    }
  };

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) return <ArrowUpDown size={13} className="text-slate-400 opacity-50 group-hover:opacity-100 transition-opacity" />;
    return sortDirection === 'asc' ? <ArrowUp size={13} className="text-indigo-500" /> : <ArrowDown size={13} className="text-indigo-500" />;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 flex flex-col items-center justify-center gap-3">
        <RefreshCw className="animate-spin text-indigo-500" size={32} />
        <p className="text-sm font-bold text-slate-500">Loading Validation Queue...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100">
      <TopNav />
      <div className="pt-28 pb-12 px-6 w-full mx-auto">

        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <ShieldAlert className="text-indigo-500" /> Retest Validation Queue
            </h1>
            <p className="text-sm text-slate-500 mt-1">Live reconciliation between Keep Secure 24 and local workspace data.</p>
          </div>
          <button
            onClick={handleSync}
            disabled={!isKeyReady || syncing}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-colors shadow-sm disabled:opacity-70 disabled:cursor-not-allowed cursor-pointer text-sm"
          >
            <RefreshCw size={16} className={syncing ? "animate-spin" : ""} />
            {syncing ? "Syncing API..." : "Sync Keep Secure 24"}
          </button>
        </div>
        {/* --- BANNER SECTION --- */}
        {!currentUser?.has_kiss24_key && (
          <div className="bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/30 p-4 rounded-xl flex flex-col sm:flex-row items-center justify-between gap-4 mb-6 shadow-sm">
            <div className="flex items-center gap-3 text-red-800 dark:text-red-300">
              <AlertCircle className="shrink-0" size={24} />
              <div className="text-sm">
                <strong className="block mb-0.5">Missing Personal API Key</strong>
                You must configure your Keep Secure 24 API key before you can interact with the external platform.
              </div>
            </div>
            <button onClick={() => setIsKeyModalOpen(true)} className="w-full sm:w-auto shrink-0 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-lg transition-colors shadow-md">
              Configure Key
            </button>
          </div>
        )}

        {currentUser?.has_kiss24_key && isKeyValid === false && !isValidatingKey && (
          <div className="bg-orange-50 dark:bg-orange-900/10 border border-orange-200 dark:border-orange-900/30 p-4 rounded-xl flex flex-col sm:flex-row items-center justify-between gap-4 mb-6 shadow-sm">
            <div className="flex items-center gap-3 text-orange-800 dark:text-orange-300">
              <AlertCircle className="shrink-0" size={24} />
              <div className="text-sm">
                <strong className="block mb-0.5">Invalid or Expired API Key</strong>
                Your Keep Secure 24 API key was rejected by the server. It may have expired or been revoked.
              </div>
            </div>
            <button onClick={() => setIsKeyModalOpen(true)} className="w-full sm:w-auto shrink-0 px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white text-xs font-bold rounded-lg transition-colors shadow-md">
              Reset Key
            </button>
          </div>
        )}
        {/* FILTER BAR */}
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 mb-6 shadow-sm flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase tracking-wider mr-1">
              <Filter size={14} /> Filters:
            </div>
            <select value={filterSeverity} onChange={(e) => setFilterSeverity(e.target.value)} className="bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl px-3 py-1.5 text-xs font-medium outline-none focus:ring-2 focus:ring-indigo-500">
              <option value="ALL">All Severities</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
              <option value="Info">Info</option>
            </select>
            <select value={filterOrganization} onChange={(e) => setFilterOrganization(e.target.value)} className="bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl px-3 py-1.5 text-xs font-medium outline-none focus:ring-2 focus:ring-indigo-500">
              <option value="ALL">All Organizations</option>
              {uniqueOrganizations.map(org => <option key={org} value={org}>{org}</option>)}
            </select>
            <select value={filterTeam} onChange={(e) => setFilterTeam(e.target.value)} className="bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl px-3 py-1.5 text-xs font-medium outline-none focus:ring-2 focus:ring-indigo-500">
              <option value="ALL">All Teams</option>
              <option value="DevoTeam">DevoTeam</option>
              <option value="Gost">Gost</option>
            </select>
            {(filterSeverity !== 'ALL' || filterOrganization !== 'ALL' || filterTeam !== 'ALL') && (
              <button onClick={() => { setFilterSeverity('ALL'); setFilterOrganization('ALL'); setFilterTeam('ALL'); }} className="text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:underline px-2 py-1">
                Reset Filters
              </button>
            )}
          </div>
          <div className="text-xs font-medium text-slate-500">
            Showing <strong className="text-slate-800 dark:text-zinc-200">{totalItems}</strong> matching vulnerabilities
          </div>
        </div>

        {/* TABLE */}
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="bg-slate-50 dark:bg-zinc-950/50 border-b border-slate-200 dark:border-zinc-800">
                <tr>
                  <th className="p-4 w-10"></th> {/* Expand Toggle Column */}
                  <th onClick={() => handleSort('id')} className="p-4 font-bold cursor-pointer select-none group hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors">
                    <div className="flex items-center gap-1.5">Vuln ID {renderSortIcon('id')}</div>
                  </th>
                  <th onClick={() => handleSort('severity')} className="p-4 font-bold cursor-pointer select-none group hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors">
                    <div className="flex items-center gap-1.5">Severity {renderSortIcon('severity')}</div>
                  </th>
                  <th className="p-4 font-bold">Target</th>
                  <th onClick={() => handleSort('validating_team')} className="p-4 font-bold cursor-pointer select-none group hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors">
                    <div className="flex items-center gap-1.5">Team {renderSortIcon('validating_team')}</div>
                  </th>
                  <th onClick={() => handleSort('need_credentials')} className="p-4 font-bold text-center cursor-pointer select-none group hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors">
                    <div className="flex items-center justify-center gap-1.5">Creds {renderSortIcon('need_credentials')}</div>
                  </th>
                  <th onClick={() => handleSort('need_vpn')} className="p-4 font-bold text-center cursor-pointer select-none group hover:bg-slate-100 dark:hover:bg-zinc-800/50 transition-colors">
                    <div className="flex items-center justify-center gap-1.5">VPN {renderSortIcon('need_vpn')}</div>
                  </th>
                  <th className="p-4 font-bold text-center">AI Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                {paginatedVulns.map(v => (
                  <VulnRow key={v.uuid} v={v} onUpdateField={handleUpdateField} isKeyReady={isKeyReady} />
                ))}
              </tbody>
            </table>
            {paginatedVulns.length === 0 && !syncing && (
              <div className="text-center py-12 text-slate-500 font-medium">No vulnerabilities match your current filters.</div>
            )}
          </div>

          {/* PAGINATION FOOTER */}
          <div className="p-4 bg-slate-50/50 dark:bg-zinc-950/50 border-t border-slate-200 dark:border-zinc-800 flex flex-col sm:flex-row justify-between items-center gap-4 text-xs font-medium">
            <div className="flex items-center gap-2">
              <span className="text-slate-500">Rows per page:</span>
              <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))} className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-lg px-2 py-1 outline-none font-bold">
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
            <div className="text-slate-500">
              Page <strong className="text-slate-800 dark:text-zinc-200">{currentPage}</strong> of <strong className="text-slate-800 dark:text-zinc-200">{totalPages}</strong>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))} disabled={currentPage === 1} className="p-1.5 rounded-lg border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-slate-700 dark:text-zinc-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" title="Previous Page">
                <ChevronLeft size={16} />
              </button>
              <button onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))} disabled={currentPage === totalPages || totalPages === 0} className="p-1.5 rounded-lg border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-slate-700 dark:text-zinc-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" title="Next Page">
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>
      <Kiss24KeyModal isOpen={isKeyModalOpen} onClose={() => setIsKeyModalOpen(false)} />
    </div>
  );
}