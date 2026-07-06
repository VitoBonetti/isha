import React, { useState } from 'react';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import type { DropResult, DragStart } from '@hello-pangea/dnd';
import { useNavigate } from 'react-router-dom';
import TestHistoryModal from '../components/Modals/TestHistoryModal';
import AssignTeamModal from '../components/Modals/AssignTeamModal';
import TopNav from '../components/TopNav';
import { useAppContext } from '../context/AppContext';
import { getWeekDateRange } from '../utils/helpers';
import type { BoardData, Test } from '../types/board';
import { ChevronLeft, ChevronRight, Search, X, History, Edit2, Trash2, Plus, Users, CheckCircle, XCircle } from 'lucide-react';

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
  if (hexColor.startsWith('#') && hexColor.length === 7) return `${hexColor}1E`;
  return hexColor;
};

export default function PlannerView({
  onlineUsers, targetYear, targetQuarter, handlePrevQuarter, handleNextQuarter, handleCurrentQuarter,
  boardData, setNewTest, setShowTestForm,
  onDragEnd, handleAssignTeam, handleCompleteTest, handleUnscheduleTest, handleUnassignPentester,
  handleDeleteTest, handleDuplicateTest, openEditModal, handleMarkUnable, handleRevertComplete, handleRevertUnable,
  assignModalTest, setAssignModalTest, backlogFilter, setBacklogFilter
}: PlannerViewProps) {

  const navigate = useNavigate();
  const { currentUser } = useAppContext();

  const displayWeeks = boardData?.weeks || [];
  const [isBacklogOpen, setIsBacklogOpen] = useState(true);
  const [draggingServiceId, setDraggingServiceId] = useState<string | null>(null);
  const [historyTest, setHistoryTest] = useState<Test | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const currentRealWeek = getISOWeek(new Date());
  const currentRealYear = new Date().getFullYear();

  const handleDragStart = (start: DragStart) => {
    const { draggableId, source } = start;
    const draggedTest = source.droppableId === 'backlog'
      ? boardData?.backlog?.find(t => String(t.id) === String(draggableId))
      : boardData?.scheduled?.find(t => String(t.id) === String(draggableId));

    if (draggedTest) setDraggingServiceId(draggedTest.service_lane_id);
  };

  const handleDragEnd = (result: DropResult) => {
    setDraggingServiceId(null);
    onDragEnd(result);
  };

  if (!boardData || !boardData.services) {
    return <div className="p-12 text-slate-500 font-bold text-center mt-20">Loading board architecture...</div>;
  }

  return (
    <DragDropContext onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div className="flex flex-col h-screen dark:bg-zinc-950 text-sm text-slate-700 dark:text-zinc-300 overflow-hidden font-sans">
        <TopNav />

        <div className="flex justify-between items-center px-6 py-3 dark:bg-zinc-900 border-b border-slate-200 dark:border-zinc-800 z-20 shadow-sm shrink-0 pt-32">

          <div className="flex w-1/3 justify-start">
            <div className="flex items-center bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg p-1">
              <button className="p-1.5 hover:bg-slate-200 dark:hover:bg-zinc-800 rounded-md text-slate-500 transition-colors" onClick={handlePrevQuarter}><ChevronLeft size={16} /></button>
              <strong className="mx-3 w-20 text-center text-sm text-slate-900 dark:text-zinc-100 font-bold">Q{targetQuarter} {targetYear}</strong>
              <button className="p-1.5 hover:bg-slate-200 dark:hover:bg-zinc-800 rounded-md text-slate-500 transition-colors" onClick={handleNextQuarter}><ChevronRight size={16} /></button>
              <div className="w-px h-5 bg-slate-300 dark:bg-zinc-700 mx-1"></div>
              <button className="ml-1 px-3 py-1 text-xs font-bold bg-white dark:bg-zinc-800 border border-slate-300 dark:border-zinc-700 rounded-md shadow-sm text-slate-600 dark:text-zinc-300 hover:bg-slate-50 dark:hover:bg-zinc-700 transition-colors" onClick={handleCurrentQuarter}>Today</button>
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
              <div className="flex items-center gap-1.5" title="Live Sync Active">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                </span>
              </div>
              <div className="flex -space-x-2">
                <div title="You" className="w-7 h-7 rounded-full bg-blue-500 text-white flex items-center justify-center text-xs font-bold border-2 border-white dark:border-zinc-900 z-10 shadow-sm overflow-hidden">
                  {currentUser?.avatar_url ? (
                    <img src={currentUser.avatar_url} alt="You" className="w-full h-full object-cover" />
                  ) : (
                    currentUser?.name?.charAt(0).toUpperCase() || 'U'
                  )}
                </div>
                {onlineUsers.filter(email => email !== currentUser?.email).map((email, idx) => {
                  const userDetails = boardData.pentesters.find(p => p.email === email);
                  const initial = userDetails?.name?.charAt(0).toUpperCase() || (typeof email === 'string' ? email.charAt(0).toUpperCase() : '?');
                  return (
                    <div key={email || idx} title={userDetails?.name || email} className="w-7 h-7 rounded-full bg-emerald-500 text-white flex items-center justify-center text-xs font-bold border-2 border-white dark:border-zinc-900 shadow-sm overflow-hidden" style={{ zIndex: 9 - idx }}>
                      {userDetails?.avatar_url ? (
                        <img src={userDetails.avatar_url} alt={userDetails?.name} className="w-full h-full object-cover" />
                      ) : (
                        initial
                      )}
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

          <div className="flex-1 min-w-0 overflow-auto bg-slate-50 dark:bg-zinc-950/50 transition-all p-6">
            <table className="w-max min-w-full border-collapse bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-sm overflow-hidden">
              <thead className="bg-slate-50 dark:bg-zinc-900">
                <tr>
                  <th className="p-4 border-b-2 border-r-2 border-slate-300 dark:border-zinc-700 text-left sticky top-0 left-0 z-20 bg-slate-50 dark:bg-zinc-900 shadow-[2px_0_5px_rgba(0,0,0,0.05)] min-w-[200px]">
                    <span className="font-bold text-slate-700 dark:text-zinc-300">Service Lanes</span>
                  </th>
                  {displayWeeks.map(week => {
                    const isCurrent = week === currentRealWeek && targetYear === currentRealYear;
                    const totalWeekCap = boardData.pentesters.reduce((sum, p) => sum + (boardData.capacities?.[p.id]?.[week] || 0), 0);
                    return (
                      <th key={week} className={`p-4 border-b-2 border-slate-200 dark:border-zinc-800 sticky top-0 z-10 min-w-[240px] ${isCurrent ? 'bg-blue-50 dark:bg-blue-900/20 border-l-2 border-r-2 border-l-blue-500 border-r-blue-500' : 'bg-slate-50 dark:bg-zinc-900 border-r border-slate-200 dark:border-zinc-800'}`}>
                        <div className={`text-sm font-bold ${isCurrent ? 'text-blue-700 dark:text-blue-400' : 'text-slate-900 dark:text-zinc-100'}`}>Week {week} {isCurrent && '(Current)'}</div>
                        <div className="text-xs font-normal text-slate-500 dark:text-zinc-400 mt-0.5">{getWeekDateRange(targetYear, week)}</div>
                        <div className={`text-xs font-bold mt-1 ${totalWeekCap >= 1 ? 'text-emerald-600' : 'text-red-500'}`}>Avail: {totalWeekCap.toFixed(1)} cr</div>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {boardData.services.map(service => (
                  <tr key={service.id} style={{ backgroundColor: getTintedBg(service.theme_color) }}>
                    <td className="p-4 font-bold text-slate-900 dark:text-zinc-100 border-b border-r-2 border-slate-300 dark:border-zinc-700 sticky left-0 z-[5] bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md shadow-[2px_0_5px_rgba(0,0,0,0.05)]">
                      <div className="flex items-center gap-2">
                        {service.name}
                      </div>
                    </td>
                    {displayWeeks.map(week => {
                      const cellId = `${service.id}_${week}`;
                      const testsInThisCell = boardData.scheduled.filter(t => t.service_lane_id === service.id && t.startYear === targetYear && week >= (t.startWeek || 0) && week < ((t.startWeek || 0) + t.duration));
                      const isInvalidDropTarget = draggingServiceId && draggingServiceId !== service.id;
                      const isValidDropTarget = draggingServiceId && draggingServiceId === service.id;
                      const isCurrent = week === currentRealWeek && targetYear === currentRealYear;
                      return (
                        <td key={cellId} className={`p-2 border-b border-r border-slate-200 dark:border-zinc-800 align-top min-h-[120px] transition-colors ${
                          isInvalidDropTarget ? 'bg-slate-100/50 dark:bg-zinc-950/80' :
                          isValidDropTarget ? 'bg-blue-50/50 dark:bg-blue-900/10' :
                          isCurrent ? 'bg-black/[0.02] dark:bg-white/[0.02] border-l-2 border-r-2 border-l-blue-500/30 border-r-blue-500/30' : ''
                        }`}>
                          <Droppable droppableId={cellId} isDropDisabled={!!isInvalidDropTarget}>
                            {(provided, snapshot) => (
                              <div ref={provided.innerRef} {...provided.droppableProps} className={`min-h-[120px] w-full h-full rounded-lg p-1 ${snapshot.isDraggingOver ? 'bg-white/50 dark:bg-zinc-800/50 ring-2 ring-blue-400' : ''}`}>
                                {testsInThisCell.map((test, index) => {
                                  const weekAssignments = boardData.assignments.filter(a => a.test_id === test.id && a.week_number === week);
                                  const totalProvided = weekAssignments.reduce((sum, a) => sum + a.allocated_credits, 0);
                                  const isAssignedToMe = weekAssignments.some(a => String(a.user_id) === String(currentUser?.id));
                                  const isSearchActive = searchQuery.trim().length > 0;
                                  const searchLower = searchQuery.toLowerCase();
                                  const testMatchesSearch = !isSearchActive || (test.name || '').toLowerCase().includes(searchLower) || weekAssignments.some(a => (a.user_name || '').toLowerCase().includes(searchLower));

                                  const renderQualityAndTeam = () => {
                                    const percentage = test.credits > 0 ? (totalProvided / test.credits) * 100 : 0;
                                    const capColor = percentage >= 100 ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : percentage >= 70 ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400';
                                    return (
                                      <div className="mt-2 flex flex-col gap-1.5">
                                        <div className="flex items-center gap-2">
                                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${capColor}`}>
                                            Cap: {totalProvided.toFixed(1)} / {test.credits} cr
                                          </span>
                                        </div>
                                        {weekAssignments.length > 0 && (
                                          <div className="flex flex-wrap gap-1">
                                            {weekAssignments.map(a => (
                                              <span key={a.user_id} className={`text-[10px] flex items-center gap-1 px-1.5 py-0.5 rounded border ${String(a.user_id) === String(currentUser?.id) ? 'bg-blue-50 border-blue-200 text-blue-700 font-bold dark:bg-blue-900/20 dark:border-blue-800' : 'bg-slate-50 border-slate-200 text-slate-600 dark:bg-zinc-800 dark:border-zinc-700'}`}>
                                                {(a.user_name || 'Unknown').split(' ')[0]} ({a.allocated_credits.toFixed(1)})
                                                {currentUser?.role === 'admin' && test.status !== 'Completed' && test.status !== 'Stopped' && (
                                                  <X size={10} className="cursor-pointer text-red-500 hover:text-red-700" onClick={() => handleUnassignPentester(test.id, a.user_id)} />
                                                )}
                                              </span>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    );
                                  };

                                  if (test.startWeek === week) {
                                    return (
                                      <Draggable key={test.id} draggableId={test.id} index={index} isDragDisabled={currentUser?.role === 'pentester' || test.status === 'Completed' || test.status === 'Stopped'}>
                                        {(provided) => (
                                            <div ref={provided.innerRef} {...provided.draggableProps} {...provided.dragHandleProps}
                                              className={`p-3 bg-white dark:bg-zinc-800 rounded-lg shadow-sm border mb-2 transition-all group ${test.status === 'Stopped' ? 'border-red-300 bg-red-50/50 dark:border-red-900/50 dark:bg-red-900/10' : isAssignedToMe ? 'border-blue-300 shadow-[0_0_10px_rgba(59,130,246,0.1)]' : 'border-slate-200 dark:border-zinc-700'} ${testMatchesSearch ? 'opacity-100' : 'opacity-20 grayscale'}`}
                                              style={{ ...provided.draggableProps.style, borderLeftWidth: '4px', borderLeftColor: test.status === 'Stopped' ? '#ef4444' : test.status === 'Completed' ? '#10b981' : service.theme_color }}
                                            >
                                              <div className="flex justify-between items-start mb-1">
                                                <div className="font-bold text-xs text-slate-900 dark:text-zinc-100 leading-tight">
                                                  {test.name}
                                                </div>
                                                {test.status === 'Completed' && <span className="ml-2 text-[9px] font-black bg-emerald-100 text-emerald-700 px-1 rounded uppercase tracking-wide">Done</span>}
                                                {test.status === 'Stopped' && <span className="ml-2 text-[9px] font-black bg-red-100 text-red-700 px-1 rounded uppercase tracking-wide">Stop</span>}
                                              </div>

                                              {renderQualityAndTeam()}

                                              {currentUser?.role === 'admin' && (
                                                <div className="mt-3 pt-2 border-t border-slate-100 dark:border-zinc-700/50 flex flex-wrap gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                  {test.status === 'Completed' ? (
                                                    <>
                                                      <button className="px-2 py-1 text-[10px] font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded transition-colors" onClick={() => handleRevertComplete(test.id)}>Undo Done</button>
                                                      <button className="px-2 py-1 text-[10px] font-bold bg-blue-50 hover:bg-blue-100 text-blue-600 rounded transition-colors flex items-center gap-1" onClick={() => setHistoryTest(test)}><History size={10}/> Hist</button>
                                                    </>
                                                  ) : test.status === 'Stopped' ? (
                                                    <>
                                                      <button className="px-2 py-1 text-[10px] font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded transition-colors" onClick={() => handleRevertUnable(test.id)}>Undo Stop</button>
                                                      <button className="px-2 py-1 text-[10px] font-bold bg-blue-50 hover:bg-blue-100 text-blue-600 rounded transition-colors flex items-center gap-1" onClick={() => setHistoryTest(test)}><History size={10}/> Hist</button>
                                                    </>
                                                  ) : (
                                                    <>
                                                      <button className="px-2 py-1 text-[10px] font-bold bg-blue-50 hover:bg-blue-100 text-blue-600 rounded transition-colors flex items-center gap-1" onClick={() => setAssignModalTest(test)}><Users size={10}/> Staff</button>
                                                      <button className="px-2 py-1 text-[10px] font-bold bg-emerald-50 hover:bg-emerald-100 text-emerald-600 rounded transition-colors flex items-center gap-1" onClick={() => handleCompleteTest(test.id)}><CheckCircle size={10}/> Done</button>
                                                      <button className="px-2 py-1 text-[10px] font-bold bg-red-50 hover:bg-red-100 text-red-600 rounded transition-colors flex items-center gap-1" onClick={() => handleMarkUnable(test.id)}><XCircle size={10}/> Stop</button>
                                                      <button className="px-2 py-1 text-[10px] font-bold bg-slate-100 hover:bg-slate-200 text-slate-600 rounded transition-colors" onClick={() => handleUnscheduleTest(test.id)}>Unsch</button>
                                                      <button className="px-2 py-1 text-[10px] font-bold bg-blue-50 hover:bg-blue-100 text-blue-600 rounded transition-colors flex items-center gap-1" onClick={() => setHistoryTest(test)}><History size={10}/> Hist</button>
                                                      <button className="px-2 py-1 text-[10px] font-bold bg-slate-100 hover:bg-slate-200 text-slate-600 rounded transition-colors flex items-center gap-1" onClick={() => openEditModal(test)}><Edit2 size={10}/> Edit</button>
                                                    </>
                                                  )}
                                                </div>
                                              )}
                                            </div>
                                        )}
                                      </Draggable>
                                    );
                                  } else {
                                    return (
                                      <div key={`${test.id}-ghost`} className={`p-2.5 bg-white/60 dark:bg-zinc-800/60 rounded-lg shadow-sm border border-dashed mb-2 ${test.status === 'Stopped' ? 'border-red-300' : 'border-slate-300 dark:border-zinc-600'} ${testMatchesSearch ? 'opacity-70' : 'opacity-20 grayscale'}`}
                                           style={{ borderLeftWidth: '4px', borderLeftStyle: 'solid', borderLeftColor: test.status === 'Stopped' ? '#ef4444' : test.status === 'Completed' ? '#10b981' : service.theme_color }}>
                                        <div className="font-bold text-[11px] text-slate-500 dark:text-zinc-400 flex items-center gap-1">
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
            <div className="w-[320px] shrink-0 bg-white dark:bg-zinc-900 border-l border-slate-200 dark:border-zinc-800 flex flex-col z-15 shadow-[-4px_0_15px_rgba(0,0,0,0.03)] animate-in slide-in-from-right-8">
              <div className="p-4 bg-slate-50 dark:bg-zinc-950/50 border-b border-slate-200 dark:border-zinc-800 flex flex-col gap-3 shrink-0">
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
                                  className={`p-3 border border-slate-200 dark:border-zinc-700 rounded-xl mb-3 cursor-grab flex justify-between items-center shadow-sm hover:shadow-md transition-all ${testMatchesSearch ? 'opacity-100' : 'opacity-30 grayscale'}`}
                                  style={{
                                    ...provided.draggableProps.style,
                                    borderLeftWidth: '4px',
                                    borderLeftColor: service?.theme_color || '#cbd5e1',
                                    backgroundColor: getTintedBg(service?.theme_color)
                                  }}
                                >
                                  <div className="overflow-hidden flex-1 pr-3">
                                      <div className="font-bold text-xs text-slate-900 dark:text-zinc-100 truncate mb-1" title={test.name}>{test.name}</div>
                                      <div className="text-[10px] text-slate-500 dark:text-zinc-400 font-medium">
                                        <span className="font-bold text-slate-700 dark:text-zinc-300">{service?.name || 'Unknown'}</span> • {test.credits} cr • {test.duration} wk
                                      </div>
                                  </div>

                                  {currentUser?.role === 'admin' && (
                                     <div className="flex flex-col gap-1.5 shrink-0">
                                      <button title="History" className="p-1.5 bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 rounded hover:bg-blue-100 dark:hover:bg-blue-500/20 transition-colors" onClick={() => setHistoryTest(test)}><History size={12} /></button>
                                      <button title="Edit Settings" className="p-1.5 bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 rounded hover:bg-slate-200 dark:hover:bg-zinc-700 transition-colors" onClick={() => openEditModal(test)}><Edit2 size={12} /></button>
                                      <button title="Delete Permanently" className="p-1.5 bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 rounded hover:bg-red-100 dark:hover:bg-red-500/20 transition-colors" onClick={() => handleDeleteTest(test.id)}><Trash2 size={12} /></button>
                                    </div>
                                  )}
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
    </DragDropContext>
  );
}