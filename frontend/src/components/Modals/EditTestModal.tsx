import React, { useState, useEffect } from 'react';
import { X, Save, Edit2 } from 'lucide-react';
import type { Test, BoardData } from '../../types/board';

interface EditTestModalProps {
  isOpen: boolean;
  test: Test | null;
  boardData: BoardData | null;
  onClose: () => void;
  onSubmit: (testId: string, updatedData: any) => Promise<void>;
}

export default function EditTestModal({ isOpen, test, boardData, onClose, onSubmit }: EditTestModalProps) {
  const [name, setName] = useState('');
  const [serviceLaneId, setServiceLaneId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [credits, setCredits] = useState(2.0);
  const [duration, setDuration] = useState(1);
  const [isTentative, setIsTentative] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (test) {
      setName(test.name || '');
      setServiceLaneId(test.service_lane_id || '');
      setCategoryId(test.category_id || '');
      setCredits(test.credits || 2.0);
      setDuration(test.duration || 1);
      setIsTentative(test.is_tentative || false);
    }
  }, [test]);

  if (!isOpen || !test || !boardData) return null;

  // Filter categories to only show ones belonging to the selected service lane
  const availableCategories = boardData.categories.filter(c => c.service_lane_id === serviceLaneId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    await onSubmit(test.id, {
      name,
      service_lane_id: serviceLaneId,
      category_id: categoryId === '' ? null : categoryId,
      credits_per_week: credits,
      duration_weeks: duration,
      status: test.status,
      is_tentative: isTentative
    });

    setIsSubmitting(false);
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-[1000] flex items-start sm:items-center justify-center p-4 animate-in fade-in overflow-y-auto">
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-4 sm:p-6 w-[95%] sm:w-full max-w-md shadow-2xl animate-in zoom-in-95 flex flex-col my-4 sm:my-8">

        <div className="flex justify-between items-center mb-4 sm:mb-6 border-b border-slate-100 dark:border-zinc-800 pb-4">
          <h2 className="text-lg font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Edit2 size={20} className="text-blue-500" /> Edit Test Settings
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors p-1">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">Test Name</label>
            <input type="text" required value={name} onChange={e => setName(e.target.value)} className="w-full px-3 py-2.5 sm:py-2 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg text-sm text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"/>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">Service Lane</label>
              <select required value={serviceLaneId} onChange={e => { setServiceLaneId(e.target.value); setCategoryId(''); }} className="w-full px-3 py-2.5 sm:py-2 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg text-sm text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow">
                <option value="" disabled>Select Lane...</option>
                {boardData.services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">Category (Optional)</label>
              <select value={categoryId} onChange={e => setCategoryId(e.target.value)} disabled={!serviceLaneId} className="w-full px-3 py-2.5 sm:py-2 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg text-sm text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow disabled:opacity-50">
                <option value="">No Category</option>
                {availableCategories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] sm:text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">Credits / Week</label>
              <input type="number" step="0.5" min="0.5" required value={credits} onChange={e => setCredits(parseFloat(e.target.value))} className="w-full px-3 py-2.5 sm:py-2 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg text-sm text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"/>
            </div>
            <div>
              <label className="block text-[11px] sm:text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">Duration (Weeks)</label>
              <input type="number" step="1" min="1" required value={duration} onChange={e => setDuration(parseInt(e.target.value))} className="w-full px-3 py-2.5 sm:py-2 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg text-sm text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"/>
            </div>
          </div>

          <div className="mt-2">
            <label className="flex items-center gap-3 cursor-pointer w-fit">
              <div className="relative flex items-center">
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={isTentative}
                  onChange={e => setIsTentative(e.target.checked)}
                />
                <div className={`block w-10 h-6 rounded-full transition-colors duration-300 ${isTentative ? 'bg-amber-500' : 'bg-slate-300 dark:bg-zinc-700'}`}></div>
                <div className={`absolute left-1 bg-white w-4 h-4 rounded-full transition-transform duration-300 shadow-sm ${isTentative ? 'transform translate-x-4' : ''}`}></div>
              </div>
              <span className="text-sm font-bold text-slate-700 dark:text-zinc-300">
                Mark as Tentative (TBC)
              </span>
            </label>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-100 dark:border-zinc-800 flex flex-col sm:flex-row justify-end gap-3">
            <button type="submit" disabled={isSubmitting} className="w-full sm:w-auto px-4 py-2.5 sm:py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors flex justify-center items-center gap-2 disabled:opacity-50 order-1 sm:order-2"><Save size={16} />{isSubmitting ? 'Saving...' : 'Save Changes'}</button>
            <button type="button" onClick={onClose} className="w-full sm:w-auto px-4 py-2.5 sm:py-2 text-sm font-medium bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors order-2 sm:order-1 flex justify-center items-center">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  );
}