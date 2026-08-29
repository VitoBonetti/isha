import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import toast, { Toaster } from 'react-hot-toast';
import { Search, Filter, ChevronsUpDown, ChevronUp, ChevronDown, FileText, ExternalLink, Files, Clock } from "lucide-react";

export default function DocumentsView() {
  const [documents, setDocuments] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Data Params
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [filterService, setFilterService] = useState("");
  const [totalPages, setTotalPages] = useState(1);

  // Sorting
  const [sortBy, setSortBy] = useState("synced_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  useEffect(() => {
    axios.get('/api/services/').then(res => setServices(res.data)).catch(() => {});
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => { setDebouncedSearch(searchTerm); setPage(1); }, 500);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => {
    fetchDocuments();
  }, [page, debouncedSearch, filterService, sortBy, sortDir]);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const params: any = { page, limit: 20, sort_by: sortBy, sort_dir: sortDir };
      if (debouncedSearch) params.search = debouncedSearch;
      if (filterService) params.service_lane_id = filterService;

      const res = await axios.get("/api/documents/", { params });
      setDocuments(res.data.items);
      setTotalPages(Math.ceil(res.data.total_count / 20) || 1);
    } catch (error) {
      toast.error("Failed to fetch documents");
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (column: string) => {
    if (sortBy === column) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortBy(column); setSortDir("asc"); }
  };

  const SortIcon = ({ column }: { column: string }) => {
    if (sortBy !== column) return <ChevronsUpDown size={14} className="opacity-30" />;
    return sortDir === "asc" ? <ChevronUp size={14} className="text-blue-500" /> : <ChevronDown size={14} className="text-blue-500" />;
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">
      <Toaster position="bottom-right" />

      <h1 className="text-2xl font-extrabold flex items-center gap-2">
        <Files size={28} className="text-blue-500" />
        Document Directory
      </h1>
      <p className="text-slate-500 dark:text-zinc-400 mb-6 md:mb-8 text-sm md:text-base">
        Global index of all synchronized Google Drive files across tests.
      </p>

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-4 items-stretch sm:items-center justify-between bg-white dark:bg-zinc-900 p-4 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm relative">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 flex-1">
          <div className="relative w-full sm:max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input type="text" placeholder="Search file or test name..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="w-full pl-10 pr-4 py-2.5 md:py-2 rounded-lg border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
          </div>
          <select className="w-full sm:w-auto p-2.5 md:p-2 border border-slate-300 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-sm outline-none" value={filterService} onChange={e => {setFilterService(e.target.value); setPage(1);}}>
            <option value="">All Services</option>
            {services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      </div>

      {/* Data Table */}
      <div className="mt-6 bg-white dark:bg-zinc-900 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden w-full">
        {loading ? (
          <div className="p-12 text-center"><div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto"></div><p className="mt-4 text-slate-500 text-sm">Loading documents...</p></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap min-w-[800px]">
              <thead className="bg-slate-50 dark:bg-zinc-800/50 border-b border-slate-200 dark:border-zinc-700">
                <tr>
                  <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("file_name")}><div className="flex items-center gap-2">File Name <SortIcon column="file_name" /></div></th>
                  <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("test_name")}><div className="flex items-center gap-2">Linked Test <SortIcon column="test_name" /></div></th>
                  <th className="p-4 font-semibold text-slate-500 uppercase">Location</th>
                  <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("service")}><div className="flex items-center gap-2">Service Lane <SortIcon column="service" /></div></th>
                  <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("scheduled")}><div className="flex items-center gap-2">Scheduled <SortIcon column="scheduled" /></div></th>
                  <th className="p-4 font-semibold text-slate-500 uppercase cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => handleSort("synced_at")}><div className="flex items-center gap-2"><Clock size={14}/> Synced <SortIcon column="synced_at" /></div></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-zinc-700">
                {documents.map((doc) => (
                  <tr key={doc.doc_id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors">
                    <td className="p-4 max-w-[250px]">
                      <a href={doc.file_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 font-bold text-blue-600 dark:text-blue-400 hover:underline group">
                        <FileText size={16} className="shrink-0 text-slate-400 group-hover:text-blue-500" />
                        <span className="truncate">{doc.file_name}</span>
                        <ExternalLink size={12} className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </a>
                    </td>
                    <td className="p-4 max-w-[200px]">
                      <Link to={`/tests/${doc.test_id}`} className="text-slate-700 dark:text-zinc-300 font-medium hover:text-blue-600 dark:hover:text-blue-400 hover:underline truncate block">
                        {doc.test_name}
                      </Link>
                    </td>
                    <td className="p-4"><span className="font-mono text-xs font-bold text-slate-500">{doc.countries || '--'}</span></td>
                    <td className="p-4"><span className="text-sm font-medium">{doc.service_name}</span></td>
                    <td className="p-4">
                      {doc.start_week && doc.start_year ? (
                        <span className="inline-flex px-2 py-0.5 rounded text-xs font-bold bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400">
                          Wk {doc.start_week}, {doc.start_year}
                        </span>
                      ) : '-'}
                    </td>
                    <td className="p-4 text-slate-500 text-xs">{formatDate(doc.synced_at)}</td>
                  </tr>
                ))}
                {documents.length === 0 && (
                  <tr><td colSpan={6} className="p-8 text-center text-slate-500 font-medium">No documents found matching your criteria.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="px-4 md:px-6 py-4 border-t border-slate-200 dark:border-zinc-700 flex flex-col sm:flex-row justify-between items-center gap-4 sm:gap-0 bg-slate-50 dark:bg-zinc-950/50">
          <span className="text-xs md:text-sm text-slate-500">Page {page} of {totalPages}</span>
          <div className="flex gap-2 w-full sm:w-auto">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium bg-white dark:bg-zinc-900 transition-colors">Prev</button>
            <button onClick={() => setPage(p => p + 1)} disabled={page >= totalPages} className="flex-1 sm:flex-none px-4 py-2 sm:py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-50 text-sm font-medium bg-white dark:bg-zinc-900 transition-colors">Next</button>
          </div>
        </div>
      </div>
    </div>
  );
}