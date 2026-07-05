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
  const [credits, setCredits] = useState(2.0);
  const [duration, setDuration] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // When the modal opens, populate the form with the test's current data
  useEffect(() => {
    if (test) {
      setName(test.name || '');
      setServiceLaneId(test.service_lane_id || '');
      setCredits(test.credits || 2.0);
      setDuration(test.duration || 1);
    }
  }, [test]);

  if (!isOpen || !test || !boardData) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    // We send back exactly what the backend PUT endpoint expects
    await onSubmit(test.id, {
      name,
      service_lane_id: serviceLaneId,
      credits_per_week: credits,
      duration_weeks: duration,
      status: test.status // Pass along the current status so it doesn't get wiped
    });

    setIsSubmitting(false);
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-[1000] flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 w-full max-w-md shadow-2xl animate-in zoom-in-95 flex flex-col">

        <div className="flex justify-between items-center mb-6 border-b border-slate-100 dark:border-zinc-800 pb-4">
          <h2 className="text-lg font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Edit2 size={20} className="text-blue-500" /> Edit Test Settings
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 dark:hover:text-zinc-100 transition-colors">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Name Field */}
          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">Test Name</label>
            <input
              type="text"
              required
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg text-sm text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"
            />
          </div>

          {/* Service Lane Field */}
          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">Service Lane</label>
            <select
              required
              value={serviceLaneId}
              onChange={e => setServiceLaneId(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg text-sm text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"
            >
              <option value="" disabled>Select a Lane...</option>
              {boardData.services.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          {/* Capacity Metrics (Side by side) */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">Credits / Week</label>
              <input
                type="number"
                step="0.5"
                min="0.5"
                required
                value={credits}
                onChange={e => setCredits(parseFloat(e.target.value))}
                className="w-full px-3 py-2 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg text-sm text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-zinc-300 mb-1.5">Duration (Weeks)</label>
              <input
                type="number"
                step="1"
                min="1"
                required
                value={duration}
                onChange={e => setDuration(parseInt(e.target.value))}
                className="w-full px-3 py-2 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg text-sm text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"
              />
            </div>
          </div>

          {/* Form Actions */}
          <div className="mt-4 pt-4 border-t border-slate-100 dark:border-zinc-800 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              <Save size={16} />
              {isSubmitting ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}