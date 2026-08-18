import { useState, useEffect } from 'react';
import axios from 'axios';
import { X, Plus, Trash2, CheckSquare } from 'lucide-react';
import toast from 'react-hot-toast';

interface Requirement {
  id: string;
  description: string;
  is_completed: boolean;
}

interface RequirementsModalProps {
  isOpen: boolean;
  testId: string;
  onClose: () => void;
}

export default function RequirementsModal({ isOpen, testId, onClose }: RequirementsModalProps) {
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [newReq, setNewReq] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isOpen && testId) {
      setLoading(true);
      axios.get(`/api/tests/${testId}/requirements`)
        .then(res => setRequirements(res.data))
        .catch(() => toast.error("Failed to load requirements"))
        .finally(() => setLoading(false));
    } else {
      setNewReq('');
    }
  }, [isOpen, testId]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newReq.trim()) return;

    try {
      const res = await axios.post(`/api/tests/${testId}/requirements`, { description: newReq });
      setRequirements([...requirements, res.data]);
      setNewReq('');
    } catch (error) {
      toast.error("Failed to add requirement");
    }
  };

  const handleToggle = async (reqId: string) => {
    // Optimistic UI update
    setRequirements(prev => prev.map(r => r.id === reqId ? { ...r, is_completed: !r.is_completed } : r));
    try {
      await axios.put(`/api/tests/requirements/${reqId}/toggle`);
    } catch (error) {
      toast.error("Failed to update status");
      // Revert on failure
      setRequirements(prev => prev.map(r => r.id === reqId ? { ...r, is_completed: !r.is_completed } : r));
    }
  };

  const handleDelete = async (reqId: string) => {
    try {
      await axios.delete(`/api/tests/requirements/${reqId}`);
      setRequirements(prev => prev.filter(r => r.id !== reqId));
    } catch (error) {
      toast.error("Failed to delete requirement");
    }
  };

  if (!isOpen) return null;

  const completedCount = requirements.filter(r => r.is_completed).length;
  const totalCount = requirements.length;
  const progress = totalCount === 0 ? 0 : Math.round((completedCount / totalCount) * 100);

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in">
      <div className="bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden flex flex-col max-h-[85vh]">

        {/* Header */}
        <div className="p-5 border-b border-slate-100 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-900/50 flex justify-between items-center shrink-0">
          <div className="flex items-center gap-3">
            <div className="bg-teal-100 dark:bg-teal-900/30 text-teal-600 dark:text-teal-400 p-2 rounded-lg">
              <CheckSquare size={20} />
            </div>
            <div>
              <h2 className="font-black text-lg text-slate-900 dark:text-zinc-100 leading-tight">Test Requirements</h2>
              <p className="text-xs font-medium text-slate-500">Track milestones and prerequisites</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-500 rounded-full transition-colors">
            <X size={16} />
          </button>
        </div>

        {/* Progress Bar */}
        <div className="px-5 py-3 bg-white dark:bg-zinc-950 border-b border-slate-100 dark:border-zinc-800 shrink-0">
          <div className="flex justify-between text-xs font-bold mb-1.5">
            <span className="text-slate-500">Completion</span>
            <span className={progress === 100 ? "text-emerald-500" : "text-blue-500"}>{progress}%</span>
          </div>
          <div className="w-full bg-slate-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
            <div className={`h-full transition-all duration-500 ${progress === 100 ? "bg-emerald-500" : "bg-blue-500"}`} style={{ width: `${progress}%` }} />
          </div>
        </div>

        {/* List Content */}
        <div className="p-5 overflow-y-auto flex-1 bg-slate-50/30 dark:bg-zinc-950/30">
          {loading ? (
            <div className="text-center py-8 text-slate-400 font-bold text-sm animate-pulse">Loading requirements...</div>
          ) : requirements.length === 0 ? (
            <div className="text-center py-10 text-slate-400 text-sm">
              <CheckSquare size={32} className="mx-auto mb-3 opacity-20" />
              No requirements added yet.<br/>Add your first milestone below.
            </div>
          ) : (
            <div className="space-y-2">
              {requirements.map((req) => (
                <div key={req.id} className={`group flex items-start gap-3 p-3 rounded-xl border transition-all ${req.is_completed ? 'bg-slate-50/50 dark:bg-zinc-900/30 border-transparent opacity-60' : 'bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-800 shadow-sm'}`}>
                  <button
                    onClick={() => handleToggle(req.id)}
                    className={`shrink-0 mt-0.5 flex items-center justify-center w-5 h-5 rounded border transition-colors ${req.is_completed ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-slate-300 dark:border-zinc-600 bg-slate-50 dark:bg-zinc-800'}`}
                  >
                    {req.is_completed && <CheckSquare size={12} strokeWidth={4} />}
                  </button>
                  <span className={`flex-1 text-sm font-medium pt-0.5 ${req.is_completed ? 'line-through text-slate-500 dark:text-zinc-500' : 'text-slate-700 dark:text-zinc-300'}`}>
                    {req.description}
                  </span>
                  <button
                    onClick={() => handleDelete(req.id)}
                    className="shrink-0 p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Input Footer */}
        <div className="p-4 border-t border-slate-100 dark:border-zinc-800 bg-white dark:bg-zinc-950 shrink-0">
          <form onSubmit={handleAdd} className="relative">
            <input
              type="text"
              placeholder="Add a new requirement..."
              value={newReq}
              onChange={(e) => setNewReq(e.target.value)}
              className="w-full pl-4 pr-12 py-2.5 bg-slate-100 dark:bg-zinc-900 border border-transparent focus:border-blue-500 dark:focus:border-blue-500 rounded-xl text-sm outline-none text-slate-900 dark:text-zinc-100 transition-colors placeholder:text-slate-400"
            />
            <button
              type="submit"
              disabled={!newReq.trim()}
              className="absolute right-1.5 top-1.5 bottom-1.5 aspect-square flex items-center justify-center bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 disabled:dark:bg-zinc-700 text-white rounded-lg transition-colors"
            >
              <Plus size={16} />
            </button>
          </form>
        </div>

      </div>
    </div>
  );
}