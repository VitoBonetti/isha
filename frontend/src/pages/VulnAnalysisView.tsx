import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import TopNav from "../components/TopNav";
import { ChevronLeft, RefreshCw, FileText, AlertTriangle } from "lucide-react";
import toast, { Toaster } from "react-hot-toast";

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import rehypeRaw from 'rehype-raw';

export default function VulnAnalysisView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchAnalysis = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`/api/tests/${id}/analysis`);
      setData(res.data);
    } catch (error: any) {
      if (error.response?.status === 404) {
        toast.error("No analysis found. Please generate one first.");
        navigate(`/tests/${id}`);
      } else {
        toast.error("Failed to load analysis.");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalysis();

    let interval: NodeJS.Timeout;
    if (data?.status === 'PENDING') {
      interval = setInterval(async () => {
        try {
          const res = await axios.get(`/api/tests/${id}/analysis`);
          if (res.data.status !== 'PENDING') {
            setData(res.data);
            clearInterval(interval);
            if (res.data.status === 'COMPLETED') {
              toast.success("Analysis complete!");
            }
          }
        } catch (error) {
          console.error("Polling error:", error);
        }
      }, 3000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [id, data?.status]);

  const handleRegenerate = async () => {
    const toastId = toast.loading("Queuing new analysis...");
    try {
      await axios.post(`/api/tests/${id}/analysis`);
      toast.dismiss(toastId);
      toast.success("Analysis started! You will be notified when ready.");
      setData((prev: any) => ({ ...prev, status: 'PENDING' }));
    } catch (error) {
      toast.dismiss(toastId);
      toast.error("Failed to start analysis.");
    }
  };

  // Preprocesses text to fix HTML/Markdown transitions and format metadata
  const cleanAnalysisText = (text: string) => {
    if (!text) return "";
    return text
      // 1. Remove <figure class="image">...</figure> image blocks
      .replace(/<figure[^>]*>[\s\S]*?<\/figure>/gi, "")
      // 2. Remove standalone <img> tags
      .replace(/<img[^>]*>/gi, "")
      // 3. Ensure HTML block closing tags are followed by blank lines so Markdown parses correctly
      .replace(/(<\/(?:ul|ol|p|h[1-6]|div|blockquote)>)/gi, "$1\n\n")
      // 4. Force metadata fields onto their own bolded lines
      .replace(/\*\*(State|Attachments|Published At|Created By):\*\*/g, "\n\n**$1:**")
      // 5. NEW: Strip hardcoded black/dark text colors safely without breaking HTML!
      .replace(/color:\s*(?:#000000|#000|black|#333333|#333|#222222|#222)\s*;?/gi, "");
  };

  if (loading && !data) {
    return <div className="min-h-screen flex items-center justify-center dark:bg-zinc-950 dark:text-zinc-100">Loading Analysis...</div>;
  }

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100 bg-slate-50 dark:bg-[#09090b]">
      <TopNav />
      <Toaster position="bottom-right" />

      {/* Expanded Container Width to 1600px */}
      <div className="pt-28 md:pt-32 pb-12 px-4 md:px-8 w-full max-w-[1600px] mx-auto">
        <div className="flex justify-between items-center mb-6">
          <button onClick={() => navigate(`/tests/${id}`)} className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white transition-colors font-medium">
            <ChevronLeft size={16} /> Back to Test Details
          </button>
          <button onClick={handleRegenerate} className="flex items-center gap-2 px-4 py-2 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-lg text-sm font-bold transition-colors shadow-sm border border-blue-200 dark:border-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-900/40">
            <RefreshCw size={14} /> Regenerate
          </button>
        </div>

        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-sm overflow-hidden">
          <div className="p-6 border-b border-slate-100 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-950/50">
            <h1 className="text-2xl font-black flex items-center gap-2">
              <FileText className="text-blue-500" /> AI Vulnerability Analysis
            </h1>
            {data?.timestamp && (
              <div className="text-sm text-slate-500 mt-2">
                Generated on {new Date(data.timestamp).toLocaleString()}
              </div>
            )}
          </div>

          <div className="p-6 md:p-10">
            {data?.status === 'PENDING' ? (
              <div className="flex flex-col items-center justify-center py-12 text-slate-500 animate-pulse">
                <RefreshCw size={32} className="mb-4 animate-spin text-blue-500" />
                <p className="font-bold">Analysis is currently being generated...</p>
                <p className="text-sm mt-2">You will be notified when it is complete.</p>
              </div>
            ) : data?.status === 'FAILED' ? (
              <div className="flex flex-col items-center justify-center py-12 text-red-500">
                <AlertTriangle size={32} className="mb-4" />
                <p className="font-bold">The previous analysis attempt failed.</p>
                <button onClick={handleRegenerate} className="mt-4 underline font-bold">Try Again</button>
              </div>
            ) : (
              <div className="prose prose-slate dark:prose-invert max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  rehypePlugins={[rehypeRaw]}
                  components={{
                    // Custom Horizontal Rule with ample vertical spacing
                    hr: () => (
                      <div className="my-14 border-t-2 border-slate-200 dark:border-zinc-800" />
                    ),
                    // Responsive Code Blocks
                    pre: ({ node, ...props }) => (
                      <pre className="p-4 rounded-xl bg-slate-900 text-slate-100 overflow-x-auto my-4 text-xs md:text-sm font-mono border border-slate-800" {...props} />
                    )
                  }}
                >
                  {cleanAnalysisText(data?.analysis_text || "")}
                </ReactMarkdown>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}