import React, { useState } from 'react';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import type { DropResult, DragStart } from '@hello-pangea/dnd';
import { useNavigate } from 'react-router-dom';
import TestHistoryModal from '../components/Modals/TestHistoryModal';
import AssignTeamModal from '../components/Modals/AssignTeamModal';
import SecureNoteModal from "../components/Modals/SecureNoteModal";
import ConfirmModal from "../components/Modals/ConfirmModal";
import TopNav from '../components/TopNav';
import { useAppContext } from '../context/AppContext';
import { getWeekDateRange } from '../utils/helpers';
import type { BoardData, Test } from '../types/board';
import { ChevronLeft, ChevronRight, Search, X, History, Edit2, Trash2, Plus, Users, CheckCircle, XCircle, CalendarOff, User, LockOpen, Lock } from 'lucide-react';

interface PlannerViewProps {
  onlineUsers: string[];
  targetYear: number;
  targetQuarter: number;
  handlePrevQuarter: () => void;
  handleNextQuarter: () => void;
  handleCurrentQuarter: () => void;
  boardData: BoardData | null;
  setNewTest: (test: any) => void;
  setShowTestForm: (show: boolean) => void;
  onDragEnd: (result: DropResult) => void;
  handleAssignTeam: (userId: string) => void;
  handleCompleteTest: (testId: string) => void;
  handleUnscheduleTest: (testId: string) => void;
  handleUnassignPentester: (testId: string, userId: string) => void;
  handleDeleteTest: (testId: string) => void;
  handleDuplicateTest: (testId: string) => void;
  openEditModal: (test: Test) => void;
  handleMarkUnable: (testId: string) => void;
  handleRevertComplete: (testId: string) => void;
  handleRevertUnable: (testId: string) => void;
  assignModalTest: Test | null;
  setAssignModalTest: (test: Test | null) => void;
  backlogFilter: string;
  setBacklogFilter: (filter: string) => void;
  setTargetYear: (year: number) => void;
}

const getISOWeek = (date: Date) => {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
};

const getTintedBg = (hexColor?: string) => {
  if (!hexColor) return 'transparent';
  if (hexColor.startsWith('#') && hexColor.length === 7) return `${hexColor}10`;
  return hexColor;
};

export default function PlannerView({
  onlineUsers, targetYear, targetQuarter, handlePrevQuarter, handleNextQuarter, handleCurrentQuarter,
  boardData, setNewTest, setShowTestForm,
  onDragEnd, handleAssignTeam, handleCompleteTest, handleUnscheduleTest, handleUnassignPentester,
  handleDeleteTest, handleDuplicateTest, openEditModal, handleMarkUnable, handleRevertComplete, handleRevertUnable,
  assignModalTest, setAssignModalTest, backlogFilter, setBacklogFilter, setTargetYear
}: PlannerViewProps) {

  const navigate = useNavigate();
  const { currentUser } = useAppContext();

  const displayWeeks = boardData?.weeks || [];
  const [isBacklogOpen, setIsBacklogOpen] = useState(false);
  const [draggingServiceId, setDraggingServiceId] = useState<string | null>(null);
  const [draggingSourceId, setDraggingSourceId] = useState<string | null>(null);
  const [historyTest, setHistoryTest] = useState<Test | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const [highlightMine, setHighlightMine] = useState(false);

  const currentRealWeek = getISOWeek(new Date());
  const currentRealYear = new Date().getFullYear();

  const [secretTarget, setSecretTarget] = useState<Test | null>(null);
  const [secretConfirmOpen, setSecretConfirmOpen] = useState<Test | null>(null);

  const handleDragStart = (start: DragStart) => {
    const { draggableId, source } = start;
    setDraggingSourceId(source.droppableId);
    const draggedTest = source.droppableId === 'backlog'
      ? boardData?.backlog?.find(t => String(t.id) === String(draggableId))
      : boardData?.scheduled?.find(t => String(t.id) === String(draggableId));
    if (draggedTest) setDraggingServiceId(draggedTest.service_lane_id);
  };

  const handleDragEnd = (result: DropResult) => {
    setDraggingServiceId(null);
    setDraggingSourceId(null);
    onDragEnd(result);
  };

  if (!boardData || !boardData.services) {
    return <div className="p-12 text-slate-500 font-bold text-center mt-20">Loading board architecture...</div>;
  }

  return (
    <DragDropContext onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div className="flex flex-col h-screen dark:bg-zinc-950 text-sm text-slate-700 dark:text-zinc-300 overflow-hidden font-sans">
        <TopNav />

        <div className="flex justify-between items-center px-6 py-3  dark:bg-zinc-900/80 backdrop-blur-md border-b border-slate-200 dark:border-zinc-800 z-20 shadow-sm shrink-0 pt-32">
          <div className="flex w-1/3 justify-start">
            <div className="flex items-center dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg p-1">
              <button className="p-1.5 hover:bg-slate-200 dark:hover:bg-zinc-800 rounded-md text-slate-500 transition-colors" onClick={handlePrevQuarter}><ChevronLeft size={16} /></button>
              <div className="mx-3 flex items-center gap-1.5 bg-slate-100 dark:bg-zinc-800/80 px-2 py-1 rounded-md shadow-inner">
                <span className="text-sm text-slate-900 dark:text-zinc-100 font-extrabold">Q{targetQuarter}</span>
                {/* 1. FIXED HOVER COLOR ON NAVIGATOR */}
                <select
                  className="bg-transparent font-bold text-sm text-slate-900 dark:text-zinc-100 outline-none cursor-pointer hover:opacity-70 transition-opacity appearance-none pr-2"
                  value={targetYear}
                  onChange={(e) => setTargetYear(parseInt(e.target.value))}
                >
                  {[2025, 2026, 2027, 2028, 2029, 2030, 2031].map(y => (
                    <option key={y} value={y} className="bg-white dark:bg-zinc-800">{y}</option>
                  ))}
                </select>
              </div>
              <button className="p-1.5 hover:bg-slate-200 dark:hover:bg-zinc-800 rounded-md text-slate-500 transition-colors" onClick={handleNextQuarter}><ChevronRight size={16} /></button>
              <div className="w-px h-5 bg-slate-300 dark:bg-zinc-700 mx-1"></div>
              <button className="ml-1 px-3 py-1 text-xs font-bold dark:bg-zinc-800 border border-slate-300 dark:border-zinc-700 rounded-md shadow-sm text-slate-600 dark:text-zinc-300 hover:bg-slate-50 dark:hover:bg-zinc-700 transition-colors" onClick={handleCurrentQuarter}>Today</button>
            </div>
          </div>

          <div className="flex justify-center w-1/3">
            <div className="relative w-full max-w-md">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input type="text" placeholder="Search app or person..." className="pl-9 pr-4 py-1.5 bg-white dark:bg-zinc-950 border border-slate-300 dark:border-zinc-700 rounded-full text-xs w-full focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-slate-900 dark:text-zinc-100" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} />
            </div>
          </div>

          <div className="flex items-center justify-end gap-4 w-1/3">
            <div className="flex items-center gap-3 pr-4 border-r border-slate-200 dark:border-zinc-800">
              <button
                onClick={() => setHighlightMine(!highlightMine)}
                className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 shadow-sm ${highlightMine ? 'bg-blue-600 text-white border-transparent' : 'bg-white dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 border border-slate-200 dark:border-zinc-700 hover:bg-slate-50 dark:hover:bg-zinc-700'}`}
              >
                <User size={14} /> My Schedule
              </button>
              <div className="w-px h-5 bg-slate-200 dark:bg-zinc-800 mx-1"></div>
              <div className="flex -space-x-2">
                <div title="You" className="w-7 h-7 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold border-2 border-white dark:border-zinc-900 z-10 shadow-sm overflow-hidden">
                  {currentUser?.name?.charAt(0).toUpperCase() || 'U'}
                </div>

                {onlineUsers.filter(email => email !== currentUser?.email).map((email, idx) => {
                  const userDetails = boardData.pentesters.find(p => p.email === email);
                  const initial = userDetails?.name?.charAt(0).toUpperCase() || (typeof email === 'string' ? email.charAt(0).toUpperCase() : '?');

                  return (
                    <div
                      key={email || idx}
                      title={userDetails?.name || email}
                      className="w-7 h-7 rounded-full bg-emerald-500 text-white flex items-center justify-center text-xs font-bold border-2 border-white dark:border-zinc-900 shadow-sm overflow-hidden"
                      style={{ zIndex: 9 - idx }}
                    >
                      {initial}
                    </div>
                  );
                })}
              </div>
            </div>

            {currentUser?.role === 'admin' && (
              <div className="flex items-center gap-2">
                {!isBacklogOpen && (
                  <button className="px-4 py-1.5 text-xs font-bold text-slate-700 dark:text-zinc-300 bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700 rounded-lg transition-colors" onClick={() => setIsBacklogOpen(true)}>
                    Show Backlog
                  </button>
                )}
                <button className="px-4 py-1.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg flex items-center gap-1.5 shadow-sm transition-colors" onClick={() => navigate('/assets')}>
                  <Plus size={14}/> Test from Assets
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden w-full relative">
          <div className="flex-1 min-w-0 overflow-auto bg-slate-50 dark:bg-zinc-950/50 transition-all">
            <table className="w-max min-w-full border-separate border-spacing-0">
              <thead className="bg-slate-50/90 dark:bg-zinc-900/90 backdrop-blur-md relative z-[40]">
                <tr>
                  <th className="p-4 border-b-2 border-r-2 border-slate-300 dark:border-zinc-700 text-left sticky top-0 left-0 z-[50] bg-slate-50/95 dark:bg-zinc-900/95 backdrop-blur-xl shadow-[2px_0_5px_rgba(0,0,0,0.05)] min-w-[200px]">
                    <span className="font-bold text-slate-700 dark:text-zinc-300">Service Lanes</span>
                  </th>
                  {displayWeeks.map(week => {
                    const isCurrent = week === currentRealWeek && targetYear === currentRealYear;
                    const totalWeekCap = boardData.pentesters.reduce((sum, p) => sum + (boardData.capacities?.[p.id]?.[week] || 0), 0);

                    return (
                      <th key={week} className={`p-4 border-b-2 border-r border-slate-200 dark:border-zinc-800 sticky top-0 z-[40] min-w-[240px] bg-slate-50/95 dark:bg-zinc-900/95 backdrop-blur-xl ${isCurrent ? 'border-l-2 border-r-2 border-l-blue-500 border-r-blue-500' : ''}`}>
                        <div className={`text-sm font-bold ${isCurrent ? 'text-blue-700 dark:text-blue-400' : 'text-slate-900 dark:text-zinc-100'}`}>Week {week} {isCurrent && '(Current)'}</div>
                        <div className="text-xs font-normal text-slate-500 dark:text-zinc-400 mt-0.5">{getWeekDateRange(targetYear, week)}</div>

                        <div className="relative group w-fit cursor-help">
                          <div className={`text-xs font-bold mt-1.5 ${totalWeekCap >= 1 ? 'text-emerald-600' : 'text-red-500'}`}>
                            Avail: {totalWeekCap.toFixed(1)} cr
                          </div>

                          <div className="absolute top-full left-0 mt-2 w-48 bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 rounded-xl shadow-xl py-2 opacity-0 group-hover:opacity-100 transition-opacity z-[100] pointer-events-none">
                             <div className="px-3 pb-1 mb-1 border-b border-slate-100 dark:border-zinc-700/50 text-[10px] font-bold text-slate-400 uppercase tracking-wider">Available Staff</div>
                             {boardData.pentesters.filter(p => (boardData.capacities[p.id]?.[week] || 0) > 0).map(p => (
                                 <div key={p.id} className="px-3 py-1 flex justify-between text-xs items-center">
                                    <span className="font-medium text-slate-700 dark:text-zinc-300 truncate max-w-[120px]">{p.name}</span>
                                    <span className="text-emerald-600 dark:text-emerald-400 font-bold bg-emerald-50 dark:bg-emerald-500/10 px-1.5 rounded">{(boardData.capacities[p.id]?.[week] || 0).toFixed(1)}</span>
                                 </div>
                             ))}
                             {boardData.pentesters.filter(p => (boardData.capacities[p.id]?.[week] || 0) > 0).length === 0 && (
                                 <div className="px-3 py-2 text-xs text-slate-500 italic text-center">No available staff</div>
                             )}
                          </div>
                        </div>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {boardData.services.map(service => (
                  <tr key={service.id} style={{ backgroundColor: getTintedBg(service.theme_color) }}>

                    {/* 2. FIXED Z-INDEX: Side Column is z-[30] */}
                    <td className="px-4 py-3 font-bold text-slate-900 dark:text-zinc-100 border-b border-r-2 border-slate-300 dark:border-zinc-700 sticky left-0 z-[30] bg-slate-50/95 dark:bg-zinc-900/95 backdrop-blur-xl shadow-[2px_0_5px_rgba(0,0,0,0.05)]">
                      <div className="flex items-center gap-3">
                        <div className="w-3 h-3 rounded-full shadow-sm shrink-0" style={{ backgroundColor: service.theme_color }} />
                        <span className="truncate max-w-[160px]" title={service.name}>{service.name}</span>
                      </div>
                    </td>

                    {displayWeeks.map(week => {
                      const cellId = `${service.id}_${week}`;
                      const testsInThisCell = boardData.scheduled.filter(t => t.service_lane_id === service.id && t.startYear === targetYear && week >= (t.startWeek || 0) && week < ((t.startWeek || 0) + t.duration));

                      // Safely cast to number, default to 0
                      const maxConcurrent = service.max_concurrent_per_week || 0;
                      // If maxConcurrent is > 0, check if we hit the limit
                      const isAtCapacity = maxConcurrent > 0 ? testsInThisCell.length >= maxConcurrent : false;

                      const isInvalidDropTarget = (draggingServiceId && draggingServiceId !== service.id) || (draggingSourceId && draggingSourceId !== cellId && isAtCapacity);
                      const isValidDropTarget = draggingServiceId && draggingServiceId === service.id && !isInvalidDropTarget;
                      const isCurrent = week === currentRealWeek && targetYear === currentRealYear;

                      return (
                        <td key={cellId} className={`p-1.5 border-b border-r border-slate-200/70 dark:border-zinc-800/70 align-top min-h-[120px] transition-colors ${
                          isInvalidDropTarget ? 'bg-slate-100/50 dark:bg-zinc-950/80' :
                          isValidDropTarget ? 'bg-blue-50/30 dark:bg-blue-900/10' :
                          isCurrent ? 'bg-black/[0.01] dark:bg-white/[0.01] border-l-[3px] border-r-[3px] border-l-blue-400/50 border-r-blue-400/50' : 'bg-transparent'
                        }`}>
                          <Droppable droppableId={cellId} isDropDisabled={!!isInvalidDropTarget}>
                            {(provided, snapshot) => (
                              <div
                                ref={provided.innerRef}
                                {...provided.droppableProps}
                                className={`min-h-[120px] w-full h-full rounded-xl p-1.5 transition-all border-2 ${snapshot.isDraggingOver ? 'border-dashed shadow-inner' : 'border-transparent hover:border-slate-200/50 dark:hover:border-zinc-800/50'}`}
                                style={snapshot.isDraggingOver ? {
                                  backgroundColor: getTintedBg(service.theme_color),
                                  borderColor: service.theme_color
                                } : {}}
                              >
                                {testsInThisCell.map((test, index) => {
                                  const weekAssignments = boardData.assignments.filter(a => a.test_id === test.id && a.week_number === week);
                                  const totalProvided = weekAssignments.reduce((sum, a) => sum + a.allocated_credits, 0);
                                  const isAssignedToMe = weekAssignments.some(a => String(a.user_id) === String(currentUser?.id));

                                  const isSearchActive = searchQuery.trim().length > 0;
                                  const searchLower = searchQuery.toLowerCase();
                                  const testMatchesSearch = !isSearchActive || (test.name || '').toLowerCase().includes(searchLower) || weekAssignments.some(a => (a.user_name || '').toLowerCase().includes(searchLower));

                                  const shouldDim = (highlightMine && !isAssignedToMe) || !testMatchesSearch;

                                  const percentage = test.credits > 0 ? (totalProvided / test.credits) * 100 : 0;
                                  const uiPercentage = Math.min(100, percentage);
                                  const progressColor = percentage >= 100 ? 'bg-emerald-500' : percentage > 70 ? 'bg-blue-500' : 'bg-orange-500';

                                  const renderQualityAndTeam = () => (
                                    <div className="mt-2.5 flex flex-col gap-2">
                                      <div className="w-full bg-slate-100 dark:bg-zinc-800 rounded-full h-1.5 flex overflow-hidden">
                                        <div className={`h-full ${progressColor} transition-all duration-300`} style={{ width: `${uiPercentage}%` }} />
                                      </div>
                                      <div className="flex justify-between items-center text-[9px] font-bold text-slate-500 dark:text-zinc-400">
                                        <span>{totalProvided.toFixed(1)} / {test.credits} cr</span>
                                        <span>{Math.round(percentage)}%</span>
                                      </div>

                                      {weekAssignments.length > 0 && (
                                        <div className="flex flex-wrap gap-1 mt-1">
                                          {weekAssignments.map(a => (
                                            <span key={a.user_id} className={`text-[10px] flex items-center gap-1 px-1.5 py-0.5 rounded-md border ${String(a.user_id) === String(currentUser?.id) ? 'bg-blue-50 border-blue-200 text-blue-700 font-bold dark:bg-blue-900/20 dark:border-blue-800/50' : 'bg-slate-50 border-slate-200 text-slate-600 dark:bg-zinc-800/50 dark:border-zinc-700'}`}>
                                              {(a.user_name || 'Unknown').split(' ')[0]}
                                              {currentUser?.role === 'admin' && test.status !== 'Completed' && test.status !== 'Stopped' && (
                                                <X size={10} className="cursor-pointer text-slate-400 hover:text-red-500 transition-colors ml-0.5" onClick={() => handleUnassignPentester(test.id, a.user_id)} />
                                              )}
                                            </span>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  );

                                  if (test.startWeek === week) {
                                    return (
                                      <Draggable key={test.id} draggableId={test.id} index={index} isDragDisabled={currentUser?.role === 'pentester' || test.status === 'Completed' || test.status === 'Stopped'}>
                                        {(provided) => (
                                            <div ref={provided.innerRef} {...provided.draggableProps} {...provided.dragHandleProps}
                                              className={`p-3.5 bg-white dark:bg-zinc-900 rounded-xl shadow-md hover:shadow-xl hover:-translate-y-0.5 mb-2.5 transition-all duration-200 group relative overflow-hidden ${
                                                test.status === 'Stopped' ? 'border border-red-200 bg-red-50/30 dark:border-red-900/50 dark:bg-red-950/20' :
                                                isAssignedToMe ? 'border-2 border-blue-400 dark:border-blue-500 shadow-[0_4px_12px_rgba(59,130,246,0.2)]' :
                                                'border border-slate-200 dark:border-zinc-700/80'
                                              } ${shouldDim ? 'opacity-20 grayscale' : 'opacity-100'}`}
                                            >
                                              <div className="absolute top-0 left-0 right-0 h-1" style={{ backgroundColor: test.status === 'Stopped' ? '#ef4444' : test.status === 'Completed' ? '#10b981' : service.theme_color }} />

                                              <div className="flex justify-between items-start mb-1 mt-1">
                                                <div className="font-bold text-xs text-slate-900 dark:text-zinc-100 leading-tight pr-4">
                                                  {test.name}
                                                </div>
                                                {test.status === 'Completed' && <span className="text-[9px] font-black bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-md uppercase tracking-wide shrink-0">Done</span>}
                                                {test.status === 'Stopped' && <span className="text-[9px] font-black bg-red-100 text-red-700 px-1.5 py-0.5 rounded-md uppercase tracking-wide shrink-0">Stop</span>}
                                              </div>

                                              {renderQualityAndTeam()}

                                              {currentUser?.role === 'admin' && (
                                                <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-white/90 dark:bg-zinc-800/90 backdrop-blur-sm rounded-lg shadow-sm border border-slate-100 dark:border-zinc-700 flex items-center p-0.5 z-[100]">
                                                  {test.status === 'Completed' ? (
                                                    <>
                                                      <button title="Undo Done" className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-zinc-300 transition-colors" onClick={() => handleRevertComplete(test.id)}><XCircle size={14}/></button>
                                                      <button title="History" className="p-1.5 text-blue-500 hover:text-blue-600 transition-colors" onClick={() => setHistoryTest(test)}><History size={14}/></button>
                                                    </>
                                                  ) : test.status === 'Stopped' ? (
                                                    <>
                                                      <button title="Undo Stop" className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-zinc-300 transition-colors" onClick={() => handleRevertUnable(test.id)}><XCircle size={14}/></button>
                                                      <button title="History" className="p-1.5 text-blue-500 hover:text-blue-600 transition-colors" onClick={() => setHistoryTest(test)}><History size={14}/></button>
                                                    </>
                                                  ) : (
                                                    <>
                                                      {service.is_active && (
                                                        <button title="Assign Staff" className="p-1.5 text-blue-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors" onClick={() => setAssignModalTest(test)}><Users size={14}/></button>
                                                      )}
                                                      <button title="Mark Done" className="p-1.5 text-emerald-500 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/30 rounded transition-colors" onClick={() => handleCompleteTest(test.id)}><CheckCircle size={14}/></button>
                                                      <button title="Stop Test" className="p-1.5 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors" onClick={() => handleMarkUnable(test.id)}><XCircle size={14}/></button>
                                                      <button title="Unschedule" className="p-1.5 text-amber-500 hover:text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-900/30 rounded transition-colors" onClick={() => handleUnscheduleTest(test.id)}><CalendarOff size={14}/></button>
                                                      <button title="Edit" className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-700 rounded transition-colors" onClick={() => openEditModal(test)}><Edit2 size={14}/></button>
                                                    </>
                                                  )}
                                                  {currentUser?.role !== 'read_only' && (test.has_secret || service?.is_active) && (
                                                    <button
                                                      onClick={() => setSecretConfirmOpen(test)}
                                                      className={`p-1.5 rounded transition-colors ${test.has_secret ? 'text-indigo-600 bg-indigo-100 dark:bg-indigo-900/30' : 'text-slate-400 hover:text-indigo-500 hover:bg-slate-100 dark:hover:bg-zinc-800'}`}
                                                      title={test.has_secret ? "View Secure Note" : "Add Secure Note"}
                                                    >
                                                      {test.has_secret ? <Lock size={14} /> : <LockOpen size={14} />}
                                                    </button>
                                                  )}
                                                </div>
                                              )}
                                            </div>
                                        )}
                                      </Draggable>
                                    );
                                  } else {
                                    return (
                                      <div key={`${test.id}-ghost`} className={`p-3 bg-white/40 dark:bg-zinc-900/40 rounded-xl shadow-sm border border-dashed mb-2.5 relative overflow-hidden transition-all ${test.status === 'Stopped' ? 'border-red-300' : 'border-slate-300 dark:border-zinc-700'} ${shouldDim ? 'opacity-20 grayscale' : 'opacity-100'}`}>
                                        <div className="absolute top-0 left-0 right-0 h-1 opacity-50" style={{ backgroundColor: test.status === 'Stopped' ? '#ef4444' : test.status === 'Completed' ? '#10b981' : service.theme_color }} />
                                        <div className="font-bold text-[11px] text-slate-500 dark:text-zinc-400 flex items-center gap-1 mt-1">
                                          ↳ {test.name}
                                          {isAssignedToMe && test.status !== 'Stopped' && test.status !== 'Completed' && <span className="ml-1 text-[8px] bg-blue-100 text-blue-700 px-1 rounded">You</span>}
                                        </div>
                                        {renderQualityAndTeam()}
                                      </div>
                                    );
                                  }
                                })}
                                {provided.placeholder}
                              </div>
                            )}
                          </Droppable>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {isBacklogOpen && currentUser?.role !== 'pentester' && (
            <div className="w-[320px] shrink-0 bg-white/90 dark:bg-zinc-900/90 backdrop-blur-md border-l border-slate-200 dark:border-zinc-800 flex flex-col z-[50] shadow-[-4px_0_15px_rgba(0,0,0,0.03)] animate-in slide-in-from-right-8">
              <div className="p-4 bg-slate-50/50 dark:bg-zinc-950/50 border-b border-slate-200 dark:border-zinc-800 flex flex-col gap-3 shrink-0">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-sm text-slate-900 dark:text-zinc-100">Backlog Queue</h3>
                    <span className="bg-slate-200 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 px-2 py-0.5 rounded-full text-xs font-bold">
                      {boardData.backlog.filter(t => backlogFilter === 'All' || String(t.service_lane_id) === String(backlogFilter)).length}
                    </span>
                  </div>
                  <button onClick={() => setIsBacklogOpen(false)} className="text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 transition-colors p-1">
                    <X size={16} />
                  </button>
                </div>

                <select className="w-full p-2 bg-white dark:bg-zinc-900 border border-slate-300 dark:border-zinc-700 rounded-lg text-xs font-medium text-slate-700 dark:text-zinc-300 focus:ring-2 focus:ring-blue-500 outline-none" value={backlogFilter} onChange={e => setBacklogFilter(e.target.value)}>
                  <option value="All">All Services</option>
                  {boardData.services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>

              <div className="flex-1 overflow-y-auto p-4 bg-slate-50/50 dark:bg-zinc-950/30">
                <Droppable droppableId="backlog" direction="vertical" isDropDisabled={['pentester', 'read_only'].includes(currentUser?.role)}>
                  {(provided) => {
                    const sortedBacklog = [...boardData.backlog].filter(t => backlogFilter === 'All' || String(t.service_lane_id) === String(backlogFilter))
                      .sort((a, b) => {
                        const sA = boardData.services.find(s => s.id === a.service_lane_id)?.name || '';
                        const sB = boardData.services.find(s => s.id === b.service_lane_id)?.name || '';
                        return sA.localeCompare(sB);
                      });

                    return (
                      <div ref={provided.innerRef} {...provided.droppableProps} className="min-h-full">
                        {sortedBacklog.map((test, index) => {
                          const service = boardData.services.find(s => s.id === test.service_lane_id);
                          const isSearchActive = searchQuery.trim().length > 0;
                          const testMatchesSearch = !isSearchActive || (test.name || '').toLowerCase().includes(searchQuery.toLowerCase());

                          return (
                            <Draggable key={test.id} draggableId={test.id} index={index} isDragDisabled={['pentester', 'read_only'].includes(currentUser?.role)}>
                              {(provided) => (
                                <div ref={provided.innerRef} {...provided.draggableProps} {...provided.dragHandleProps}
                                  className={`p-3 bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700/50 rounded-xl mb-2.5 cursor-grab flex flex-col shadow-sm hover:shadow-md transition-all group ${testMatchesSearch ? 'opacity-100' : 'opacity-30 grayscale'}`}
                                >
                                  <div className="flex items-center gap-2 mb-1.5">
                                    <div className="w-2.5 h-2.5 rounded-full shrink-0 shadow-sm" style={{ backgroundColor: service?.theme_color || '#cbd5e1' }} />
                                    <div className="font-bold text-xs text-slate-900 dark:text-zinc-100 truncate flex-1" title={test.name}>{test.name}</div>
                                  </div>

                                  <div className="flex justify-between items-center text-[10px] text-slate-500 dark:text-zinc-400 font-medium">
                                    <span>{test.credits} cr • {test.duration} wk</span>

                                    {currentUser?.role === 'admin' && (
                                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button title="History" className="p-1 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors" onClick={() => setHistoryTest(test)}><History size={12} /></button>
                                        <button title="Edit Settings" className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:hover:text-zinc-300 dark:hover:bg-zinc-700 rounded transition-colors" onClick={() => openEditModal(test)}><Edit2 size={12} /></button>
                                        <button title="Delete Permanently" className="p-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors" onClick={() => handleDeleteTest(test.id)}><Trash2 size={12} /></button>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              )}
                            </Draggable>
                          );
                        })}
                        {provided.placeholder}
                      </div>
                    )
                  }}
                </Droppable>
              </div>
            </div>
          )}
        </div>
      </div>

      <AssignTeamModal assignModalTest={assignModalTest} setAssignModalTest={setAssignModalTest} boardData={boardData} handleAssignTeam={handleAssignTeam} targetYear={targetYear} />
      {historyTest && <TestHistoryModal test={historyTest} onClose={() => setHistoryTest(null)} />}
      <ConfirmModal
        isOpen={!!secretConfirmOpen}
        variant="secure"
        title="Access Secure Vault"
        message="You are about to decrypt sensitive credentials. Proceed?"
        confirmText="Decrypt & Open"
        onConfirm={() => { setSecretTarget(secretConfirmOpen); setSecretConfirmOpen(null); }}
        onCancel={() => setSecretConfirmOpen(null)}
       />
      {secretTarget && <SecureNoteModal test={secretTarget} onClose={() => setSecretTarget(null)} />}
    </DragDropContext>
  );
}