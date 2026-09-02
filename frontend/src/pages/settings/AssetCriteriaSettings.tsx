import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import toast, { Toaster } from 'react-hot-toast';
import ConfirmModal from '../../components/Modals/ConfirmModal';
import {
  Settings2, Plus, Edit2, Trash2, X, Play, ListFilter, ChevronDown, ChevronRight
} from 'lucide-react';

// --- Custom Multi-Select Component ---
const CustomMultiSelect = ({ options, value, onChange }: { options: any[], value: any[], onChange: (val: any[]) => void }) => {
  const [isOpen, setIsOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedCount = Array.isArray(value) ? value.length : 0;

  return (
    <div className="relative" ref={wrapperRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full p-2.5 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors flex justify-between items-center text-left"
      >
        <span className={selectedCount === 0 ? "text-slate-400" : "text-slate-900 dark:text-zinc-100 font-medium"}>
          {selectedCount === 0 ? "Select options..." : `${selectedCount} option(s) selected`}
        </span>
        <ChevronDown size={16} className={`text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute z-50 top-full mt-1.5 left-0 w-full bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 rounded-xl shadow-xl max-h-56 overflow-y-auto p-2 animate-in fade-in slide-in-from-top-2">
          {options.length === 0 ? (
            <div className="p-2 text-xs text-slate-500 italic text-center">Loading...</div>
          ) : (
            options.map(opt => (
              <label key={opt.id} className="flex items-center gap-2.5 p-2 hover:bg-slate-50 dark:hover:bg-zinc-800 rounded-lg cursor-pointer text-sm text-slate-700 dark:text-zinc-300 transition-colors">
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-950"
                  checked={Array.isArray(value) && value.includes(opt.id)}
                  onChange={(e) => {
                    const current = Array.isArray(value) ? value : [];
                    if (e.target.checked) onChange([...current, opt.id]);
                    else onChange(current.filter(id => id !== opt.id));
                  }}
                />
                <span className="truncate">{opt.name}</span>
              </label>
            ))
          )}
        </div>
      )}
    </div>
  );
};

// --- Main Settings Component ---
const OPERATORS = [
  { value: '==', label: 'Equals (==)' },
  { value: '!=', label: 'Not Equals (!=)' },
  { value: 'contains', label: 'Contains' },
  { value: 'in', label: 'In List (OR logic)' },
  { value: '>', label: 'Greater Than (>)' },
  { value: '<', label: 'Less Than (<)' },
  { value: 'is_null', label: 'Is Null' },
  { value: 'is_not_null', label: 'Is Not Null' }
];

const defaultForm = { year: new Date().getFullYear(), criticality_threshold: 8, kpi_rules: [] };

export default function AssetCriteriaSettings() {
  const [criteria, setCriteria] = useState<any[]>([]);
  const [schemaFields, setSchemaFields] = useState<any[]>([]);
  const [relationCache, setRelationCache] = useState<Record<string, any[]>>({});
  const [isLoading, setIsLoading] = useState(true);

  // Panel & Table State
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [editYear, setEditYear] = useState<number | null>(null);
  const [formData, setFormData] = useState<any>(defaultForm);
  const [expandedYears, setExpandedYears] = useState<Set<number>>(new Set());

  const [actionModal, setActionModal] = useState<{ isOpen: boolean; year: number; type: 'delete' | 'evaluate' } | null>(null);

  const fetchInitialData = async () => {
    try {
      setIsLoading(true);
      const [critRes, fieldsRes] = await Promise.all([
        axios.get('/api/asset-criteria/'),
        axios.get('/api/asset-criteria/fields')
      ]);
      setCriteria(critRes.data);
      setSchemaFields(fieldsRes.data);
    } catch (error) {
      toast.error('Failed to load criteria engine data.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { fetchInitialData(); }, []);

  const fetchRelationData = async (endpoint: string) => {
    if (relationCache[endpoint]) return;
    try {
      const res = await axios.get(endpoint);
      setRelationCache(prev => ({ ...prev, [endpoint]: res.data }));
    } catch (error) {
      toast.error('Failed to load dynamic field options.');
    }
  };

  const toggleRowExpansion = (year: number) => {
    setExpandedYears(prev => {
      const next = new Set(prev);
      if (next.has(year)) next.delete(year);
      else next.add(year);
      return next;
    });
  };

  const openPanel = (c?: any) => {
    if (c) {
      setEditYear(c.year);
      setFormData({ year: c.year, criticality_threshold: c.criticality_threshold, kpi_rules: c.kpi_rules || [] });
      c.kpi_rules.forEach((rule: any) => {
        const fieldDef = schemaFields.find(f => f.name === rule.field);
        if (fieldDef?.type === 'relation') fetchRelationData(fieldDef.endpoint);
      });
    } else {
      setEditYear(null);
      setFormData(defaultForm);
    }
    setIsPanelOpen(true);
  };

  const handleRuleChange = (index: number, key: string, val: any) => {
    setFormData((prev: any) => {
      const newRules = [...prev.kpi_rules];
      newRules[index] = { ...newRules[index], [key]: val };

      if (key === 'field') {
        const fieldDef = schemaFields.find(f => f.name === val);
        newRules[index].value = '';
        if (fieldDef?.type === 'boolean') newRules[index].value = true;
        if (fieldDef?.type === 'relation') fetchRelationData(fieldDef.endpoint);
      }

      if (key === 'operator' && (val === 'is_null' || val === 'is_not_null')) {
        newRules[index].value = null;
      }
      if (key === 'operator' && val === 'in' && !Array.isArray(newRules[index].value)) {
         newRules[index].value = newRules[index].value ? [newRules[index].value] : [];
      }
      if (key === 'operator' && val !== 'in' && Array.isArray(newRules[index].value)) {
         newRules[index].value = newRules[index].value[0] || '';
      }

      return { ...prev, kpi_rules: newRules };
    });
  };

  const submitCriteria = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const processedRules = formData.kpi_rules.map((rule: any) => {
        if (rule.operator === 'in' && typeof rule.value === 'string') {
          return { ...rule, value: rule.value.split(',').map((s: string) => s.trim()).filter(Boolean) };
        }
        return rule;
      });

      await axios.post('/api/asset-criteria/', { ...formData, kpi_rules: processedRules });
      toast.success('Criteria saved.');
      setIsPanelOpen(false);
      fetchInitialData();
    } catch (error) {
      toast.error('Failed to save criteria.');
    }
  };

  const executeAction = async () => {
    if (!actionModal) return;

    // 1. Extract the values we need before destroying the state
    const { year, type } = actionModal;

    // 2. Close the modal instantly for a snappy UI
    setActionModal(null);

    try {
      if (type === 'delete') {
        await axios.delete(`/api/asset-criteria/${year}`);
        toast.success(`Criteria for ${year} deleted.`);
        fetchInitialData();
      } else {
        const toastId = toast.loading(`Evaluating assets for ${year}...`);
        const res = await axios.post(`/api/asset-criteria/evaluate/${year}`, {});
        toast.success(`Evaluated ${res.data.assets_evaluated} assets. Updated ${res.data.assets_updated} records.`, { id: toastId });
      }
    } catch (error) {
      toast.error(`${type === 'delete' ? 'Deletion' : 'Evaluation'} failed.`);
    }
  };

  const inputClasses = "w-full p-2.5 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors";

  if (isLoading) return <div className="p-8 text-center text-slate-500">Loading criteria...</div>;

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">
      <Toaster position="bottom-right" />
      <ConfirmModal
        isOpen={!!actionModal}
        title={actionModal?.type === 'delete' ? 'Confirm Deletion' : 'Evaluate Assets'}
        message={actionModal?.type === 'delete' ? `Delete criteria for ${actionModal.year}?` : `Evaluate ALL non-team assets against ${actionModal?.year} criteria?`}
        confirmText={actionModal?.type === 'delete' ? 'Delete' : 'Run Evaluation'}
        variant={actionModal?.type === 'delete' ? 'danger' : 'info'}
        onConfirm={executeAction}
        onCancel={() => setActionModal(null)}
      />

      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Settings2 size={22} className="text-blue-500" /> Asset Criteria
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-0.5">Manage rules for KPI and Criticality flags.</p>
        </div>
        <button onClick={() => openPanel()} className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 shadow-sm transition-colors cursor-pointer">
          <Plus size={16} /> New Criteria
        </button>
      </div>

      <div className="border border-slate-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm flex flex-col bg-white dark:bg-zinc-900">
        <table className="hidden md:table w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-slate-50 dark:bg-zinc-950/50 border-b border-slate-200 dark:border-zinc-800 select-none">
            <tr>
              <th className="p-4 w-10"></th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Year</th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">Criticality Threshold</th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400">KPI Rules</th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
            {criteria.map(c => (
              <React.Fragment key={c.id}>
                <tr className="hover:bg-slate-50/50 dark:hover:bg-zinc-800/30 transition-colors">
                  <td className="p-4 cursor-pointer" onClick={() => toggleRowExpansion(c.year)}>
                    <ChevronRight size={16} className={`text-slate-400 transition-transform ${expandedYears.has(c.year) ? 'rotate-90 text-blue-500' : ''}`} />
                  </td>
                  <td className="p-4 font-bold text-slate-900 dark:text-zinc-100 text-base">{c.year}</td>
                  <td className="p-4"><span className="font-mono bg-slate-100 dark:bg-zinc-800 px-2 py-1 rounded border border-slate-200 dark:border-zinc-700 text-slate-700 dark:text-zinc-300">≥ {c.criticality_threshold}</span></td>
                  <td className="p-4 text-slate-500 dark:text-zinc-400"><div className="flex items-center gap-1.5"><ListFilter size={14} /> {c.kpi_rules.length}</div></td>
                  <td className="p-4 text-right">
                    <div className="flex justify-end gap-2">
                      <button onClick={(e) => { e.stopPropagation(); setActionModal({ isOpen: true, year: c.year, type: 'evaluate' }) }} className="text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 p-2 rounded-xl transition-colors cursor-pointer" title="Evaluate Assets"><Play size={16} className="fill-current" /></button>
                      <button onClick={(e) => { e.stopPropagation(); openPanel(c) }} className="text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 p-2 rounded-xl transition-colors cursor-pointer"><Edit2 size={16} /></button>
                      <button onClick={(e) => { e.stopPropagation(); setActionModal({ isOpen: true, year: c.year, type: 'delete' }) }} className="text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 p-2 rounded-xl transition-colors cursor-pointer"><Trash2 size={16} /></button>
                    </div>
                  </td>
                </tr>
                {expandedYears.has(c.year) && (
                  <tr className="bg-slate-50/50 dark:bg-zinc-950/30 border-t-0">
                    <td colSpan={5} className="p-6 pt-2">
                      <div className="ml-10 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl p-4 shadow-sm">
                        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Active KPI Conditions</h4>
                        {c.kpi_rules.length === 0 ? (
                          <span className="text-sm text-slate-400 italic">No rules defined.</span>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            {c.kpi_rules.map((r: any, i: number) => {
                              const fieldDef = schemaFields.find(f => f.name === r.field);
                              return (
                                <div key={i} className="flex items-center gap-2 text-xs bg-slate-50 dark:bg-zinc-950 border border-slate-100 dark:border-zinc-800 px-3 py-1.5 rounded-lg shadow-sm">
                                  <span className="font-bold text-blue-600 dark:text-blue-400">{fieldDef?.label || r.field}</span>
                                  <span className="font-mono text-slate-400 px-1">{r.operator}</span>
                                  {r.value !== null && (
                                    <span className="font-semibold text-slate-700 dark:text-zinc-300">
                                      {Array.isArray(r.value) ? `[${r.value.length} selected]` : String(r.value)}
                                    </span>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
        {criteria.length === 0 && <div className="p-12 text-center text-sm text-slate-500">No criteria configured.</div>}
      </div>

      {/* RIGHT SLIDE-OVER FORM PANEL */}
      {isPanelOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-slate-900/40 dark:bg-zinc-950/70 backdrop-blur-sm transition-opacity animate-in fade-in" onClick={() => setIsPanelOpen(false)} />
          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-2xl bg-white dark:bg-zinc-900 border-l border-slate-200 dark:border-zinc-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
              <div className="p-6 border-b border-slate-100 dark:border-zinc-800 flex justify-between items-center bg-slate-50/50 dark:bg-zinc-950/50">
                <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100">{editYear ? 'Edit Criteria' : 'New Criteria'}</h3>
                <button onClick={() => setIsPanelOpen(false)} className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors cursor-pointer"><X size={18} /></button>
              </div>

              <form onSubmit={submitCriteria} className="flex-1 p-6 overflow-y-auto space-y-8 mb-20">
                <div>
                  <h4 className="text-sm font-bold text-slate-900 dark:text-zinc-100 mb-4 border-b border-slate-200 dark:border-zinc-800 pb-2">1. Base Configuration</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">Target Year</label>
                      <input type="number" className={inputClasses + " mt-1.5"} value={formData.year} onChange={e => setFormData({ ...formData, year: parseInt(e.target.value) || new Date().getFullYear() })} required />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">Criticality Threshold (≥)</label>
                      <input type="number" className={inputClasses + " mt-1.5"} value={formData.criticality_threshold} onChange={e => setFormData({ ...formData, criticality_threshold: parseInt(e.target.value) || 0 })} required />
                    </div>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-4 border-b border-slate-200 dark:border-zinc-800 pb-2">
                    <h4 className="text-sm font-bold text-slate-900 dark:text-zinc-100">2. KPI Conditions (AND across fields, OR within same field)</h4>
                    <button type="button" onClick={() => setFormData((p: any) => ({ ...p, kpi_rules: [...p.kpi_rules, { field: '', operator: '==', value: '' }] }))} className="text-xs font-bold text-blue-600 hover:text-blue-700 flex items-center gap-1 transition-colors">
                      <Plus size={14} /> Add Rule
                    </button>
                  </div>

                  <div className="space-y-4">
                    {formData.kpi_rules.map((rule: any, idx: number) => {
                      const fieldDef = schemaFields.find(f => f.name === rule.field);
                      const isNullOp = rule.operator === 'is_null' || rule.operator === 'is_not_null';
                      const isRelation = fieldDef?.type === 'relation';
                      const isBoolean = fieldDef?.type === 'boolean';
                      const options = isRelation ? relationCache[fieldDef.endpoint] || [] : [];
                      const isInOp = rule.operator === 'in';

                      return (
                        <div key={idx} className="flex items-start gap-3 bg-slate-50 dark:bg-zinc-950/50 p-4 rounded-2xl border border-slate-200 dark:border-zinc-800">
                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 flex-1">
                            <div>
                              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">Field</label>
                              <select value={rule.field} onChange={(e) => handleRuleChange(idx, 'field', e.target.value)} className={inputClasses} required>
                                <option value="" disabled>Select Field...</option>
                                {schemaFields.map(f => <option key={f.name} value={f.name}>{f.label}</option>)}
                              </select>
                            </div>
                            <div>
                              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">Operator</label>
                              <select value={rule.operator} onChange={(e) => handleRuleChange(idx, 'operator', e.target.value)} className={inputClasses}>
                                {OPERATORS.map(op => <option key={op.value} value={op.value}>{op.label}</option>)}
                              </select>
                            </div>
                            <div>
                              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">Value</label>
                              {isNullOp ? (
                                <div className="p-2.5 text-sm text-slate-400 italic bg-slate-100 dark:bg-zinc-900 rounded-xl border border-dashed border-slate-300 dark:border-zinc-700">Not required</div>
                              ) : isBoolean ? (
                                <select value={String(rule.value)} onChange={(e) => handleRuleChange(idx, 'value', e.target.value === 'true')} className={inputClasses} required>
                                  <option value="true">True</option>
                                  <option value="false">False</option>
                                </select>
                              ) : isRelation ? (
                                isInOp ? (
                                  <CustomMultiSelect
                                    options={options}
                                    value={Array.isArray(rule.value) ? rule.value : []}
                                    onChange={(newVal) => handleRuleChange(idx, 'value', newVal)}
                                  />
                                ) : (
                                  <select value={rule.value} onChange={(e) => handleRuleChange(idx, 'value', e.target.value)} className={inputClasses} required>
                                    <option value="" disabled>Select Option...</option>
                                    {options.map(opt => <option key={opt.id} value={opt.id}>{opt.name}</option>)}
                                  </select>
                                )
                              ) : (
                                <input type={fieldDef?.type === 'number' ? 'number' : 'text'} placeholder="Value..." value={rule.value || ''} onChange={(e) => handleRuleChange(idx, 'value', e.target.value)} className={inputClasses} required />
                              )}
                            </div>
                          </div>
                          <button type="button" onClick={() => setFormData((p: any) => ({ ...p, kpi_rules: p.kpi_rules.filter((_: any, i: number) => i !== idx) }))} className="mt-5 p-2.5 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-xl transition-colors shrink-0">
                            <Trash2 size={16} />
                          </button>
                        </div>
                      )
                    })}
                    {formData.kpi_rules.length === 0 && <div className="p-8 text-center border-2 border-dashed border-slate-200 dark:border-zinc-800 rounded-2xl text-sm text-slate-500">No KPI conditions configured.</div>}
                  </div>
                </div>

                <div className="fixed bottom-0 right-0 w-full max-w-2xl p-6 bg-white dark:bg-zinc-900 border-t border-slate-100 dark:border-zinc-800 flex justify-end gap-3 z-10">
                  <button type="button" onClick={() => setIsPanelOpen(false)} className="px-5 py-2.5 text-sm font-bold bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 hover:bg-slate-200 hover:text-slate-900 rounded-xl transition-colors cursor-pointer">Cancel</button>
                  <button type="submit" className="px-5 py-2.5 text-sm font-bold bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-sm transition-colors cursor-pointer">{editYear ? 'Update' : 'Save'} Criteria</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}