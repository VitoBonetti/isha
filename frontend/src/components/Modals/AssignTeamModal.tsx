import React from 'react';
import { X, Users } from 'lucide-react';
import type { BoardData, Test } from '../../types/board';

interface AssignTeamModalProps {
  assignModalTest: Test | null;
  setAssignModalTest: (test: Test | null) => void;
  boardData: BoardData | null;
  handleAssignTeam: (userId: string) => void;
  targetYear: number;
}

export default function AssignTeamModal({
  assignModalTest,
  setAssignModalTest,
  boardData,
  handleAssignTeam,
  targetYear
}: AssignTeamModalProps) {
  if (!assignModalTest || !boardData) return null;

  const safeStartYear = assignModalTest.startYear || targetYear;
  const safeStartWeek = assignModalTest.startWeek || 1;
  const testStartVal = safeStartYear * 100 + safeStartWeek;

  const activePentesters = boardData.pentesters.filter(p => {
    if (p.role === 'read_only') return false;
    const pStart = (p.start_year || 2024) * 100 + (p.start_week || 1);
    const pEnd = p.end_year ? (p.end_year * 100 + (p.end_week || 52)) : 999999;
    return pStart <= testStartVal && pEnd >= testStartVal;
  });

  return (
    <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-[1000] flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 w-full max-w-lg shadow-2xl animate-in zoom-in-95 max-h-[85vh] flex flex-col">

        <div className="flex justify-between items-center mb-6 border-b border-slate-100 dark:border-zinc-800 pb-4 shrink-0">
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
              <Users size={20} className="text-blue-500" /> Assign Pentester
            </h2>
            <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1 truncate max-w-[350px]">
              {assignModalTest.name}
            </p>
          </div>
          <button onClick={() => setAssignModalTest(null)} className="text-slate-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto pr-2 -mr-2">
          <table className="w-full text-left text-sm">
            <thead className="bg-white dark:bg-zinc-900 sticky top-0 z-10 border-b-2 border-slate-100 dark:border-zinc-800">
              <tr>
                <th className="py-3 px-2 font-bold text-slate-600 dark:text-zinc-400">Team Member</th>
                <th className="py-3 px-2 font-bold text-slate-600 dark:text-zinc-400 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-zinc-800/50">
              {activePentesters.map(p => {
                const availCapacity = boardData.capacities[p.id]?.[safeStartWeek] || 0;
                const isAvail = availCapacity > 0;

                return (
                  <tr key={p.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/30 transition-colors">
                    <td className="py-3 px-2">
                      <div className="font-bold text-slate-900 dark:text-zinc-100">{p.name}</div>
                      <div className={`text-xs mt-1 font-medium ${isAvail ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                        Avail Wk {safeStartWeek}: {availCapacity.toFixed(1)} cr
                      </div>
                    </td>
                    <td className="py-3 px-2 text-right align-middle">
                      {isAvail ? (
                        <button
                          onClick={() => handleAssignTeam(p.id)}
                          className="px-4 py-1.5 bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-500/30 rounded-lg font-bold hover:bg-blue-100 dark:hover:bg-blue-500/20 transition-colors text-xs"
                        >
                          Add to Test
                        </button>
                      ) : (
                        <span className="text-xs text-slate-400 dark:text-zinc-500 italic font-medium px-4">
                          Unavailable
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="mt-6 pt-4 border-t border-slate-100 dark:border-zinc-800 text-right shrink-0">
          <button
            onClick={() => setAssignModalTest(null)}
            className="px-5 py-2.5 text-sm font-medium bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}