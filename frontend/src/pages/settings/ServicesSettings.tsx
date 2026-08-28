import React, { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import ConfirmModal from '../../components/Modals/ConfirmModal';
import TemplateEditorModal from '../../components/Modals/TemplateEditorModal';
import {
  Activity, Plus, Edit2, Trash2, X, Mail, CheckCircle
} from 'lucide-react';

// Reusable Toggle Component
const Toggle = ({ checked, onChange, label, disabled = false }: { checked: boolean, onChange: (c: boolean) => void, label: string, disabled?: boolean }) => (
  <label className={`flex items-center gap-3 select-none ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>
    <div className="relative flex items-center shrink-0">
      <input type="checkbox" className="sr-only" checked={checked} disabled={disabled} onChange={e => onChange(e.target.checked)} />
      <div className={`block w-10 h-6 rounded-full transition-colors duration-300 ${checked ? 'bg-blue-500' : 'bg-slate-300 dark:bg-zinc-700'}`}></div>
      <div className={`absolute left-1 bg-white w-4 h-4 rounded-full transition-transform duration-300 shadow-sm ${checked ? 'transform translate-x-4' : ''}`}></div>
    </div>
    <span className="text-sm font-bold text-slate-700 dark:text-zinc-300 leading-tight">{label}</span>
  </label>
);

const PREDEFINED_COLORS = ['#ef4444', '#f97316', '#f59e0b', '#84cc16', '#10b981', '#14b8a6', '#06b6d4', '#3b82f6', '#6366f1', '#8b5cf6', '#a855f7', '#ec4899', '#f43f5e', '#64748b', '#000000', '#ffffff', '#cccccc', '#eeeeee'];

const defaultServiceForm = {
  name: '', theme_color: '#3b82f6', default_credits: 2.0, default_duration_weeks: 1,
  max_concurrent_per_week: 5, target_goal: 0, display_order: 99, is_active: true,
  auto_provision_workspace: false, requires_mitre: false
};

export default function ServicesSettings() {
  const [localServices, setLocalServices] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const currentYear = new Date().getFullYear();

  // Panel & Edit State
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [editServiceId, setEditServiceId] = useState<string | null>(null);
  const [serviceForm, setServiceForm] = useState(defaultServiceForm);

  // Modals
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; id: string; name: string } | null>(null);

  const [templateModal, setTemplateModal] = useState<{
    isOpen: boolean; serviceId: string; serviceName: string; type: 'intro' | 'final' | null; initialTemplate: string;
  }>({ isOpen: false, serviceId: '', serviceName: '', type: null, initialTemplate: '' });

  // Goal Ledger State
  const [goalLedgerService, setGoalLedgerService] = useState<{id: string, name: string} | null>(null);
  const [ledgerGoals, setLedgerGoals] = useState<{year: number, target_goal: number}[]>([]);
  const [newLedgerYear, setNewLedgerYear] = useState(currentYear);
  const [newLedgerGoal, setNewLedgerGoal] = useState(0);

  const fetchServices = async () => {
    setIsLoading(true);
    try {
      const res = await axios.get(`/api/services/?year=${currentYear}`);
      setLocalServices(res.data);
    } catch (err) {
      toast.error("Failed to load services");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchServices();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openCreatePanel = () => {
    setEditServiceId(null);
    setServiceForm(defaultServiceForm);
    setIsPanelOpen(true);
  };

  const openEditPanel = (item: any) => {
    setEditServiceId(item.id);
    setServiceForm({
      name: item.name, theme_color: item.theme_color, default_credits: item.default_credits,
      default_duration_weeks: item.default_duration_weeks, max_concurrent_per_week: item.max_concurrent_per_week || 5,
      target_goal: item.target_goal || 0, display_order: item.display_order || 99, is_active: item.is_active,
      auto_provision_workspace: item.auto_provision_workspace || false, requires_mitre: item.requires_mitre || false
    });
    setIsPanelOpen(true);
  };

  const closePanel = () => {
    setIsPanelOpen(false);
    setEditServiceId(null);
    setServiceForm(defaultServiceForm);
  };

  const submitService = async (e: React.FormEvent) => {
    e.preventDefault();
    const toastId = toast.loading("Saving service...");
    try {
      if (editServiceId) {
        await axios.put(`/api/services/${editServiceId}?year=${currentYear}`, serviceForm);
        toast.success("Service lane updated", { id: toastId });
      } else {
        await axios.post(`/api/services/?year=${currentYear}`, serviceForm);
        toast.success("Service lane created", { id: toastId });
      }
      closePanel();
      fetchServices();
    } catch (err) {
      toast.error("Failed to save service lane", { id: toastId });
    }
  };

  const executeDelete = async () => {
    if (!deleteModal) return;
    try {
      await axios.delete(`/api/services/${deleteModal.id}`);
      toast.success("Service deleted");
      setDeleteModal(null);
      fetchServices();
    } catch (err) {
      toast.error("Failed to delete service. It may be in use.");
    }
  };

  const inputClasses = "w-full mt-1.5 p-2.5 border border-slate-200 dark:border-zinc-800 rounded-xl bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none text-sm transition-colors";

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Loading service lanes...</div>;
  }

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">

      <ConfirmModal
        isOpen={!!deleteModal}
        title="Confirm Deletion"
        message={`Are you sure you want to delete ${deleteModal?.name}? This action cannot be undone.`}
        onConfirm={executeDelete}
        onCancel={() => setDeleteModal(null)}
      />

      {/* SERVICE LANE GOAL LEDGER MODAL */}
      {goalLedgerService && (
        <div className="fixed inset-0 bg-slate-900/50 dark:bg-zinc-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2 mb-1">
              <Activity size={20} className="text-blue-500" /> Goal Ledger
            </h3>
            <p className="text-sm text-slate-500 mb-4">Manage yearly targets for <strong>{goalLedgerService.name}</strong>.</p>

            <div className="space-y-2 mb-6 max-h-60 overflow-y-auto pr-2">
              {ledgerGoals.length === 0 ? (
                <div className="text-sm text-slate-500 italic">No goals set yet.</div>
              ) : (
                ledgerGoals.map(g => (
                  <div key={g.year} className="flex justify-between items-center bg-slate-50 dark:bg-zinc-800/50 p-3 rounded-xl border border-slate-100 dark:border-zinc-800">
                    <span className="font-bold text-slate-700 dark:text-zinc-300">Year {g.year}</span>
                    <span className="font-black text-blue-600 dark:text-blue-400">{g.target_goal} <span className="text-xs text-slate-500 font-medium">target</span></span>
                  </div>
                ))
              )}
            </div>

            <div className="flex gap-3 mb-6 border-t border-slate-100 dark:border-zinc-800 pt-4">
              <div className="flex-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Year</label>
                <input type="number" className={inputClasses} value={newLedgerYear} onChange={e => setNewLedgerYear(parseInt(e.target.value))} />
              </div>
              <div className="flex-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Target Goal</label>
                <input type="number" className={inputClasses} value={newLedgerGoal} onChange={e => setNewLedgerGoal(parseInt(e.target.value))} />
              </div>
              <button
                className="mt-6 px-4 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold transition-colors text-sm shadow-sm"
                onClick={async () => {
                  await axios.post(`/api/services/${goalLedgerService.id}/goals?year=${newLedgerYear}&target_goal=${newLedgerGoal}`);
                  const res = await axios.get(`/api/services/${goalLedgerService.id}/goals`);
                  setLedgerGoals(res.data);
                  toast.success("Goal saved!");
                }}
              >Save</button>
            </div>

            <div className="flex justify-end">
              <button onClick={() => setGoalLedgerService(null)} className="px-5 py-2.5 text-sm font-bold bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 rounded-xl transition-colors">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* HEADER BAR */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Activity size={22} className="text-blue-500" /> Dynamic Service Lanes
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-0.5">
            Define distinct testing lanes, default credits, and email automations.
          </p>
        </div>
        <button
          onClick={openCreatePanel}
          className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 shadow-sm transition-colors cursor-pointer"
        >
          <Plus size={16} /> Add Service
        </button>
      </div>

      {/* CARDS CONTAINER */}
      <div className="flex flex-col gap-4">
        {localServices?.map((item: any) => (
          <div key={item.id} className={`border p-5 rounded-2xl flex flex-col xl:flex-row xl:items-center transition-colors bg-white dark:bg-zinc-900 shadow-sm hover:shadow-md gap-4 ${item.is_active ? 'border-slate-200 dark:border-zinc-800 hover:border-blue-500 dark:hover:border-blue-500/50' : 'border-slate-200 dark:border-zinc-800 opacity-60 grayscale'}`}>

            {/* LEFT SECTION: Basic Info */}
            <div className="flex-1 min-w-[250px]">
              <div className="font-bold text-lg text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                {item.theme_color && <div className="w-4 h-4 rounded-full shadow-sm shrink-0" style={{backgroundColor: item.theme_color}}></div>}
                <span className="truncate">{item.name}</span>
                <span className={`ml-2 px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider shadow-sm border ${item.is_active ? 'bg-emerald-100 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20 text-emerald-800 dark:text-emerald-400' : 'bg-slate-100 dark:bg-zinc-800 border-slate-200 dark:border-zinc-700 text-slate-500 dark:text-zinc-400'}`}>
                  {item.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              <div className="mt-2 text-sm text-slate-500 dark:text-zinc-400 font-medium flex flex-wrap items-center gap-4">
                <span>Credits: <strong className="text-slate-900 dark:text-zinc-200">{item.default_credits}cr</strong></span>
                <span>Duration: <strong className="text-slate-900 dark:text-zinc-200">{item.default_duration_weeks}w</strong></span>
                <span>Max: <strong className="text-slate-900 dark:text-zinc-200">{item.max_concurrent_per_week || '∞'}</strong></span>
                <button
                  onClick={async () => {
                    setGoalLedgerService({id: item.id, name: item.name});
                    const res = await axios.get(`/api/services/${item.id}/goals`);
                    setLedgerGoals(res.data);
                  }}
                  className="text-blue-600 dark:text-blue-400 font-bold hover:underline px-2 py-1 rounded hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
                >
                  Manage Yearly Goals
                </button>
              </div>
            </div>

            {/* MIDDLE SECTION: Email Templates */}
            <div className="flex-1 flex flex-col gap-2 min-w-[200px] xl:border-l border-slate-200 dark:border-zinc-800 xl:pl-4 pt-3 xl:pt-0 border-t xl:border-t-0">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Email Automations</span>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => setTemplateModal({ isOpen: true, serviceId: item.id, serviceName: item.name, type: 'intro', initialTemplate: item.intro_email_template })}
                  className={`text-xs font-bold flex items-center gap-1.5 px-3 py-2 rounded-xl border transition-colors ${item.intro_email_template ? 'bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-700 text-slate-700 dark:text-zinc-300 hover:border-blue-500' : 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-900/50 text-blue-600 dark:text-blue-400 hover:bg-blue-100'}`}
                >
                  <Mail size={14} /> {item.intro_email_template ? 'Edit Intro Email' : 'Add Intro Email'}
                </button>
                <button
                  onClick={() => setTemplateModal({ isOpen: true, serviceId: item.id, serviceName: item.name, type: 'final', initialTemplate: item.final_email_template })}
                  className={`text-xs font-bold flex items-center gap-1.5 px-3 py-2 rounded-xl border transition-colors ${item.final_email_template ? 'bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-700 text-slate-700 dark:text-zinc-300 hover:border-emerald-500' : 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-900/50 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100'}`}
                >
                  <CheckCircle size={14} /> {item.final_email_template ? 'Edit Final Email' : 'Add Final Email'}
                </button>
              </div>
            </div>

            {/* RIGHT SECTION: Actions */}
            <div className="flex xl:flex-col justify-end w-full xl:w-auto gap-2 shrink-0 border-t border-slate-100 dark:border-zinc-800/50 xl:border-t-0 pt-3 xl:pt-0 mt-1 xl:mt-0">
              <button
                onClick={() => openEditPanel(item)}
                className="flex-1 xl:flex-none flex justify-center items-center text-slate-500 bg-slate-100 dark:bg-zinc-800 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 p-2.5 rounded-xl transition-colors cursor-pointer"
              >
                <Edit2 size={16} />
              </button>
              <button
                onClick={() => setDeleteModal({ isOpen: true, id: item.id, name: item.name })}
                className="flex-1 xl:flex-none flex justify-center items-center text-red-500 bg-red-50 dark:bg-red-900/20 hover:text-red-600 hover:bg-red-100 dark:hover:bg-red-900/40 p-2.5 rounded-xl transition-colors cursor-pointer"
              >
                <Trash2 size={16} />
              </button>
            </div>

          </div>
        ))}
        {(!localServices || localServices.length === 0) && (
          <div className="p-12 text-center text-sm text-slate-500 bg-white dark:bg-zinc-900 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm">
            No services found.
          </div>
        )}
      </div>

      {/* RIGHT SLIDE-OVER FORM PANEL */}
      {isPanelOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-slate-900/40 dark:bg-zinc-950/70 backdrop-blur-sm transition-opacity animate-in fade-in" onClick={closePanel} />
          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-md bg-white dark:bg-zinc-900 border-l border-slate-200 dark:border-zinc-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">

              {/* PANEL HEADER */}
              <div className="p-6 border-b border-slate-100 dark:border-zinc-800 flex justify-between items-center bg-slate-50/50 dark:bg-zinc-950/50">
                <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100">
                  {editServiceId ? 'Edit Service Lane' : 'Add Service Lane'}
                </h3>
                <button onClick={closePanel} className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer">
                  <X size={18} />
                </button>
              </div>

              {/* PANEL BODY */}
              <form onSubmit={submitService} className="flex-1 p-6 overflow-y-auto space-y-6 pb-32">
                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">Service Name</label>
                  <input type="text" className={inputClasses} value={serviceForm.name} onChange={e => setServiceForm({ ...serviceForm, name: e.target.value })} required />
                </div>

                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider mb-2 block">Theme Color</label>
                  <div className="p-3 bg-slate-50 dark:bg-zinc-950/50 border border-slate-200 dark:border-zinc-800 rounded-xl space-y-3">
                    <div className="flex flex-wrap gap-2">
                      {PREDEFINED_COLORS.map(color => (
                        <button
                          key={color} type="button" title={color}
                          onClick={() => setServiceForm({ ...serviceForm, theme_color: color })}
                          className={`w-6 h-6 rounded-full border-2 transition-all hover:scale-110 cursor-pointer ${serviceForm.theme_color.toLowerCase() === color ? 'border-slate-900 dark:border-white scale-110 shadow-md' : 'border-transparent shadow-sm'}`}
                          style={{ backgroundColor: color }}
                        />
                      ))}
                    </div>
                    <div className="flex items-center gap-3">
                      <input type="text" className={`${inputClasses} !mt-0 font-mono uppercase w-full`} value={serviceForm.theme_color} onChange={e => setServiceForm({...serviceForm, theme_color: e.target.value})} placeholder="#3B82F6" maxLength={7} pattern="^#[0-9A-Fa-f]{6}$" required />
                      <div className="w-10 h-10 rounded-xl shadow-inner border border-slate-200 dark:border-zinc-700 shrink-0 transition-colors" style={{ backgroundColor: serviceForm.theme_color.length === 7 ? serviceForm.theme_color : 'transparent' }}></div>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">Default Credits</label>
                    <input type="number" step="0.1" className={inputClasses} value={serviceForm.default_credits} onChange={e => setServiceForm({...serviceForm, default_credits: parseFloat(e.target.value)})} required />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">Duration (Wks)</label>
                    <input type="number" className={inputClasses} value={serviceForm.default_duration_weeks} onChange={e => setServiceForm({...serviceForm, default_duration_weeks: parseInt(e.target.value)})} required />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">Max Concurrent</label>
                    <input type="number" className={inputClasses} value={serviceForm.max_concurrent_per_week || ''} onChange={e => setServiceForm({...serviceForm, max_concurrent_per_week: parseInt(e.target.value)})} required />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">Display Order</label>
                    <input type="number" className={inputClasses} value={serviceForm.display_order} onChange={e => setServiceForm({...serviceForm, display_order: parseInt(e.target.value)})} placeholder="e.g. 1" />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">Target Goal (Annual)</label>
                  <input type="number" className={inputClasses} value={serviceForm.target_goal || ''} onChange={e => setServiceForm({...serviceForm, target_goal: parseInt(e.target.value) || 0})} placeholder="e.g. 100" />
                </div>

                <div className="pt-4 border-t border-slate-200 dark:border-zinc-800 space-y-4">
                  <Toggle checked={serviceForm.is_active} onChange={(c) => setServiceForm({...serviceForm, is_active: c})} label="Service Lane is Active" />
                  <Toggle checked={serviceForm.auto_provision_workspace} onChange={(c) => setServiceForm({...serviceForm, auto_provision_workspace: c})} label="Auto-Provision Drive Workspace" />
                  <Toggle checked={serviceForm.requires_mitre} onChange={(c) => setServiceForm({...serviceForm, requires_mitre: c})} label="Require MITRE ID" />
                </div>

                {/* PANEL FOOTER ACTIONS */}
                <div className="fixed bottom-0 right-0 w-full max-w-md p-6 bg-white dark:bg-zinc-900 border-t border-slate-100 dark:border-zinc-800 flex justify-end gap-3 z-10">
                  <button type="button" onClick={closePanel} className="px-5 py-2.5 text-sm font-bold bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-zinc-700 rounded-xl transition-colors cursor-pointer">
                    Cancel
                  </button>
                  <button type="submit" className="px-5 py-2.5 text-sm font-bold bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-sm transition-colors cursor-pointer">
                    {editServiceId ? 'Update Service' : 'Save Service'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* KEEP AS MODAL: EMAIL TEMPLATE EDITOR */}
      <TemplateEditorModal
        isOpen={templateModal.isOpen}
        serviceId={templateModal.serviceId}
        serviceName={templateModal.serviceName}
        templateType={templateModal.type}
        initialTemplate={templateModal.initialTemplate}
        onClose={() => setTemplateModal({ ...templateModal, isOpen: false })}
        onSuccess={() => fetchServices()}
      />
    </div>
  );
}