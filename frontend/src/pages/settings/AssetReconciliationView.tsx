import React, { useState, useMemo } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import {
  GitMerge, RefreshCw, Check, Search, ShieldCheck,
  Building2, ExternalLink, ChevronLeft,
  ChevronRight, ArrowUpDown, Layers, Database
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface Suggestion {
  kiss24_uuid: string;
  kiss24_name: string;
  score: number;
}

interface Candidate {
  mario_raw_asset_id: string;
  mario_name: string;
  snow_number: string;
  country_name: string;
  org_uuid: string;
  top_suggestions: Suggestion[];
}

type CandidateStatusFilter = 'ALL' | 'HAS_CANDIDATES' | 'NO_CANDIDATES' | 'HIGH_CONFIDENCE' | 'LOW_CONFIDENCE';
type SortOption = 'SCORE_DESC' | 'SCORE_ASC' | 'NAME_ASC' | 'NAME_DESC' | 'COUNTRY_ASC';

export default function AssetReconciliationView() {
  const navigate = useNavigate();
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasScanned, setHasScanned] = useState(false);

  // Filter States
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCountry, setFilterCountry] = useState('ALL');
  const [filterCandidateStatus, setFilterCandidateStatus] = useState<CandidateStatusFilter>('ALL');

  // Sort State
  const [sortOption, setSortOption] = useState<SortOption>('SCORE_DESC');

  // Pagination States
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(25);

  const [selectedMatches, setSelectedMatches] = useState<Record<string, string>>({});
  const [linkingState, setLinkingState] = useState<Record<string, boolean>>({});

  // --- Bulk Selection States ---
  const [selectedAssets, setSelectedAssets] = useState<Set<string>>(new Set());
  const [isBulkLinking, setIsBulkLinking] = useState(false);

  const toggleAssetSelection = (marioId: string) => {
    const newSet = new Set(selectedAssets);
    if (newSet.has(marioId)) newSet.delete(marioId);
    else newSet.add(marioId);
    setSelectedAssets(newSet);
  };

  const toggleAllAssets = () => {
    if (selectedAssets.size === paginatedCandidates.length) {
      setSelectedAssets(new Set());
    } else {
      const newSet = new Set(selectedAssets);
      paginatedCandidates.forEach(c => {
        if (c.top_suggestions.length > 0) newSet.add(c.mario_raw_asset_id);
      });
      setSelectedAssets(newSet);
    }
  };

  const handleBulkApprove = async () => {
    if (selectedAssets.size === 0) return;
    setIsBulkLinking(true);
    const toastId = toast.loading(`Linking ${selectedAssets.size} assets to Keep Secure 24...`);

    const assetsToLink = Array.from(selectedAssets).map(marioId => {
      const candidate = candidates.find(c => c.mario_raw_asset_id === marioId)!;
      return {
        mario_raw_asset_id: marioId,
        kiss24_uuid: selectedMatches[marioId],
        snow_number: candidate.snow_number
      };
    }).filter(a => a.kiss24_uuid);

    try {
      const res = await axios.post('/api/kiss24/reconcile-asset/bulk', { assets: assetsToLink });
      if (res.data.status === "Partial") toast.error(res.data.message, { id: toastId, duration: 8000 });
      else toast.success(res.data.message, { id: toastId });

      setCandidates(prev => prev.filter(c => !selectedAssets.has(c.mario_raw_asset_id)));
      setSelectedAssets(new Set());
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Bulk linking failed.", { id: toastId });
    } finally {
      setIsBulkLinking(false);
    }
  };

  const loadCandidates = async () => {
    setLoading(true);
    try {
      const res = await axios.get('/api/kiss24/reconciliation-candidates?limit=0');
      setCandidates(res.data);

      const initialSelections: Record<string, string> = {};
      res.data.forEach((item: Candidate) => {
        if (item.top_suggestions && item.top_suggestions.length > 0) {
          initialSelections[item.mario_raw_asset_id] = item.top_suggestions[0].kiss24_uuid;
        }
      });
      setSelectedMatches(initialSelections);
      setHasScanned(true);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to load reconciliation candidates.");
    } finally {
      setLoading(false);
    }
  };

  const uniqueCountries = useMemo(() => {
    const countries = new Set<string>();
    candidates.forEach(c => {
      if (c.country_name) countries.add(c.country_name);
    });
    return Array.from(countries).sort();
  }, [candidates]);

  const processedCandidates = useMemo(() => {
    let result = [...candidates];

    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      result = result.filter(item =>
        item.mario_name.toLowerCase().includes(term) ||
        item.snow_number.toLowerCase().includes(term)
      );
    }

    if (filterCountry !== 'ALL') {
      result = result.filter(item => item.country_name === filterCountry);
    }

    if (filterCandidateStatus === 'HAS_CANDIDATES') {
      result = result.filter(item => item.top_suggestions.length > 0);
    } else if (filterCandidateStatus === 'NO_CANDIDATES') {
      result = result.filter(item => item.top_suggestions.length === 0);
    } else if (filterCandidateStatus === 'HIGH_CONFIDENCE') {
      result = result.filter(item => item.top_suggestions.length > 0 && item.top_suggestions[0].score >= 80);
    } else if (filterCandidateStatus === 'LOW_CONFIDENCE') {
      result = result.filter(item => item.top_suggestions.length > 0 && item.top_suggestions[0].score < 50);
    }

    result.sort((a, b) => {
      const scoreA = a.top_suggestions[0]?.score || 0;
      const scoreB = b.top_suggestions[0]?.score || 0;

      switch (sortOption) {
        case 'SCORE_DESC': return scoreB - scoreA;
        case 'SCORE_ASC': return scoreA - scoreB;
        case 'NAME_ASC': return a.mario_name.localeCompare(b.mario_name);
        case 'NAME_DESC': return b.mario_name.localeCompare(a.mario_name);
        case 'COUNTRY_ASC': return a.country_name.localeCompare(b.country_name);
        default: return 0;
      }
    });

    return result;
  }, [candidates, searchTerm, filterCountry, filterCandidateStatus, sortOption]);

  React.useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, filterCountry, filterCandidateStatus, sortOption, pageSize]);

  const totalItems = processedCandidates.length;
  const totalPages = Math.ceil(totalItems / pageSize) || 1;
  const paginatedCandidates = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return processedCandidates.slice(start, start + pageSize);
  }, [processedCandidates, currentPage, pageSize]);

  const handleApproveMatch = async (candidate: Candidate) => {
    const selectedKiss24Uuid = selectedMatches[candidate.mario_raw_asset_id];
    if (!selectedKiss24Uuid) {
      return toast.error("Please select a KISS24 asset to match.");
    }

    setLinkingState(prev => ({ ...prev, [candidate.mario_raw_asset_id]: true }));
    const toastId = toast.loading(`Linking ${candidate.snow_number} to Keep Secure 24...`);

    try {
      await axios.post('/api/kiss24/reconcile-asset', {
        mario_raw_asset_id: candidate.mario_raw_asset_id,
        kiss24_uuid: selectedKiss24Uuid,
        snow_number: candidate.snow_number
      });

      toast.success(`Successfully linked ${candidate.snow_number}!`, { id: toastId });
      setCandidates(prev => prev.filter(c => c.mario_raw_asset_id !== candidate.mario_raw_asset_id));
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Linking failed.", { id: toastId });
    } finally {
      setLinkingState(prev => ({ ...prev, [candidate.mario_raw_asset_id]: false }));
    }
  };

  const getScoreBadge = (score: number) => {
    if (score >= 80) return <span className="px-2 py-0.5 rounded text-[10px] font-black bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">{score}% Match</span>;
    if (score >= 50) return <span className="px-2 py-0.5 rounded text-[10px] font-black bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 border border-amber-200 dark:border-amber-800">{score}% Match</span>;
    return <span className="px-2 py-0.5 rounded text-[10px] font-black bg-slate-100 text-slate-600 dark:bg-zinc-800 dark:text-zinc-400 border border-slate-200 dark:border-zinc-700">{score}% Match</span>;
  };

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">
      {/* Toolbar Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-black flex items-center gap-2 text-slate-900 dark:text-zinc-100">
            <GitMerge className="text-indigo-500" /> Asset Reconciliation Hub
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Reconcile ServiceNow-synced Mario raw assets with Keep Secure 24 assets within the same country.
          </p>
        </div>
        <button onClick={loadCandidates} disabled={loading} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-70 text-white font-bold rounded-xl transition-colors shadow-sm text-sm cursor-pointer">
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          {loading ? "Scanning..." : hasScanned ? "Re-Scan Databases" : "Start Asset Scan"}
        </button>
      </div>

      {/* Filter & Order Bar */}
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 mb-6 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-wrap flex-1">
            <div className="relative flex-1 min-w-[200px] max-w-xs">
              <Search className="absolute left-3.5 top-2.5 text-slate-400" size={16} />
              <input type="text" value={searchTerm} onChange={e => setSearchTerm(e.target.value)} disabled={!hasScanned} placeholder="Search asset name or SNow ID..." className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl pl-9 pr-4 py-1.5 text-xs outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50" />
            </div>
            <select value={filterCountry} onChange={e => setFilterCountry(e.target.value)} disabled={!hasScanned} className="bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl px-3 py-1.5 text-xs font-bold outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50">
              <option value="ALL">All Countries / Orgs</option>
              {uniqueCountries.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={filterCandidateStatus} onChange={e => setFilterCandidateStatus(e.target.value as CandidateStatusFilter)} disabled={!hasScanned} className="bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl px-3 py-1.5 text-xs font-bold outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50">
              <option value="ALL">All Candidate Statuses</option>
              <option value="HAS_CANDIDATES">Has Candidates</option>
              <option value="NO_CANDIDATES">No Candidates Found</option>
              <option value="HIGH_CONFIDENCE">High Confidence (≥80%)</option>
              <option value="LOW_CONFIDENCE">Needs Review (&lt;50%)</option>
            </select>
            {(searchTerm || filterCountry !== 'ALL' || filterCandidateStatus !== 'ALL') && (
              <button onClick={() => { setSearchTerm(''); setFilterCountry('ALL'); setFilterCandidateStatus('ALL'); }} className="text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:underline px-2 py-1">
                Reset Filters
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1">
              <ArrowUpDown size={13} /> Order By:
            </span>
            <select value={sortOption} onChange={e => setSortOption(e.target.value as SortOption)} disabled={!hasScanned} className="bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl px-3 py-1.5 text-xs font-bold outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50">
              <option value="SCORE_DESC">Top Match Score (High → Low)</option>
              <option value="SCORE_ASC">Top Match Score (Low → High)</option>
              <option value="NAME_ASC">Asset Name (A → Z)</option>
              <option value="NAME_DESC">Asset Name (Z → A)</option>
              <option value="COUNTRY_ASC">Country Name</option>
            </select>
          </div>
        </div>
        <div className="text-xs font-medium text-slate-500 border-t border-slate-100 dark:border-zinc-800/80 pt-2 flex justify-between items-center">
          <span>Showing <strong className="text-slate-800 dark:text-zinc-200">{totalItems}</strong> matching raw assets</span>
          <span>Total Unmatched Pool: <strong className="text-slate-800 dark:text-zinc-200">{candidates.length}</strong></span>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-sm overflow-hidden min-h-[400px]">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 text-slate-500">
            <RefreshCw className="animate-spin text-indigo-500 mb-4" size={32} />
            <h3 className="font-bold text-slate-700 dark:text-zinc-300">Scanning Databases...</h3>
            <p className="text-xs mt-1">Fetching and comparing assets from Keep Secure 24. This may take a moment.</p>
          </div>
        ) : !hasScanned ? (
          <div className="flex flex-col items-center justify-center py-24 text-slate-500">
            <Database size={40} className="text-indigo-400 mb-4 opacity-80" />
            <h3 className="font-bold text-slate-700 dark:text-zinc-300 text-lg">Ready to Reconcile</h3>
            <p className="text-sm mt-1 mb-6">Click the scan button to cross-reference Mario and Keep Secure 24 assets.</p>
            <button onClick={loadCandidates} className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-colors shadow-sm text-sm">
              Start Asset Scan
            </button>
          </div>
        ) : (
          <>
            {paginatedCandidates.length > 0 && (
              <div className="flex items-center justify-between p-3 bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800">
                <label className="flex items-center gap-3 cursor-pointer group ml-2">
                  <input
                    type="checkbox"
                    checked={paginatedCandidates.length > 0 && selectedAssets.size === paginatedCandidates.filter(c => c.top_suggestions.length > 0).length}
                    onChange={toggleAllAssets}
                    className="w-4 h-4 rounded text-indigo-600 border-slate-300 focus:ring-indigo-500 cursor-pointer"
                  />
                  <span className="text-xs font-bold text-slate-700 dark:text-zinc-300 select-none group-hover:text-indigo-600 transition-colors">
                    Select Page ({selectedAssets.size} selected)
                  </span>
                </label>
                {selectedAssets.size > 0 && (
                  <button
                    onClick={handleBulkApprove}
                    disabled={isBulkLinking}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl transition-colors flex items-center gap-2 shadow-sm disabled:opacity-50"
                  >
                    {isBulkLinking ? <RefreshCw size={14} className="animate-spin" /> : <Layers size={14} />}
                    Confirm {selectedAssets.size} Matches
                  </button>
                )}
              </div>
            )}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-slate-50 dark:bg-zinc-950/50 border-b border-slate-200 dark:border-zinc-800">
                  <tr>
                    <th className="p-4 font-bold">Mario Raw Asset (ServiceNow)</th>
                    <th className="p-4 font-bold">Market / Region</th>
                    <th className="p-4 font-bold w-96">Keep Secure 24 Match Candidate</th>
                    <th className="p-4 font-bold text-center">Match Score</th>
                    <th className="p-4 font-bold text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                  {paginatedCandidates.map(candidate => {
                    const selectedUuid = selectedMatches[candidate.mario_raw_asset_id] || '';
                    const selectedSuggestion = candidate.top_suggestions.find(s => s.kiss24_uuid === selectedUuid);
                    const isLinking = linkingState[candidate.mario_raw_asset_id];

                    return (
                      <tr key={candidate.mario_raw_asset_id} className="hover:bg-slate-50/50 dark:hover:bg-zinc-800/30 transition-colors">
                        <td className="p-4 flex items-start gap-3">
                          <input
                            type="checkbox"
                            checked={selectedAssets.has(candidate.mario_raw_asset_id)}
                            onChange={() => toggleAssetSelection(candidate.mario_raw_asset_id)}
                            disabled={candidate.top_suggestions.length === 0}
                            className="mt-1 shrink-0 w-4 h-4 rounded text-indigo-600 border-slate-300 focus:ring-indigo-500 cursor-pointer disabled:opacity-30"
                          />
                          <div>
                            <div className="font-bold text-slate-900 dark:text-zinc-100">{candidate.mario_name}</div>
                            <div className="font-mono text-xs text-indigo-600 dark:text-indigo-400 mt-0.5">
                              SNow ID: {candidate.snow_number}
                            </div>
                          </div>
                        </td>
                        <td className="p-4">
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 text-xs font-bold">
                            <Building2 size={12} /> {candidate.country_name}
                          </span>
                        </td>
                        <td className="p-4">
                          {candidate.top_suggestions.length > 0 ? (
                            <div className="flex items-center gap-2">
                              <select
                                value={selectedUuid}
                                onChange={e => setSelectedMatches(prev => ({ ...prev, [candidate.mario_raw_asset_id]: e.target.value }))}
                                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl px-3 py-2 text-xs font-medium outline-none focus:ring-2 focus:ring-indigo-500"
                              >
                                {candidate.top_suggestions.map(s => (
                                  <option key={s.kiss24_uuid} value={s.kiss24_uuid}>
                                    {s.score}% - {s.kiss24_name}
                                  </option>
                                ))}
                              </select>

                              {selectedUuid && (
                                <a
                                  href={`https://randstad.eu.vulnmanager.com/assets/${selectedUuid}/show`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="p-2 text-blue-600 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/40 border border-blue-200 dark:border-blue-900/50 rounded-xl transition-colors shrink-0"
                                  title="Inspect asset in Keep Secure 24"
                                >
                                  <ExternalLink size={16} />
                                </a>
                              )}
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400 italic">No candidates found in this region</span>
                          )}
                        </td>
                        <td className="p-4 text-center">
                          {selectedSuggestion ? getScoreBadge(selectedSuggestion.score) : '-'}
                        </td>
                        <td className="p-4 text-right">
                          <button
                            onClick={() => handleApproveMatch(candidate)}
                            disabled={isLinking || !selectedUuid}
                            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-sm transition-colors inline-flex items-center gap-1.5 cursor-pointer"
                          >
                            {isLinking ? <RefreshCw size={14} className="animate-spin" /> : <Check size={14} />}
                            Confirm Match
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {paginatedCandidates.length === 0 && (
                <div className="text-center py-16">
                  <ShieldCheck size={40} className="mx-auto text-emerald-500 mb-3 opacity-80" />
                  <h3 className="font-bold text-slate-700 dark:text-zinc-300">No Assets Match Your Filters</h3>
                  <p className="text-xs text-slate-500 mt-1">Try resetting your search, candidate status, or country filters.</p>
                </div>
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
                <button onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))} disabled={currentPage === 1} className="p-1.5 rounded-lg border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-slate-700 dark:text-zinc-300 disabled:opacity-40 hover:bg-slate-100 transition-colors">
                  <ChevronLeft size={16} />
                </button>
                <button onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))} disabled={currentPage === totalPages || totalPages === 0} className="p-1.5 rounded-lg border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-slate-700 dark:text-zinc-300 disabled:opacity-40 hover:bg-slate-100 transition-colors">
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}