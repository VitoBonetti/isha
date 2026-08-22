import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { X, Send, Eye, Code, BrainCircuit, UploadCloud, AlertCircle, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAppContext } from '../../context/AppContext';

interface Kiss24CreateVulnModalProps {
  isOpen: boolean;
  testId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function Kiss24CreateVulnModal({ isOpen, testId, onClose, onSuccess }: Kiss24CreateVulnModalProps) {
  // Step Management
  const { currentUser } = useAppContext();
  const [step, setStep] = useState<1 | 2>(1);
  const [isDrafting, setIsDrafting] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);

  // Form State
  const [note, setNote] = useState('');
  const [severity, setSeverity] = useState('info');
  const [images, setImages] = useState<{ name: string; base64: string }[]>([]);

  // API Data
  const [vulnTypes, setVulnTypes] = useState<any[]>([]);

  // Step 2 Review State
  const [htmlContent, setHtmlContent] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [selectedType, setSelectedType] = useState('');
  const [selectedContext, setSelectedContext] = useState('');
  const [title, setTitle] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [suggestedCwe, setSuggestedCwe] = useState('');
  const [mitreId, setMitreId] = useState('');
  const [remediationEffort, setRemediationEffort] = useState('Minimal');

  // Add a ref to track the active toast so the websocket can close it
  const draftToastId = useRef<string | null>(null);

  // Fetch Vulnerability Types on mount
  useEffect(() => {
    if (isOpen && vulnTypes.length === 0) {
      axios.get('/api/kiss24/vuln-types').then(res => setVulnTypes(res.data)).catch(console.error);
    }
  }, [isOpen]);

  // Reset state on close
  useEffect(() => {
    if (!isOpen) {
      setStep(1);
      setNote('');
      setSeverity('info'); // Reset to default severity
      setImages([]);
      setHtmlContent('');
      setShowPreview(false);
      setSelectedType('');
      setSelectedContext('');
      setTitle('');
      setSuggestedCwe('');
      setIsAuthenticated(false);
      setMitreId('');
      setRemediationEffort('Minimal');
    }
  }, [isOpen]);

  // --- WEBSOCKET LISTENER FOR LUIGI  ---
  useEffect(() => {
    if (!isOpen || !currentUser) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/board`;
    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.action === 'VULN_DRAFT_READY' && data.email === currentUser?.email) {
          if (draftToastId.current) toast.success("Luigi finished drafting!", { id: draftToastId.current });

          setHtmlContent(data.html);
          setSuggestedCwe(data.suggested_type);
          setStep(2);
          setShowPreview(true);
          setIsDrafting(false);
        }
      } catch (e) { console.error(e); }
    };
    return () => socket.close();
  }, [isOpen, currentUser?.email]);

  if (!isOpen) return null;

  // Handle File Upload to Base64
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const files = Array.from(e.target.files);

    files.forEach(file => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = (reader.result as string).split(',')[1]; // Remove data:image/png;base64, prefix
        setImages(prev => [...prev, { name: file.name, base64: base64String }]);
      };
      reader.readAsDataURL(file);
    });
  };

  // Step 1 -> 2: Draft with Luigi
  const handleDraft = async () => {
    if (!note.trim()) return toast.error("A general note is required for Luigi to draft the finding.");

    setIsDrafting(true);
    draftToastId.current = toast.loading("Luigi is reading and drafting the vulnerability...");

    try {
      // Fire and forget! The WebSocket will handle the rest.
      await axios.post('/api/luigi/draft-vulnerability', { note, severity });
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Luigi failed to receive task.", { id: draftToastId.current });
      setIsDrafting(false);
    }
  };

  // Publish to KISS24
  const handlePublish = async () => {
    if (!selectedType || !selectedContext || !title.trim()) {
      return toast.error("Please select a Vulnerability Type, Context, and provide a Title.");
    }

    setIsPublishing(true);
    const toastId = toast.loading("Publishing to Keep Secure 24...");

    try {
      await axios.post(`/api/kiss24/${testId}/vulnerabilities/publish`, {
        vulnerability_type: selectedType,
        context: selectedContext,
        severity,
        title,
        html: htmlContent,
        authenticated: isAuthenticated,
        images,
        mitre_id: mitreId,
        remediation_effort: remediationEffort
      });
      toast.success("Vulnerability published successfully!", { id: toastId });
      onSuccess();
      onClose();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Publishing failed.", { id: toastId });
    } finally {
      setIsPublishing(false);
    }
  };

  // Auto-fill context and title when a Type is selected
  const handleTypeSelect = (typeId: string) => {
    setSelectedType(typeId);
    const typeObj = vulnTypes.find(v => v.id === typeId);
    if (typeObj) {
      setTitle(typeObj.name);
      if (typeObj.contexts.length === 1) {
        setSelectedContext(typeObj.contexts[0].id);
      } else {
        setSelectedContext(''); // Force them to pick if multiple exist
      }
    }
  };

  return (
    <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in">
      <div className={`bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-2xl w-full flex flex-col transition-all duration-300 ${step === 1 ? 'max-w-2xl' : 'max-w-6xl h-[90vh]'}`}>

        {/* Header */}
        <div className="p-5 border-b border-slate-100 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-900/50 flex justify-between items-center shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-100 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400 rounded-lg">
              <BrainCircuit size={20} />
            </div>
            <div>
              <h2 className="font-black text-lg text-slate-900 dark:text-zinc-100 leading-tight">AI Vulnerability Drafter</h2>
              <p className="text-xs font-medium text-slate-500">Step {step} of 2: {step === 1 ? 'Input & Analysis' : 'Review & Publish'}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-500 rounded-full transition-colors">
            <X size={16} />
          </button>
        </div>

        {/* STEP 1: Input */}
        {step === 1 && (
          <div className="p-6 space-y-5 flex-1 overflow-y-auto">
            <div className="bg-indigo-50 dark:bg-indigo-900/10 border border-indigo-200 dark:border-indigo-900/30 p-4 rounded-xl flex gap-3 text-indigo-800 dark:text-indigo-300 text-sm shadow-sm">
              <AlertCircle size={20} className="shrink-0" />
              <p>Provide a rough description and severity. Luigi will format it into a  HTML report and map it to a CWE category Ready for be published on Sucks Secure 24.</p>
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-700 dark:text-zinc-300 mb-2">Severity</label>
              <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="w-full p-3 bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl text-sm font-bold outline-none focus:ring-2 focus:ring-indigo-500">
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
                <option value="info">Info</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-700 dark:text-zinc-300 mb-2">Raw Pentester Notes</label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="e.g., Found XSS on the login parameter. Alert(1) fired. Used payload <script>..."
                className="w-full h-32 p-4 bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-700 dark:text-zinc-300 mb-2">Evidence Images</label>
              <div className="border-2 border-dashed border-slate-200 dark:border-zinc-800 rounded-xl p-6 text-center hover:bg-slate-50 dark:hover:bg-zinc-900/50 transition-colors relative">
                <input type="file" multiple accept="image/*" onChange={handleImageUpload} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" />
                <UploadCloud size={24} className="mx-auto text-slate-400 mb-2" />
                <p className="text-sm font-medium text-slate-600 dark:text-zinc-400">Click or drag images here to attach</p>
                {images.length > 0 && (
                  <p className="text-xs font-bold text-indigo-500 mt-2">{images.length} file(s) queued for upload</p>
                )}
              </div>
            </div>

            <button onClick={handleDraft} disabled={isDrafting || !note.trim()} className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white font-bold rounded-xl shadow-md transition-colors flex items-center justify-center gap-2">
              {isDrafting ? <Loader2 size={18} className="animate-spin" /> : <BrainCircuit size={18} />}
              {isDrafting ? 'Drafting Report...' : 'Draft with Luigi'}
            </button>
          </div>
        )}

        {/* STEP 2: Review & Publish */}
        {step === 2 && (
          <div className="flex flex-1 overflow-hidden">
            {/* Left: Metadata Form */}
            <div className="w-80 shrink-0 border-r border-slate-200 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-950/50 p-5 overflow-y-auto space-y-6">

              <div className="bg-white dark:bg-zinc-900 p-4 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-sm">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Luigi's Suggestion</span>
                <p className="text-sm font-bold text-indigo-600 dark:text-indigo-400">{suggestedCwe}</p>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">Vulnerability Type</label>
                <select value={selectedType} onChange={(e) => handleTypeSelect(e.target.value)} className="w-full p-2.5 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-lg text-xs outline-none focus:ring-2 focus:ring-indigo-500">
                  <option value="">Select mapped type...</option>
                  {vulnTypes.map(vt => <option key={vt.id} value={vt.id}>{vt.name}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">Context</label>
                <select value={selectedContext} onChange={(e) => setSelectedContext(e.target.value)} disabled={!selectedType} className="w-full p-2.5 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-lg text-xs outline-none disabled:opacity-50">
                  <option value="">Select context...</option>
                  {vulnTypes.find(v => v.id === selectedType)?.contexts.map((c: any) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">Finding Title</label>
                <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} className="w-full p-2.5 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-lg text-xs outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">MITRE ID (Optional)</label>
                <input type="text" value={mitreId} onChange={(e) => setMitreId(e.target.value)} placeholder="e.g. T1190" className="w-full p-2.5 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-lg text-xs outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">Remediation Effort</label>
                <select value={remediationEffort} onChange={(e) => setRemediationEffort(e.target.value)} className="w-full p-2.5 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-lg text-xs outline-none focus:ring-2 focus:ring-indigo-500">
                  <option value="Minimal">Minimal</option>
                  <option value="Moderate">Moderate</option>
                  <option value="Significant">Significant</option>
                </select>
              </div>

              <div className="flex items-center justify-between p-3 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-lg">
                <span className="text-xs font-bold text-slate-700 dark:text-zinc-300">Is Authenticated?</span>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" className="sr-only peer" checked={isAuthenticated} onChange={(e) => setIsAuthenticated(e.target.checked)} />
                  <div className="w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer dark:bg-zinc-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-indigo-600"></div>
                </label>
              </div>

            </div>

            {/* Right: HTML Editor (Mimicking TemplateEditorModal) */}
            <div className="flex-1 flex flex-col relative">
              <div className="px-5 py-3 border-b border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 flex justify-between items-center shrink-0">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">HTML Body</span>
                <div className="flex bg-slate-100 dark:bg-zinc-800 rounded-lg p-0.5">
                  <button onClick={() => setShowPreview(false)} className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-md transition-all ${!showPreview ? 'bg-white dark:bg-zinc-700 text-slate-900 dark:text-white shadow-sm' : 'text-slate-500 hover:text-slate-700 dark:hover:text-zinc-300'}`}>
                    <Code size={14} /> HTML
                  </button>
                  <button onClick={() => setShowPreview(true)} className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-md transition-all ${showPreview ? 'bg-white dark:bg-zinc-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-slate-500 hover:text-slate-700 dark:hover:text-zinc-300'}`}>
                    <Eye size={14} /> Preview
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-hidden bg-slate-50 dark:bg-zinc-900 relative">
                {showPreview ? (
                  <div
                    className="absolute inset-0 p-8 overflow-y-auto bg-white dark:bg-zinc-950 text-sm text-slate-800 dark:text-zinc-200 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:my-4 [&_li]:mb-1.5 [&_h1]:font-bold [&_h1]:text-lg [&_h1]:mt-6 [&_h1]:mb-2 [&_strong]:font-bold [&_a]:text-blue-600 [&_a]:underline"
                    dangerouslySetInnerHTML={{ __html: htmlContent }}
                  />
                ) : (
                  <textarea
                    value={htmlContent}
                    onChange={(e) => setHtmlContent(e.target.value)}
                    className="absolute inset-0 w-full h-full p-5 bg-slate-900 text-emerald-400 font-mono text-sm leading-relaxed outline-none resize-none"
                    spellCheck="false"
                  />
                )}
              </div>
            </div>
          </div>
        )}

        {/* Footer (Only for Step 2) */}
        {step === 2 && (
          <div className="p-4 border-t border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 flex justify-between items-center shrink-0">
            <button onClick={() => setStep(1)} className="px-5 py-2 font-bold text-sm text-slate-600 hover:text-slate-900 dark:text-zinc-400 transition-colors">
              Back to Draft
            </button>
            <div className="flex gap-3">
              <button onClick={onClose} disabled={isPublishing} className="px-5 py-2 font-bold text-sm text-slate-600 hover:bg-slate-100 dark:text-zinc-400 dark:hover:bg-zinc-900 rounded-xl transition-colors">
                Cancel
              </button>
              <button onClick={handlePublish} disabled={isPublishing} className="px-6 py-2 flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm rounded-xl shadow-md transition-colors">
                {isPublishing ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                {isPublishing ? 'Publishing...' : 'Publish to KISS24'}
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}