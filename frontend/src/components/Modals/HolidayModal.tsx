import React, { useMemo } from 'react';
import { X, CalendarDays, Users, MapPin, AlertCircle } from 'lucide-react';

interface HolidayModalProps {
  isOpen: boolean;
  onClose: () => void;
  holidayData: any;
  setHolidayData: (data: any) => void;
  onSave: () => void;
  onDelete: (id: string) => void;
  pentesters: any[];
  locations: any[];
  currentUser: any;
}

export default function HolidayModal({ 
  isOpen, onClose, holidayData, setHolidayData, 
  onSave, onDelete, pentesters, locations, currentUser 
}: HolidayModalProps) {
  if (!isOpen || !holidayData) return null;

  const isEditing = !!holidayData.id;

  const liveCredits = useMemo(() => {
    if (!holidayData.start_date || !holidayData.end_date) return 0;

    let workingDays = 0;
    let d = new Date(`${holidayData.start_date}T12:00:00`);
    const end = new Date(`${holidayData.end_date}T12:00:00`);

    while (d <= end) {
      if (d.getDay() !== 0 && d.getDay() !== 6) workingDays++;
      d.setDate(d.getDate() + 1);
    }
    if (workingDays === 0) return 0;

    if (holidayData.event_type === 'national_holiday' || holidayData.event_type === 'team_day') {
      const locId = holidayData.location_id || null;
      const affectedUsers = pentesters.filter(p => !locId || p.location_id === locId);

      let totalDailyCap = 0;
      affectedUsers.forEach(p => {
         const c = Number(p.base_capacity || 1.0);
         totalDailyCap += (c / 5);
      });
      return (workingDays * totalDailyCap).toFixed(1);
    }

    if (!holidayData.user_id) return 0;
    const user = pentesters.find(p => p.id === holidayData.user_id);
    if (!user) return 0;

    const baseCap = Number(user.base_capacity || 1.0);
    return (workingDays * (baseCap / 5)).toFixed(1);
  }, [holidayData, pentesters]);

  return (
    <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 w-full max-w-md shadow-2xl animate-in zoom-in-95">
        <div className="flex justify-between items-center mb-6 border-b border-slate-100 dark:border-zinc-800 pb-4">
          <h2 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <CalendarDays size={20} className="text-blue-500" />
            {isEditing ? 'Edit Time Off' : 'Add Time Off'}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); onSave(); }} className="space-y-5">

          <div>
            <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase mb-1.5">Event Type</label>
            <select
              required
              value={holidayData.event_type}
              onChange={e => setHolidayData({...holidayData, event_type: e.target.value})}
              className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 dark:text-zinc-100 outline-none"
            >
              <option value="personal_time_off">Personal Time Off</option>
              {currentUser?.role === 'admin' && (
                <>
                  <option value="national_holiday">National Holiday</option>
                  <option value="team_day">Team Day</option>
                </>
              )}
            </select>
          </div>

          {holidayData.event_type === 'personal_time_off' && (
            <div>
              <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase mb-1.5 flex items-center gap-1"><Users size={12}/> Team Member</label>
              <select
                required
                value={holidayData.user_id || ''}
                onChange={e => setHolidayData({...holidayData, user_id: e.target.value})}
                disabled={currentUser?.role !== 'admin'}
                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 disabled:opacity-60 disabled:cursor-not-allowed dark:text-zinc-100 outline-none font-medium"
              >
                <option value="" disabled>Select User...</option>
                {pentesters.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
          )}

          {holidayData.event_type === 'national_holiday' && (
            <div>
              <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase mb-1.5 flex items-center gap-1"><MapPin size={12}/> Location</label>
              <select
                value={holidayData.location_id || ''}
                onChange={e => setHolidayData({...holidayData, location_id: e.target.value})}
                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 dark:text-zinc-100 outline-none"
              >
                <option value="">Global (All Locations)</option>
                {locations?.map(loc => (
                  <option key={loc.id} value={loc.id}>{loc.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className="flex gap-4">
            <div className="flex-1">
              <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase mb-1.5">Start Date</label>
              <input
                type="date" required
                value={holidayData.start_date}
                onChange={e => setHolidayData({...holidayData, start_date: e.target.value})}
                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 dark:text-zinc-100 outline-none"
              />
            </div>
            <div className="flex-1">
              <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase mb-1.5">End Date</label>
              <input
                type="date" required
                value={holidayData.end_date}
                onChange={e => setHolidayData({...holidayData, end_date: e.target.value})}
                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 dark:text-zinc-100 outline-none"
              />
            </div>
          </div>

          <div className="mt-6 bg-blue-50 dark:bg-blue-500/10 border border-blue-100 dark:border-blue-500/20 rounded-xl p-3.5 flex items-center justify-between text-sm shadow-inner">
            <div className="flex items-center gap-2 font-bold text-blue-800 dark:text-blue-400">
              <AlertCircle size={16} />
              Estimated Impact:
            </div>
            <span className={`font-extrabold ${Number(liveCredits) > 0 ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
              -{liveCredits} Credits
            </span>
          </div>

          <div className="flex justify-between items-center pt-5 border-t border-slate-100 dark:border-zinc-800 mt-6">
            {isEditing ? (
              <button type="button" onClick={() => onDelete(holidayData.id)} className="px-4 py-2.5 text-sm font-bold text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-lg transition-colors">
                Delete Event
              </button>
            ) : <div />} 
            
            <div className="flex gap-2">
              <button type="button" onClick={onClose} className="px-4 py-2.5 text-sm font-medium bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors">Cancel</button>
              <button type="submit" className="px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors">Save Event</button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}