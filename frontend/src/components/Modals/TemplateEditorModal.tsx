import { useState, useEffect } from 'react';
import axios from 'axios';
import { X, Save, Eye, Code, Mail, CheckCircle, Info, Copy } from 'lucide-react';
import toast from 'react-hot-toast';

interface TemplateEditorModalProps {
  isOpen: boolean;
  serviceId: string;
  serviceName: string;
  templateType: 'intro' | 'final' | null;
  initialTemplate: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function TemplateEditorModal({ isOpen, serviceId, serviceName, templateType, initialTemplate, onClose, onSuccess }: TemplateEditorModalProps) {
  const [content, setContent] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setContent(initialTemplate || '');
      setShowPreview(false);
    }
  }, [isOpen, initialTemplate]);

  if (!isOpen || !templateType) return null;

  const isIntro = templateType === 'intro';

  // --- CHEAT SHEET DATA ---
  const tags = isIntro ? [
    { tag: "{{service_lane}}", desc: "Name of the service lane" },
    { tag: "{{country_code}}", desc: "Target country code" },
    { tag: "{{asset_name}}", desc: "Name of the target asset" },
    { tag: "{{week}}", desc: "Scheduled week number" },
    { tag: "{{year}}", desc: "Scheduled year" },
    { tag: "{{week_start_date}}", desc: "Calculated Monday date" },
    { tag: "{{pentesters}}", desc: "Assigned team names" }
  ] : [
    { tag: "{{service_lane}}", desc: "Name of the service lane" },
    { tag: "{{country_code}}", desc: "Target country code" },
    { tag: "{{asset_name}}", desc: "Name of the target asset" },
    { tag: "{{week}}", desc: "Scheduled week number" },
    { tag: "{{year}}", desc: "Scheduled year" },
    { tag: "{{pentesters}}", desc: "Assigned team names" },
    { tag: "{{kiss24}}", desc: "KISS24 Platform UUID" }
  ];

  const handleCopy = (tag: string) => {
    navigator.clipboard.writeText(tag);
    toast.success(`Copied ${tag} to clipboard!`, { duration: 2000 });
  };

  const handleSave = async () => {
    setIsSaving(true);
    const payload = isIntro ? { intro_email_template: content } : { final_email_template: content };

    try {
      await axios.patch(`/api/services/${serviceId}/templates`, payload);
      toast.success(`${isIntro ? 'Intro' : 'Final'} template saved!`);
      onSuccess();
      onClose();
    } catch (error) {
      toast.error("Failed to save template");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in">
      <div className="bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-2xl w-full max-w-6xl overflow-hidden flex flex-col h-[90vh]">

        {/* Header */}
        <div className="p-5 border-b border-slate-100 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-900/50 flex justify-between items-center shrink-0">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${isIntro ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' : 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400'}`}>
              {isIntro ? <Mail size={20} /> : <CheckCircle size={20} />}
            </div>
            <div>
              <h2 className="font-black text-lg text-slate-900 dark:text-zinc-100 leading-tight">
                {isIntro ? 'Intro Email Template' : 'Final Email Template'}
              </h2>
              <p className="text-xs font-medium text-slate-500">Editing template for <strong className="text-slate-700 dark:text-zinc-300">{serviceName}</strong></p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-500 rounded-full transition-colors">
            <X size={16} />
          </button>
        </div>

        {/* Body Layout: Editor (Left) + Cheat Sheet (Right) */}
        <div className="flex flex-1 overflow-hidden">

          {/* Main Editor Section */}
          <div className="flex-1 flex flex-col border-r border-slate-200 dark:border-zinc-800">
            <div className="px-5 py-3 border-b border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 flex justify-between items-center shrink-0">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Editor</span>
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
                  className="absolute inset-0 p-8 overflow-y-auto bg-white dark:bg-zinc-950 text-sm text-slate-800 dark:text-zinc-200 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:my-4 [&_li]:mb-1.5 [&_h3]:font-bold [&_h3]:text-lg [&_h3]:text-slate-900 [&_h3:dark]:text-white [&_h3]:mt-6 [&_h3]:mb-2 [&_strong]:font-bold [&_a]:text-blue-600 [&_a]:underline"
                  dangerouslySetInnerHTML={{ __html: content || '<div class="text-slate-400 italic">Preview empty...</div>' }}
                />
              ) : (
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  className="absolute inset-0 w-full h-full p-5 bg-slate-900 text-emerald-400 font-mono text-sm leading-relaxed outline-none resize-none"
                  spellCheck="false"
                  placeholder="Paste your HTML template here..."
                />
              )}
            </div>
          </div>

          {/* Cheat Sheet Section */}
          <div className="w-80 shrink-0 bg-slate-50 dark:bg-zinc-950/50 flex flex-col">
            <div className="px-5 py-3 border-b border-slate-200 dark:border-zinc-800 shrink-0 flex items-center gap-2">
              <Info size={16} className="text-indigo-500" />
              <span className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">Cheat Sheet</span>
            </div>

            <div className="p-5 overflow-y-auto flex-1 space-y-4">
              <p className="text-xs text-slate-500 dark:text-zinc-400 mb-2 leading-relaxed">
                Click any tag below to copy it. Luigi will dynamically replace these when drafting the email.
              </p>

              <div className="space-y-2.5">
                {tags.map((t, idx) => (
                  <div key={idx} onClick={() => handleCopy(t.tag)} className="group cursor-pointer p-3 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-lg hover:border-indigo-400 dark:hover:border-indigo-500 transition-all hover:shadow-sm">
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">{t.tag}</span>
                      <Copy size={12} className="text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                    <p className="text-[10px] text-slate-500 dark:text-zinc-500 leading-tight">{t.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 flex justify-end gap-3 shrink-0">
          <button onClick={onClose} disabled={isSaving} className="px-5 py-2 font-bold text-sm text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-900 rounded-xl transition-colors">
            Cancel
          </button>
          <button onClick={handleSave} disabled={isSaving} className="px-6 py-2 flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm rounded-xl transition-colors">
            <Save size={16} /> {isSaving ? 'Saving...' : 'Save Template'}
          </button>
        </div>

      </div>
    </div>
  );
}