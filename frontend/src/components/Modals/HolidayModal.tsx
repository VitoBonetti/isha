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

  const getCapacity = (user: any) => Number(user.base_capacity ?? user.capacity ?? 1.0);

  const liveCredits = useMemo(() => {
    if (!holidayData.start_date || !holidayData.end_date) return "0.0";

    // WFA costs absolutely 0 credits!
    if (holidayData.event_type === 'working_from_abroad') return "0.0";

    let workingDays = 0;
    let d = new Date(`${holidayData.start_date}T12:00:00`);
    const end = new Date(`${holidayData.end_date}T12:00:00`);

    while (d <= end) {
      if (d.getDay() !== 0 && d.getDay() !== 6) workingDays++;
      d.setDate(d.getDate() + 1);
    }
    if (workingDays === 0) return "0.0";

    if (holidayData.event_type === 'national_holiday' || holidayData.event_type === 'team_day') {
      const locId = holidayData.location_id ? String(holidayData.location_id) : null;
      const affectedUsers = pentesters?.filter(p =>
        !locId || String(p.location_id) === locId
      ) || [];

      let totalDailyCap = 0;
      affectedUsers.forEach(p => {
         totalDailyCap += (getCapacity(p) / 5);
      });
      return (workingDays * totalDailyCap).toFixed(1);
    }

    if (!holidayData.user_id) return "0.0";
    const user = pentesters?.find(p => p.id === holidayData.user_id);
    if (!user) return "0.0";

    return (workingDays * (getCapacity(user) / 5)).toFixed(1);
  }, [holidayData, pentesters]);

  return (
    <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-50 flex items-start sm:items-center justify-center p-2 sm:p-4 animate-in fade-in overflow-y-auto">
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 sm:p-6 w-[95%] sm:w-full max-w-md shadow-2xl animate-in zoom-in-95 my-4 sm:my-auto flex-shrink-0">
        <div className="flex justify-between items-start sm:items-center mb-4 sm:mb-6 border-b border-slate-100 dark:border-zinc-800 pb-4">
          <h2 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <CalendarDays size={20} className="text-blue-500" />
            {isEditing ? 'Edit Event' : 'Add Event'}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors p-1">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); onSave(); }} className="space-y-4 sm:space-y-5">

          <div>
            <label className="block text-[11px] sm:text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase mb-1.5">Event Type</label>
            <select
              required
              value={holidayData.event_type}
              onChange={e => setHolidayData({...holidayData, event_type: e.target.value})}
              className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 dark:text-zinc-100 outline-none"
            >
              <option value="personal_time_off">Personal Time Off</option>
              <option value="sick_day">Sick Day</option>
              <option value="working_from_abroad">Working from Abroad</option>
              {currentUser?.role === 'admin' && (
                <>
                  <option value="national_holiday">National Holiday</option>
                  <option value="team_day">Team Day</option>
                </>
              )}
            </select>
          </div>

          {/* Show team member for PTO, Sick, OR Working from Abroad */}
          {['personal_time_off', 'sick_day', 'working_from_abroad'].includes(holidayData.event_type) && (
            <div>
              <label className="block text-[11px] sm:text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase mb-1.5 flex items-center gap-1"><Users size={12}/> Team Member</label>
              <select
                required
                value={holidayData.user_id || ''}
                onChange={e => setHolidayData({...holidayData, user_id: e.target.value})}
                disabled={currentUser?.role !== 'admin'}
                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 disabled:opacity-60 disabled:cursor-not-allowed dark:text-zinc-100 outline-none font-medium"
              >
                <option value="" disabled>Select User...</option>
                {(pentesters?.length ? pentesters : []).map(p => (
                  <option key={p.id} value={p.id}>{p.name || 'Unnamed User'}</option>
                ))}
              </select>
            </div>
          )}

          {/* Show location for National Holidays AND Working from Abroad */}
          {['national_holiday', 'working_from_abroad'].includes(holidayData.event_type) && (
            <div>
              <label className="block text-[11px] sm:text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase mb-1.5 flex items-center gap-1"><MapPin size={12}/> Location</label>
              <select
                value={holidayData.location_id || ''}
                onChange={e => setHolidayData({...holidayData, location_id: e.target.value})}
                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 dark:text-zinc-100 outline-none"
              >
                <option value="">{holidayData.event_type === 'working_from_abroad' ? 'Unknown/Other' : 'Global (All Locations)'}</option>
                {locations?.map(loc => (
                  <option key={loc.id} value={loc.id}>{loc.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <label className="block text-[11px] sm:text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase mb-1.5">Start Date</label>
              <input
                type="date" required
                value={holidayData.start_date}
                onChange={e => setHolidayData({...holidayData, start_date: e.target.value})}
                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 dark:text-zinc-100 outline-none"
              />
            </div>
            <div className="flex-1">
              <label className="block text-[11px] sm:text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase mb-1.5">End Date</label>
              <input
                type="date" required
                value={holidayData.end_date}
                onChange={e => setHolidayData({...holidayData, end_date: e.target.value})}
                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 dark:text-zinc-100 outline-none"
              />
            </div>
          </div>

          <div className="mt-4 sm:mt-6 bg-blue-50 dark:bg-blue-500/10 border border-blue-100 dark:border-blue-500/20 rounded-xl p-3.5 flex items-center justify-between text-sm shadow-inner">
            <div className="flex items-center gap-2 font-bold text-blue-800 dark:text-blue-400">
              <AlertCircle size={16} className="flex-shrink-0" />
              Estimated Impact:
            </div>
            <span className={`font-extrabold flex-shrink-0 ${Number(liveCredits) > 0 ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
              -{liveCredits} Credits
            </span>
          </div>

          <div className="flex flex-col sm:flex-row justify-between items-center pt-5 border-t border-slate-100 dark:border-zinc-800 mt-6 gap-3 sm:gap-0">
            {isEditing ? (
              <button type="button" onClick={() => onDelete(holidayData.id)} className="w-full sm:w-auto px-4 py-2.5 text-sm font-bold text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-lg transition-colors order-3 sm:order-1 flex justify-center">
                Delete Event
              </button>
            ) : <div className="hidden sm:block" />}

            <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto order-1 sm:order-2">
              <button type="submit" className="w-full sm:w-auto px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors order-1 sm:order-2 flex justify-center">Save Event</button>
              <button type="button" onClick={onClose} className="w-full sm:w-auto px-4 py-2.5 text-sm font-medium bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors order-2 sm:order-1 flex justify-center">Cancel</button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}