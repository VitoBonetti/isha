import { useState, useEffect } from 'react';
import axios from 'axios';
import { X, Send, Eye, Code, Mail } from 'lucide-react';
import toast from 'react-hot-toast';

interface IntroEmailModalProps {
  isOpen: boolean;
  testId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function IntroEmailModal({ isOpen, testId, onClose, onSuccess }: IntroEmailModalProps) {
  const [to, setTo] = useState('');
  const [cc, setCc] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');

  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [showPreview, setShowPreview] = useState(true);

  useEffect(() => {
    if (isOpen && testId) {
      setLoading(true);
      setShowPreview(true);
      axios.get(`/api/luigi/${testId}/draft-intro-email`)
        .then(res => {
          setTo(res.data.to);
          setCc(res.data.cc);
          setSubject(res.data.subject);
          setBody(res.data.body);
        })
        .catch(() => toast.error("Failed to load email draft"))
        .finally(() => setLoading(false));
    }
  }, [isOpen, testId]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!to.trim() || !subject.trim() || !body.trim()) {
      toast.error("To, Subject, and Body are required.");
      return;
    }

    setSending(true);
    try {
      await axios.post(`/api/luigi/${testId}/send-intro-email`, {
        to, cc, subject, body
      });
      toast.success("Intro email sent successfully!");
      onSuccess(); // Trigger a milestone refresh
      onClose();
    } catch (error) {
      toast.error("Failed to send email");
    } finally {
      setSending(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in">
      <div className="bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-2xl w-full max-w-4xl overflow-hidden flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="p-5 border-b border-slate-100 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-900/50 flex justify-between items-center shrink-0">
          <div className="flex items-center gap-3">
            <div className="bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 p-2 rounded-lg">
              <Mail size={20} />
            </div>
            <div>
              <h2 className="font-black text-lg text-slate-900 dark:text-zinc-100 leading-tight">Send Intro Email</h2>
              <p className="text-xs font-medium text-slate-500">Review and send the automated engagement setup email</p>
            </div>
          </div>
          <button onClick={onClose} disabled={sending} className="p-2 bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-500 rounded-full transition-colors disabled:opacity-50">
            <X size={16} />
          </button>
        </div>

        {loading ? (
          <div className="flex-1 p-10 flex items-center justify-center text-slate-400 font-bold text-sm animate-pulse">
            Drafting email from template...
          </div>
        ) : (
          <form onSubmit={handleSend} className="flex flex-col flex-1 overflow-hidden">
            <div className="p-5 overflow-y-auto flex-1 bg-slate-50/30 dark:bg-zinc-950/30 space-y-4">

              {/* Email Headers */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-500 uppercase">To</label>
                  <input type="text" value={to} onChange={(e) => setTo(e.target.value)} placeholder="contact@example.com" className="w-full px-3 py-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-lg text-sm text-slate-900 dark:text-zinc-100 outline-none focus:border-blue-500 transition-colors" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-500 uppercase">CC</label>
                  <input type="text" value={cc} onChange={(e) => setCc(e.target.value)} placeholder="cc@example.com, manager@example.com" className="w-full px-3 py-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-lg text-sm text-slate-900 dark:text-zinc-100 outline-none focus:border-blue-500 transition-colors" />
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-500 uppercase">Subject</label>
                <input type="text" value={subject} onChange={(e) => setSubject(e.target.value)} className="w-full px-3 py-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-lg text-sm text-slate-900 dark:text-zinc-100 outline-none focus:border-blue-500 transition-colors font-medium" />
              </div>

              {/* Body Section with Tabs */}
              <div className="space-y-1 flex-1 flex flex-col min-h-[300px]">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-500 uppercase">Message Body</label>
                  <div className="flex bg-slate-100 dark:bg-zinc-800 rounded-lg p-0.5">
                    <button type="button" onClick={() => setShowPreview(true)} className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-md transition-all ${showPreview ? 'bg-white dark:bg-zinc-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-slate-500 hover:text-slate-700 dark:hover:text-zinc-300'}`}>
                      <Eye size={14} /> Preview
                    </button>
                    <button type="button" onClick={() => setShowPreview(false)} className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-md transition-all ${!showPreview ? 'bg-white dark:bg-zinc-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-slate-500 hover:text-slate-700 dark:hover:text-zinc-300'}`}>
                      <Code size={14} /> HTML
                    </button>
                  </div>
                </div>

                <div className="flex-1 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl overflow-hidden flex flex-col">
                  {showPreview ? (
                    <div
                      className="flex-1 p-5 overflow-y-auto h-full text-sm text-slate-800 dark:text-zinc-200 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:my-4 [&_li]:mb-1.5 [&_h3]:font-bold [&_h3]:text-lg [&_h3]:text-slate-900 [&_h3:dark]:text-white [&_h3]:mt-6 [&_h3]:mb-2 [&_strong]:font-bold"
                      dangerouslySetInnerHTML={{ __html: body }}
                    />
                  ) : (
                    <textarea
                      value={body}
                      onChange={(e) => setBody(e.target.value)}
                      className="flex-1 w-full p-4 bg-slate-900 text-emerald-400 font-mono text-xs outline-none resize-none h-full"
                      spellCheck="false"
                    />
                  )}
                </div>
              </div>

            </div>

            {/* Footer */}
            <div className="p-4 border-t border-slate-100 dark:border-zinc-800 bg-white dark:bg-zinc-950 flex justify-end gap-3 shrink-0">
              <button type="button" onClick={onClose} disabled={sending} className="px-4 py-2 font-bold text-sm text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-900 rounded-xl transition-colors disabled:opacity-50">
                Cancel
              </button>
              <button type="submit" disabled={sending} className="px-5 py-2 flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-bold text-sm rounded-xl transition-colors">
                {sending ? (
                  <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                ) : (
                  <Send size={16} />
                )}
                {sending ? 'Sending...' : 'Send via Luigi'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}