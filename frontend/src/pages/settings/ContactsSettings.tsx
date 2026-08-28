import React, { useState, useEffect, useMemo } from "react";
import axios from "axios";
import toast from "react-hot-toast";
import ConfirmModal from "../../components/Modals/ConfirmModal";
import {
  Users, Search, Filter, Trash2, Edit2, Shield, Code, MapPin,
  Mail, ChevronLeft, ChevronRight, Plus, Server, X
} from "lucide-react";

export default function ContactsSettings() {
  const [contacts, setContacts] = useState<any[]>([]);
  const [countries, setCountries] = useState<any[]>([]);
  const [poolAssets, setPoolAssets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters & Pagination
  const [searchTerm, setSearchTerm] = useState("");
  const [filterRole, setFilterRole] = useState<"all" | "stakeholder" | "developer">("all");
  const [filterCountry, setFilterCountry] = useState<string>("all");
  const [currentPage, setCurrentPage] = useState(1);
  const ITEMS_PER_PAGE = 15;

  // Modals & Panel
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; id: string; email: string } | null>(null);
  const [isPanelOpen, setIsPanelOpen] = useState(false);

  // Advanced Form State
  const defaultForm = {
    contact_id: '', email: '', full_name: '',
    isStakeholder: false, isDeveloper: false,
    countries: [] as any[], assets: [] as any[]
  };
  const [contactForm, setContactForm] = useState(defaultForm);

  // Temporary Form UI States
  const [newCountryId, setNewCountryId] = useState('');
  const [devCountryFilter, setDevCountryFilter] = useState('');
  const [newAssetId, setNewAssetId] = useState('');

  const fetchContacts = async () => {
    try {
      setLoading(true);
      const [resContacts, resCountries, resAssets] = await Promise.all([
        axios.get("/api/contacts/"),
        axios.get("/api/countries/"),
        axios.get("/api/assets/") // Fetches from the Active Pool
      ]);
      setContacts(resContacts.data);
      setCountries(resCountries.data);
      setPoolAssets(resAssets.data);
    } catch (error) {
      toast.error("Failed to load data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchContacts(); }, []);

  const openCreatePanel = () => {
    setContactForm(defaultForm);
    setDevCountryFilter('');
    setNewCountryId('');
    setNewAssetId('');
    setIsPanelOpen(true);
  };

  const openEditPanel = (c: any) => {
    const mappedCountries = c.country_mappings || [];
    const mappedAssets = c.asset_mappings || [];

    setContactForm({
      contact_id: c.id,
      email: c.email,
      full_name: c.full_name || '',
      isStakeholder: mappedCountries.length > 0,
      isDeveloper: mappedAssets.length > 0,
      countries: mappedCountries.map((m: any) => ({ id: m.country_id, name: m.country_name })),
      assets: mappedAssets.map((m: any) => ({ id: m.raw_asset_id, name: m.asset_name }))
    });
    setDevCountryFilter('');
    setNewCountryId('');
    setNewAssetId('');
    setIsPanelOpen(true);
  };

  const closePanel = () => {
    setIsPanelOpen(false);
    setContactForm(defaultForm);
  };

  const submitContact = async (e: React.FormEvent) => {
    e.preventDefault();

    const payload = {
      contact_id: contactForm.contact_id || null,
      email: contactForm.email,
      full_name: contactForm.full_name,
      countries: contactForm.isStakeholder ? contactForm.countries.map(c => ({ id: c.id, is_stakeholder: true, is_developer: false })) : [],
      assets: contactForm.isDeveloper ? contactForm.assets.map(a => ({ id: a.id, is_stakeholder: false, is_developer: true })) : []
    };

    try {
      await axios.post('/api/contacts/sync', payload);
      toast.success("Contact saved successfully!");
      closePanel();
      fetchContacts();
    } catch (err) {
      toast.error("Failed to save contact.");
    }
  };

  const handleDelete = async () => {
    if (!deleteModal) return;
    try {
      await axios.delete(`/api/contacts/global/${deleteModal.id}`);
      toast.success("Contact permanently deleted.");
      fetchContacts();
    } catch (error) {
      toast.error("Failed to delete contact.");
    } finally {
      setDeleteModal(null);
    }
  };

  const filteredContacts = useMemo(() => {
    return contacts.filter(c => {
      const searchMatch = (c.email || "").toLowerCase().includes(searchTerm.toLowerCase()) || (c.full_name || "").toLowerCase().includes(searchTerm.toLowerCase());
      if (!searchMatch) return false;
      const allMappings = [...(c.country_mappings || []), ...(c.asset_mappings || [])];
      if (filterRole === "stakeholder" && !allMappings.some(m => m.is_stakeholder)) return false;
      if (filterRole === "developer" && !allMappings.some(m => m.is_developer)) return false;
      if (filterCountry !== "all" && !(c.country_mappings || []).some((cm: any) => cm.country_id === filterCountry)) return false;
      return true;
    });
  }, [contacts, searchTerm, filterRole, filterCountry]);

  const paginatedContacts = filteredContacts.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE);
  const totalPages = Math.ceil(filteredContacts.length / ITEMS_PER_PAGE) || 1;

  const inputClasses = "w-full mt-1.5 p-2.5 border border-slate-200 dark:border-zinc-800 rounded-xl bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 focus:ring-2 focus:ring-blue-500 outline-none text-sm transition-colors";

  if (loading) return <div className="p-8 text-center text-slate-500">Loading Contacts...</div>;

  return (
    <div className="w-full animate-in fade-in zoom-in-95 duration-200">

      <ConfirmModal
        isOpen={deleteModal?.isOpen || false}
        title="Delete Global Contact"
        message={`Are you sure you want to permanently delete ${deleteModal?.email}? This will remove them from all Country and Asset mappings.`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteModal(null)}
      />

      {/* HEADER & CONTROLS */}
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Users size={22} className="text-blue-500" /> Global Contacts
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-0.5">
            Manage stakeholders and developers across all countries and assets.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full lg:w-auto">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type="text"
              placeholder="Search name or email..."
              className="w-full pl-9 pr-4 py-2.5 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl text-sm outline-none focus:ring-2 focus:ring-blue-500 shadow-sm transition-colors"
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl px-3 shadow-sm h-[42px] overflow-x-auto no-scrollbar">
            <Filter size={14} className="text-slate-400 shrink-0" />
            <select className="bg-transparent text-sm font-bold text-slate-700 dark:text-zinc-300 outline-none cursor-pointer shrink-0" value={filterRole} onChange={e => setFilterRole(e.target.value as any)}>
              <option value="all">All Roles</option>
              <option value="stakeholder">Stakeholders</option>
              <option value="developer">Developers</option>
            </select>
            <div className="w-px h-4 bg-slate-200 dark:bg-zinc-800 mx-1 shrink-0"></div>
            <MapPin size={14} className="text-slate-400 shrink-0" />
            <select className="bg-transparent text-sm font-bold text-slate-700 dark:text-zinc-300 outline-none cursor-pointer max-w-[120px] truncate shrink-0" value={filterCountry} onChange={e => setFilterCountry(e.target.value)}>
              <option value="all">All Countries</option>
              {countries.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>

          <button
            onClick={openCreatePanel}
            className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-xl text-sm font-bold flex justify-center items-center gap-2 shadow-sm transition-colors cursor-pointer"
          >
            <Plus size={16} /> Add Contact
          </button>
        </div>
      </div>

      {/* TABLE CONTAINER */}
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-sm overflow-hidden flex flex-col min-h-[500px]">
        {/* DESKTOP TABLE */}
        <table className="hidden md:table w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-slate-50 dark:bg-zinc-950/50 border-b border-slate-200 dark:border-zinc-800">
            <tr>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 w-1/3">Contact Details</th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 w-1/3">Assignments</th>
              <th className="p-4 font-bold text-slate-600 dark:text-zinc-400 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
            {paginatedContacts.map(c => {
              const mappedCountries = c.country_mappings || [];
              const mappedAssets = c.asset_mappings || [];

              return (
                <tr key={c.id} className="hover:bg-slate-50/50 dark:hover:bg-zinc-800/30 transition-colors">
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800/50 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold shrink-0">
                        {c.full_name ? c.full_name.charAt(0).toUpperCase() : <Mail size={18}/>}
                      </div>
                      <div className="min-w-0">
                        <div className="font-bold text-slate-900 dark:text-zinc-100 truncate">{c.full_name || 'No Name Provided'}</div>
                        <div className="text-slate-500 dark:text-zinc-400 text-xs mt-0.5 truncate">{c.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="p-4 whitespace-normal">
                    <div className="flex flex-col gap-2">
                      {mappedCountries.length > 0 && (
                        <div className="flex gap-1.5 flex-wrap">
                          {mappedCountries.map((mc: any, idx: number) => (
                             <span key={`c-${idx}`} className="px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-900/50 text-[10px] font-bold text-amber-700 dark:text-amber-400 flex gap-1 items-center">
                               <Shield size={10}/> {mc.country_name}
                             </span>
                          ))}
                        </div>
                      )}
                      {mappedAssets.length > 0 && (
                        <div className="flex gap-1.5 flex-wrap">
                          {mappedAssets.map((ma: any, idx: number) => (
                             <span key={`a-${idx}`} className="px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-900/50 text-[10px] font-bold text-indigo-700 dark:text-indigo-400 flex gap-1 items-center">
                               <Code size={10}/> {ma.asset_name}
                             </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="p-4 text-right">
                    <div className="flex justify-end gap-2">
                      <button onClick={() => openEditPanel(c)} className="text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 p-2 rounded-xl transition-colors cursor-pointer">
                        <Edit2 size={16} />
                      </button>
                      <button onClick={() => setDeleteModal({isOpen: true, id: c.id, email: c.email})} className="text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 p-2 rounded-xl transition-colors cursor-pointer">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {/* MOBILE LIST */}
        <div className="md:hidden flex flex-col divide-y divide-slate-100 dark:divide-zinc-800">
          {paginatedContacts.map(c => {
             const mappedCountries = c.country_mappings || [];
             const mappedAssets = c.asset_mappings || [];

             return (
              <div key={c.id} className="p-4 flex flex-col gap-3">
                <div className="flex justify-between items-start gap-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-full bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800/50 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold shrink-0">
                      {c.full_name ? c.full_name.charAt(0).toUpperCase() : <Mail size={18}/>}
                    </div>
                    <div className="min-w-0">
                      <div className="font-bold text-base text-slate-900 dark:text-zinc-100 truncate">{c.full_name || 'No Name'}</div>
                      <div className="text-slate-500 dark:text-zinc-400 text-xs mt-0.5 truncate">{c.email}</div>
                    </div>
                  </div>
                </div>

                {(mappedCountries.length > 0 || mappedAssets.length > 0) && (
                  <div className="flex flex-col gap-1.5 bg-slate-50 dark:bg-zinc-950 p-2.5 rounded-xl border border-slate-100 dark:border-zinc-800">
                    <div className="flex gap-1.5 flex-wrap">
                      {mappedCountries.map((mc: any, idx: number) => (
                        <span key={`mc-${idx}`} className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-900/50 text-[9px] font-extrabold uppercase tracking-wider text-amber-700 dark:text-amber-400"><Shield size={10}/> {mc.country_name}</span>
                      ))}
                    </div>
                    <div className="flex gap-1.5 flex-wrap">
                      {mappedAssets.map((ma: any, idx: number) => (
                        <span key={`ma-${idx}`} className="flex items-center gap-1 px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-900/50 text-[9px] font-extrabold uppercase tracking-wider text-indigo-700 dark:text-indigo-400"><Code size={10}/> {ma.asset_name}</span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex justify-end gap-2 mt-1">
                  <button onClick={() => openEditPanel(c)} className="text-slate-600 dark:text-zinc-300 bg-slate-100 dark:bg-zinc-800 p-2 rounded-xl flex-1 flex justify-center items-center font-bold text-xs gap-1">
                    <Edit2 size={14} /> Edit
                  </button>
                  <button onClick={() => setDeleteModal({isOpen: true, id: c.id, email: c.email})} className="text-red-600 bg-red-50 dark:bg-red-900/20 p-2 rounded-xl flex-1 flex justify-center items-center font-bold text-xs gap-1">
                    <Trash2 size={14} /> Delete
                  </button>
                </div>
              </div>
             )
          })}
        </div>

        {filteredContacts.length === 0 && (
          <div className="flex-1 flex items-center justify-center text-slate-500 text-sm p-12">No contacts found matching your filters.</div>
        )}

        {/* PAGINATION */}
        {filteredContacts.length > 0 && (
          <div className="px-4 py-3.5 border-t border-slate-200 dark:border-zinc-800 flex justify-between items-center bg-slate-50 dark:bg-zinc-950/50 mt-auto">
            <span className="text-xs md:text-sm text-slate-500 dark:text-zinc-400">Page {currentPage} of {totalPages}</span>
            <div className="flex gap-2">
              <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1} className="p-1.5 border border-slate-200 dark:border-zinc-700 rounded-lg disabled:opacity-50 hover:bg-white dark:hover:bg-zinc-800 transition-colors text-slate-700 dark:text-zinc-300 bg-white dark:bg-zinc-900 cursor-pointer">
                <ChevronLeft size={16}/>
              </button>
              <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages} className="p-1.5 border border-slate-200 dark:border-zinc-700 rounded-lg disabled:opacity-50 hover:bg-white dark:hover:bg-zinc-800 transition-colors text-slate-700 dark:text-zinc-300 bg-white dark:bg-zinc-900 cursor-pointer">
                <ChevronRight size={16}/>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* RIGHT SLIDE-OVER FORM PANEL */}
      {isPanelOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-slate-900/40 dark:bg-zinc-950/70 backdrop-blur-sm transition-opacity animate-in fade-in" onClick={closePanel} />

          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-md bg-white dark:bg-zinc-900 border-l border-slate-200 dark:border-zinc-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">

              <div className="p-6 border-b border-slate-100 dark:border-zinc-800 flex justify-between items-center bg-slate-50/50 dark:bg-zinc-950/50">
                <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100">
                  {contactForm.contact_id ? 'Edit Contact & Roles' : 'Add New Contact'}
                </h3>
                <button onClick={closePanel} className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer">
                  <X size={18} />
                </button>
              </div>

              <form onSubmit={submitContact} className="flex-1 p-6 overflow-y-auto space-y-6 pb-24">

                <div className="space-y-4">
                  <div>
                    <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">Email Address</label>
                    <input type="email" className={inputClasses} value={contactForm.email} onChange={e => setContactForm({...contactForm, email: e.target.value.toLowerCase()})} required placeholder="contact@company.com" />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">Full Name (Optional)</label>
                    <input type="text" className={inputClasses} value={contactForm.full_name} onChange={e => setContactForm({...contactForm, full_name: e.target.value})} placeholder="John Doe" />
                  </div>
                </div>

                <div className="pt-2">
                  <span className="text-xs font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider block mb-3">System Roles</span>
                  <div className="flex flex-col gap-3">
                    <label className="flex items-center gap-3 cursor-pointer text-amber-700 dark:text-amber-500 font-bold bg-amber-50 dark:bg-amber-900/10 p-3 rounded-xl border border-amber-200 dark:border-amber-900/30">
                      <input type="checkbox" className="w-4 h-4 accent-amber-600" checked={contactForm.isStakeholder} onChange={e => setContactForm({...contactForm, isStakeholder: e.target.checked})} />
                      <Shield size={18}/> Assign as Stakeholder
                    </label>
                    <label className="flex items-center gap-3 cursor-pointer text-indigo-700 dark:text-indigo-500 font-bold bg-indigo-50 dark:bg-indigo-900/10 p-3 rounded-xl border border-indigo-200 dark:border-indigo-900/30">
                      <input type="checkbox" className="w-4 h-4 accent-indigo-600" checked={contactForm.isDeveloper} onChange={e => setContactForm({...contactForm, isDeveloper: e.target.checked})} />
                      <Code size={18}/> Assign as Developer
                    </label>
                  </div>
                </div>

                {/* Conditional Role Mapping Sections */}
                <div className="space-y-6">

                  {/* Stakeholder -> Countries */}
                  {contactForm.isStakeholder && (
                    <div className="bg-amber-50/50 dark:bg-amber-950/10 p-4 rounded-xl border border-amber-200 dark:border-amber-900/30 animate-in fade-in">
                      <h4 className="font-bold text-sm flex items-center gap-2 mb-3 text-amber-800 dark:text-amber-500"><MapPin size={16}/> Stakeholder Countries</h4>
                      <div className="space-y-2 mb-4 max-h-40 overflow-y-auto pr-2 custom-scrollbar">
                        {contactForm.countries.map(c => (
                          <div key={c.id} className="flex justify-between items-center bg-white dark:bg-zinc-900 p-2.5 rounded-lg border border-slate-200 dark:border-zinc-800 text-xs shadow-sm">
                            <span className="font-bold truncate pr-2 text-slate-700 dark:text-zinc-300">{c.name}</span>
                            <button type="button" onClick={() => setContactForm({...contactForm, countries: contactForm.countries.filter(x => x.id !== c.id)})} className="text-slate-400 hover:text-red-500 cursor-pointer"><Trash2 size={14}/></button>
                          </div>
                        ))}
                        {contactForm.countries.length === 0 && <span className="text-xs text-slate-500 italic block p-2">No countries assigned.</span>}
                      </div>
                      <div className="flex gap-2">
                        <select className="flex-1 p-2.5 text-xs border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 outline-none text-slate-700 dark:text-zinc-300 font-medium" value={newCountryId} onChange={e => setNewCountryId(e.target.value)}>
                          <option value="">Select Country...</option>
                          {countries.filter(c => !contactForm.countries.find(existing => existing.id === c.id)).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                        </select>
                        <button type="button" disabled={!newCountryId} onClick={() => {
                          const countryName = countries.find(c => c.id === newCountryId)?.name;
                          setContactForm({...contactForm, countries: [...contactForm.countries, { id: newCountryId, name: countryName }]});
                          setNewCountryId('');
                        }} className="bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold px-4 rounded-lg disabled:opacity-50 transition-colors shadow-sm cursor-pointer">Add</button>
                      </div>
                    </div>
                  )}

                  {/* Developer -> Assets */}
                  {contactForm.isDeveloper && (
                    <div className="bg-indigo-50/50 dark:bg-indigo-950/10 p-4 rounded-xl border border-indigo-200 dark:border-indigo-900/30 animate-in fade-in">
                      <h4 className="font-bold text-sm flex items-center gap-2 mb-3 text-indigo-800 dark:text-indigo-500"><Server size={16}/> Developer Assets</h4>
                      <div className="space-y-2 mb-4 max-h-40 overflow-y-auto pr-2 custom-scrollbar">
                        {contactForm.assets.map(a => (
                          <div key={a.id} className="flex justify-between items-center bg-white dark:bg-zinc-900 p-2.5 rounded-lg border border-slate-200 dark:border-zinc-800 text-xs shadow-sm">
                            <span className="font-bold truncate pr-2 text-slate-700 dark:text-zinc-300">{a.name}</span>
                            <button type="button" onClick={() => setContactForm({...contactForm, assets: contactForm.assets.filter(x => x.id !== a.id)})} className="text-slate-400 hover:text-red-500 cursor-pointer"><Trash2 size={14}/></button>
                          </div>
                        ))}
                        {contactForm.assets.length === 0 && <span className="text-xs text-slate-500 italic block p-2">No assets assigned.</span>}
                      </div>
                      <div className="flex flex-col gap-2">
                        <select className="w-full p-2.5 text-xs border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 outline-none text-slate-700 dark:text-zinc-300 font-medium" value={devCountryFilter} onChange={e => { setDevCountryFilter(e.target.value); setNewAssetId(''); }}>
                          <option value="">Filter by Country...</option>
                          {countries.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                        </select>
                        <div className="flex gap-2">
                          <select disabled={!devCountryFilter} className="flex-1 p-2.5 text-xs border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-900 outline-none disabled:opacity-50 text-slate-700 dark:text-zinc-300 font-medium" value={newAssetId} onChange={e => setNewAssetId(e.target.value)}>
                            <option value="">Select Asset...</option>
                            {poolAssets.filter(pa => pa.country_id === devCountryFilter && !contactForm.assets.find(existing => existing.id === pa.raw_asset_id)).map(pa => <option key={pa.raw_asset_id} value={pa.raw_asset_id}>{pa.name}</option>)}
                          </select>
                          <button type="button" disabled={!newAssetId} onClick={() => {
                            const assetName = poolAssets.find(pa => pa.raw_asset_id === newAssetId)?.name;
                            setContactForm({...contactForm, assets: [...contactForm.assets, { id: newAssetId, name: assetName }]});
                            setNewAssetId('');
                          }} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-4 rounded-lg disabled:opacity-50 transition-colors shadow-sm cursor-pointer">Add</button>
                        </div>
                      </div>
                    </div>
                  )}

                </div>

                {/* PANEL FOOTER */}
                <div className="fixed bottom-0 right-0 w-full max-w-md p-6 bg-white dark:bg-zinc-900 border-t border-slate-100 dark:border-zinc-800 flex justify-end gap-3 z-10">
                  <button type="button" onClick={closePanel} className="px-5 py-2.5 text-sm font-bold bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-zinc-700 rounded-xl transition-colors cursor-pointer">
                    Cancel
                  </button>
                  <button type="submit" className="px-5 py-2.5 text-sm font-bold bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-sm transition-colors cursor-pointer">
                    {contactForm.contact_id ? 'Update Contact' : 'Save Contact'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}