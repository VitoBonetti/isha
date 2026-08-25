import { useState } from 'react';
import axios from 'axios';
import { X, Calendar as CalendarIcon, Clock, Users, CheckCircle, ExternalLink } from 'lucide-react';
import toast from 'react-hot-toast';

interface MeetingProposalsModalProps {
  isOpen: boolean;
  testId: string;
  testName: string;
  proposalData: any; // { proposals: [], meeting_type: str, emails: [] }
  onClose: () => void;
  onSuccess: () => void;
}

export default function MeetingProposalsModal({ isOpen, testId, testName, proposalData, onClose, onSuccess }: MeetingProposalsModalProps) {
  const [selectedSlot, setSelectedSlot] = useState<number | null>(null);
  const [isBooking, setIsBooking] = useState(false);

  if (!isOpen || !proposalData) return null;

  const handleBook = async () => {
    if (selectedSlot === null) return;
    setIsBooking(true);
    const slot = proposalData.proposals[selectedSlot];

    let dynamicDescription = "";
    const typeLower = proposalData.meeting_type.toLowerCase();

    if (typeLower.includes('intake')) {
      dynamicDescription = "The goals of this call are to explain the pentesting process, allow the testers to gain a functional understanding of the application, and verify accessibility.";
    } else if (typeLower.includes('finding') || typeLower.includes('restitution')) {
      dynamicDescription = "The goals of this call are to walk through the identified vulnerabilities, discuss remediation strategies, and address any technical questions regarding the pentest findings.";
    } else {
      dynamicDescription = `Discussion regarding the pentest: ${testName}`;
    }

    const payload = {
      summary: `${proposalData.meeting_type.replace(' Planned', '')}: ${testName}`,
      description: dynamicDescription,
      emails: proposalData.emails,
      startTime: slot.start_time,
      endTime: slot.end_time,
      meeting_type: proposalData.meeting_type
    };

    try {
      const res = await axios.post(`/api/luigi/${testId}/book-meeting`, payload);
      toast.success(
        (t) => (
          <div className="flex flex-col gap-1">
            <span className="font-medium text-sm">Meeting booked successfully!</span>
            <a href={res.data.link} target="_blank" rel="noopener noreferrer" onClick={() => toast.dismiss(t.id)} className="text-xs text-blue-600 font-bold hover:underline flex items-center gap-1">
              View on Google Calendar <ExternalLink size={12} />
            </a>
          </div>
        ),
        { duration: 8000 }
      );
      onSuccess();
      onClose();
    } catch (error) {
      toast.error("Failed to book meeting.");
    } finally {
      setIsBooking(false);
    }
  };

  const formatDate = (isoString: string) => {
    const d = new Date(isoString);
    return {
      date: d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }),
      time: d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in">
      <div className="bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">

        <div className="p-5 border-b border-slate-100 dark:border-zinc-800 flex justify-between items-center bg-indigo-50 dark:bg-indigo-900/10">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded-lg"><CalendarIcon size={20} /></div>
            <div>
              <h2 className="font-black text-lg text-slate-900 dark:text-zinc-100">Luigi's Proposed Slots</h2>
              <p className="text-xs font-medium text-slate-500">{proposalData.meeting_type} • {testName}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 bg-white dark:bg-zinc-800 text-slate-500 rounded-full hover:bg-slate-200 transition-colors"><X size={16} /></button>
        </div>

        <div className="p-6 overflow-y-auto bg-slate-50/50 dark:bg-zinc-900/30 space-y-4">
          <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-zinc-400 mb-2">
            <Users size={16} /> <strong>Participants:</strong> {proposalData.emails?.length || 0} people
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {proposalData.proposals.map((slot: any, idx: number) => {
              const start = formatDate(slot.start_time);
              const end = formatDate(slot.end_time);
              const isSelected = selectedSlot === idx;

              return (
                <div
                  key={idx}
                  onClick={() => setSelectedSlot(idx)}
                  className={`cursor-pointer border-2 rounded-xl p-4 transition-all ${isSelected ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20 shadow-md' : 'border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:border-indigo-300'}`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className="font-bold text-slate-900 dark:text-zinc-100 text-lg">{start.date}</div>
                    {isSelected && <CheckCircle size={20} className="text-indigo-500" />}
                  </div>
                  <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400 font-bold mb-3">
                    <Clock size={16} /> {start.time} — {end.time} ({slot.duration_mins}m)
                  </div>
                  <p className="text-xs text-slate-500 dark:text-zinc-400 leading-relaxed border-t border-slate-100 dark:border-zinc-800 pt-2">
                    <strong>AI Note:</strong> {slot.description}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        <div className="p-4 border-t border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 flex justify-end gap-3">
          <button onClick={onClose} disabled={isBooking} className="px-5 py-2 font-bold text-sm text-slate-600 hover:bg-slate-100 rounded-xl transition-colors">Cancel</button>
          <button onClick={handleBook} disabled={isBooking || selectedSlot === null} className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white font-bold text-sm rounded-xl transition-colors flex items-center gap-2">
            {isBooking ? 'Booking...' : 'Send Calendar Invite'}
          </button>
        </div>
      </div>
    </div>
  );
}