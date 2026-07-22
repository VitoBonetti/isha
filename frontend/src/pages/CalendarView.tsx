import { useState, useMemo, useEffect } from 'react';
import axios from 'axios';
import toast, { Toaster } from 'react-hot-toast';
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon, Palmtree } from 'lucide-react';
import HolidayModal from '../components/Modals/HolidayModal';
import { useAppContext } from '../context/AppContext';
import TopNav from '../components/TopNav';

const USER_COLORS = [
  { bg: 'bg-sky-100 dark:bg-sky-500/20', border: 'border-sky-500', text: 'text-sky-700 dark:text-sky-400' },
  { bg: 'bg-green-100 dark:bg-green-500/20', border: 'border-green-500', text: 'text-green-700 dark:text-green-400' },
  { bg: 'bg-amber-100 dark:bg-amber-500/20', border: 'border-amber-500', text: 'text-amber-700 dark:text-amber-400' },
  { bg: 'bg-purple-100 dark:bg-purple-500/20', border: 'border-purple-500', text: 'text-purple-700 dark:text-purple-400' },
  { bg: 'bg-rose-100 dark:bg-rose-500/20', border: 'border-rose-500', text: 'text-rose-700 dark:text-rose-400' },
  { bg: 'bg-indigo-100 dark:bg-indigo-500/20', border: 'border-indigo-500', text: 'text-indigo-700 dark:text-indigo-400' },
];

const getUserColor = (userId: string, pentestersArray: any[]) => {
  if (!userId || !pentestersArray) return USER_COLORS[0];
  const userIndex = pentestersArray.findIndex(p => p.id === userId);
  return USER_COLORS[Math.max(0, userIndex) % USER_COLORS.length];
};

export default function CalendarView() {
  const { currentUser } = useAppContext();

  const [currentDate, setCurrentDate] = useState(new Date());
  const [modalOpen, setModalOpen] = useState(false);
  const [activeHoliday, setActiveHoliday] = useState<any>(null);

  // Local state for data fetching to ensure modal has data even if routed directly
  const [boardData, setBoardData] = useState<any>({});
  const [locations, setLocations] = useState<any[]>([]);
  const [pentesters, setPentesters] = useState<any[]>([]);

  // Fetch all necessary data on mount
  useEffect(() => {
    const currentYear = new Date().getFullYear();
    const currentMonth = new Date().getMonth() + 1;
    let quarter = 1;
    if (currentMonth > 3) quarter = 2;
    if (currentMonth > 6) quarter = 3;
    if (currentMonth > 9) quarter = 4;

    // Fetch Locations for Modal Dropdowns
    axios.get('/api/locations/')
      .then(res => setLocations(res.data || []))
      .catch(() => {});

    // Fetch Users for Credit Calculations and User Selection
    axios.get('/api/users/')
      .then(res => setPentesters(res.data || []))
      .catch(console.error);

    // Fetch Board Data (Events)
    axios.get(`/api/board/${currentYear}/Q${quarter}`)
      .then(res => setBoardData(res.data || {}))
      .catch(console.error);
  }, []);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const monthName = currentDate.toLocaleString('default', { month: 'long' });

  const handlePrevMonth = () => setCurrentDate(new Date(year, month - 1, 1));
  const handleNextMonth = () => setCurrentDate(new Date(year, month + 1, 1));
  const handleToday = () => setCurrentDate(new Date());

  const toDateStr = (d: Date) => {
    if (!d) return "";
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  };

  const extractDateStr = (dateInput: string) => {
    if (!dateInput) return "";
    return String(dateInput).split('T')[0];
  };

  const weeks = useMemo(() => {
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const weeksArray = [];
    let currentWeek: (Date | null)[] = [];

    const firstDayOfMonth = new Date(year, month, 1).getDay();
    const padDays = (firstDayOfMonth === 0 || firstDayOfMonth === 6) ? 0 : firstDayOfMonth - 1;

    for (let i = 0; i < padDays; i++) currentWeek.push(null);

    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(year, month, day);
      const dayOfWeek = date.getDay();
      if (dayOfWeek !== 0 && dayOfWeek !== 6) currentWeek.push(date);
      if (dayOfWeek === 5) { weeksArray.push(currentWeek); currentWeek = []; }
    }

    if (currentWeek.length > 0) {
      while (currentWeek.length < 5) currentWeek.push(null);
      weeksArray.push(currentWeek);
    }

    return weeksArray;
  }, [year, month]);

  // Use local state for events and pentesters to ensure they are populated
  const events = boardData?.events || [];
  const localPentesters = pentesters.length > 0 ? pentesters : (boardData?.pentesters || []);

  const getIsoWeek = (date: Date) => {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  };

  const isUserActiveOnDate = (user: any, dateStr: string) => {
    if (!dateStr) return true;
    const d = new Date(dateStr);
    const eventYear = d.getFullYear();
    const eventWeek = getIsoWeek(d);

    if (user.start_year > eventYear || (user.start_year === eventYear && user.start_week > eventWeek)) return false;
    if (user.end_year && (user.end_year < eventYear || (user.end_year === eventYear && user.end_week < eventWeek))) return false;
    return true;
  };

  // Filter the pentesters dynamically based on the modal's selected start date
  const activeHolidayPentesters = localPentesters.filter(p => isUserActiveOnDate(p, activeHoliday?.start_date));

  return (
    <div className="min-h-screen dark:bg-[#09090b] text-slate-900 dark:text-zinc-100 flex flex-col relative overflow-hidden transition-colors duration-300">


      <TopNav />
      <Toaster position="bottom-right" />

      <main className="flex-1 pt-32 pb-12 px-6 max-w-7xl mx-auto w-full relative z-10 flex flex-col">

        {/* Header */}
        <div className="flex justify-between items-center mb-6 shrink-0">
          <div>
            <h1 className="text-2xl font-extrabold flex items-center gap-2">
              <Palmtree size={28} className="text-emerald-500" />
              Holiday Tracker
            </h1>
            <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1">Manage personal time off and national holidays across regions.</p>
          </div>

          <div className="flex items-center gap-4 bg-white dark:bg-zinc-900 p-2 rounded-xl border border-slate-200 dark:border-zinc-800 shadow-sm">
            <button onClick={handlePrevMonth} className="p-2 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors text-slate-600 dark:text-zinc-400"><ChevronLeft size={20} /></button>
            <div className="w-40 text-center font-bold text-lg">{monthName} {year}</div>
            <button onClick={handleNextMonth} className="p-2 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors text-slate-600 dark:text-zinc-400"><ChevronRight size={20} /></button>
            <div className="w-px h-6 bg-slate-200 dark:bg-zinc-800 mx-1"></div>
            <button onClick={handleToday} className="px-4 py-1.5 text-sm font-bold bg-blue-50 dark:bg-blue-500/10 hover:bg-blue-100 dark:hover:bg-blue-500/20 text-blue-600 dark:text-blue-400 rounded-lg transition-colors">
              Today
            </button>
          </div>
        </div>

        {/* Grid Container */}
        <div className="flex-1 flex flex-col bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-sm overflow-hidden min-h-[600px]">

          {/* Days Header */}
          <div className="grid grid-cols-5 border-b border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-950/50 shrink-0">
            {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'].map(day => (
              <div key={day} className="p-4 text-center text-xs font-extrabold tracking-widest uppercase text-slate-500 dark:text-zinc-500 border-r border-slate-200 dark:border-zinc-800 last:border-r-0">
                {day}
              </div>
            ))}
          </div>

          {/* Calendar Body */}
          <div className="flex-1 flex flex-col">
            {weeks.map((week, weekIdx) => {
              const refDay = week.find(d => d !== null);
              if (!refDay) return null;
              const refIdx = week.indexOf(refDay);

              const trueWeekStart = new Date(refDay);
              trueWeekStart.setDate(refDay.getDate() - refIdx);
              const trueWeekStartStr = toDateStr(trueWeekStart);

              const trueWeekEnd = new Date(refDay);
              trueWeekEnd.setDate(refDay.getDate() - refIdx + 4);
              const trueWeekEndStr = toDateStr(trueWeekEnd);

              const weekEvents = events.filter((evt: any) => {
                const eStart = extractDateStr(evt.start_date || evt.start);
                const eEnd = extractDateStr(evt.end_date || evt.end);
                return eStart <= trueWeekEndStr && eEnd >= trueWeekStartStr;
              });

              return (
                <div key={weekIdx} className="relative w-full grow shrink-0 basis-auto border-b border-slate-200 dark:border-zinc-800 last:border-b-0 min-h-[120px]">

                  {/* Background Day Cells */}
                  <div className="absolute inset-0 grid grid-cols-5">
                    {week.map((day, dayIdx) => {
                      const isToday = day && toDateStr(day) === toDateStr(new Date());
                      return (
                        <div
                          key={dayIdx}
                          onClick={() => {
                            if (!day) return;
                            const dStr = toDateStr(day);
                            const defaultUserId = currentUser?.role === 'admin' ? '' : (currentUser?.id || '');

                            setActiveHoliday({
                              event_type: 'personal_time_off',
                              user_id: defaultUserId,
                              location_id: '',
                              start_date: dStr,
                              end_date: dStr
                            });
                            setModalOpen(true);
                          }}
                          className={`border-r border-slate-200 dark:border-zinc-800 last:border-r-0 p-3 h-full cursor-pointer transition-colors ${!day ? 'bg-slate-50/50 dark:bg-zinc-950/50' : 'hover:bg-slate-50 dark:hover:bg-zinc-800/30'}`}
                        >
                          {day && (
                            <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${isToday ? 'bg-blue-600 text-white shadow-md' : 'text-slate-600 dark:text-zinc-400'}`}>
                              {day.getDate()}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Event Bars Overlay - Content Layer expands parent so no absolute clipping/overlaps occur! */}
                  <div className="relative z-10 pt-14 pb-2 pointer-events-none grid grid-cols-5 auto-rows-max gap-y-1 px-1">
                    {weekEvents.map((evt: any, evtIdx: number) => {
                      const eStart = extractDateStr(evt.start_date || evt.start);
                      const eEnd = extractDateStr(evt.end_date || evt.end);
                      const eType = evt.event_type || evt.type;

                      let startCol = null;
                      let endCol = null;

                      for (let idx = 0; idx < 5; idx++) {
                        const cellDate = new Date(trueWeekStart);
                        cellDate.setDate(trueWeekStart.getDate() + idx);
                        const cellDateStr = toDateStr(cellDate);

                        if (cellDateStr >= eStart && cellDateStr <= eEnd) {
                          if (startCol === null) startCol = idx + 1;
                          endCol = idx + 2;
                        }
                      }

                      if (startCol === null) return null;

                      const user = localPentesters.find((p: any) => p.id === evt.user_id);
                      let label = user?.name || 'Unknown User';

                      let bgClass, borderClass, textClass;

                      if (eType === 'national_holiday') {
                        bgClass = 'bg-red-100 dark:bg-red-500/20'; borderClass = 'border-red-500'; textClass = 'text-red-800 dark:text-red-400';
                        const locName = locations.find(l => l.id === evt.location_id)?.name || 'Global';
                        label = `🌍 Public Holiday (${locName})`;
                      } else if (eType === 'team_day') {
                        bgClass = 'bg-fuchsia-100 dark:bg-fuchsia-500/20'; borderClass = 'border-fuchsia-500'; textClass = 'text-fuchsia-800 dark:text-fuchsia-400';
                        label = `🚀 Team Day`;
                      } else if (eType === 'sick_day') {
                        bgClass = 'bg-orange-100 dark:bg-orange-500/20'; borderClass = 'border-orange-500'; textClass = 'text-orange-800 dark:text-orange-400';
                        label = `🤒 ${user?.name || 'Unknown User'} (Sick)`;
                      } else {
                        const theme = getUserColor(user?.id, localPentesters);
                        bgClass = theme.bg; borderClass = theme.border; textClass = theme.text;
                      }

                      const isAdmin = currentUser?.role === 'admin';
                      const isOwner = String(user?.id) === String(currentUser?.id);
                      const canEdit = isAdmin || (['personal_time_off', 'sick_day'].includes(eType) && isOwner);

                      return (
                        <div
                          key={evt.id || evtIdx}
                          title={label}
                          onClick={(e) => {
                            e.stopPropagation();
                            if (!canEdit) return;
                            setActiveHoliday({
                              id: evt.id,
                              event_type: eType,
                              user_id: evt.user_id || '',
                              location_id: evt.location_id || '',
                              start_date: eStart,
                              end_date: eEnd
                            });
                            setModalOpen(true);
                          }}
                          style={{ gridColumn: `${startCol} / ${endCol}` }}
                          className={`mx-1 px-2.5 py-1.5 rounded-lg text-xs font-bold truncate pointer-events-auto shadow-sm transition-transform hover:scale-[1.01] flex items-center gap-1.5 ${bgClass} ${textClass} ${canEdit ? 'cursor-pointer hover:opacity-80' : 'cursor-default'} ${startCol !== 1 || eStart >= trueWeekStartStr ? `border-l-4 ${borderClass}` : ''}`}
                        >
                          {eType === 'personal_time_off' && user?.name && (
                            <div className="w-4 h-4 rounded-full shadow-sm shrink-0 bg-black/20 flex items-center justify-center text-[10px] font-bold">
                              {user?.name?.charAt(0).toUpperCase() || 'U'}
                            </div>
                          )}
                          <span className="truncate">{label}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <HolidayModal
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          holidayData={activeHoliday}
          setHolidayData={setActiveHoliday}
          pentesters={activeHolidayPentesters}
          locations={locations}
          currentUser={currentUser}
          onSave={async () => {
            try {
              const payload = {
                event_type: activeHoliday.event_type,
                location_id: activeHoliday.location_id === '' ? null : activeHoliday.location_id,
                start_date: activeHoliday.start_date,
                end_date: activeHoliday.end_date,
                user_id: activeHoliday.user_id || null
              };

              if (activeHoliday.id) await axios.put(`/api/board/events/${activeHoliday.id}`, payload);
              else await axios.post('/api/board/events', payload);

              toast.success("Time off saved!");
              setModalOpen(false);

              // Refresh board data so new events appear immediately
              const currentYear = new Date().getFullYear();
              const currentMonth = new Date().getMonth() + 1;
              let quarter = 1;
              if (currentMonth > 3) quarter = 2;
              if (currentMonth > 6) quarter = 3;
              if (currentMonth > 9) quarter = 4;

              axios.get(`/api/board/${currentYear}/Q${quarter}`).then(res => setBoardData(res.data || {}));

            } catch (err: any) {
              toast.error(err.response?.data?.detail || "Failed to save.");
            }
          }}
          onDelete={async (id) => {
            try {
              await axios.delete(`/api/board/events/${id}`);
              toast.success("Time off deleted!");
              setModalOpen(false);

              // Refresh board data after deletion
              const currentYear = new Date().getFullYear();
              const currentMonth = new Date().getMonth() + 1;
              let quarter = 1;
              if (currentMonth > 3) quarter = 2;
              if (currentMonth > 6) quarter = 3;
              if (currentMonth > 9) quarter = 4;

              axios.get(`/api/board/${currentYear}/Q${quarter}`).then(res => setBoardData(res.data || {}));

            } catch (err: any) {
              toast.error(err.response?.data?.detail || "Failed to delete.");
            }
          }}
        />
      </main>
    </div>
  );
}