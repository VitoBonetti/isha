import { useState, useEffect } from 'react';
import { X, Users, Mail } from 'lucide-react';

interface MeetingParticipantsModalProps {
  isOpen: boolean;
  meetingType: string;
  initialEmails: string;
  onClose: () => void;
  onConfirm: (emails: string[]) => void;
}

export default function MeetingParticipantsModal({ isOpen, meetingType, initialEmails, onClose, onConfirm }: MeetingParticipantsModalProps) {
  const [emailText, setEmailText] = useState("");

  useEffect(() => {
    if (isOpen) setEmailText(initialEmails);
  }, [isOpen, initialEmails]);

  if (!isOpen) return null;

  const handleConfirm = () => {
    // Split the string by commas, trim whitespace, and filter out any empty entries
    const emailArray = emailText.split(',').map(e => e.trim()).filter(e => e.length > 0);
    onConfirm(emailArray);
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in">
      <div className="bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden flex flex-col">
        <div className="p-5 border-b border-slate-100 dark:border-zinc-800 flex justify-between items-center bg-indigo-50 dark:bg-indigo-900/10">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded-lg"><Users size={20} /></div>
            <div>
              <h2 className="font-black text-lg text-slate-900 dark:text-zinc-100">Meeting Participants</h2>
              <p className="text-xs font-medium text-slate-500">Edit who should be invited to the {meetingType}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 bg-white dark:bg-zinc-800 text-slate-500 rounded-full hover:bg-slate-200 transition-colors"><X size={16} /></button>
        </div>

        <div className="p-6 bg-slate-50/50 dark:bg-zinc-900/30">
          <label className="text-sm font-bold text-slate-700 dark:text-zinc-300 flex items-center gap-2 mb-2">
            <Mail size={16} /> Participant Emails (Comma separated)
          </label>
          <textarea
            value={emailText}
            onChange={(e) => setEmailText(e.target.value)}
            rows={5}
            className="w-full p-3 border border-slate-300 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-900 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-indigo-500 outline-none transition-all text-sm"
            placeholder="email1@example.com, email2@example.com"
          />
          <p className="text-xs text-slate-500 mt-2">Luigi will cross-reference the Google Calendars of these exact emails to find the best time slots.</p>
        </div>

        <div className="p-4 border-t border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 flex justify-end gap-3">
          <button onClick={onClose} className="px-5 py-2 font-bold text-sm text-slate-600 hover:bg-slate-100 rounded-xl transition-colors">Cancel</button>
          <button onClick={handleConfirm} className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-sm rounded-xl transition-colors flex items-center gap-2">
            Continue to Luigi
          </button>
        </div>
      </div>
    </div>
  );
}