import { useState, useEffect, useMemo } from "react";
import axios from "axios";
import TopNav from "../components/TopNav";
import ConfirmModal from "../components/Modals/ConfirmModal";
import toast, { Toaster } from "react-hot-toast";
import { Users, Search, Filter, Trash2, Edit2, Shield, Code, MapPin, Mail, ChevronLeft, ChevronRight, Plus, Server } from "lucide-react";

export default function ContactsView() {
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

  // Modals & Forms
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; id: string; email: string } | null>(null);
  const [showForm, setShowForm] = useState(false);

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

  // --- SUBMIT SYNC ---
  const submitContact = async (e: React.FormEvent) => {
    e.preventDefault();

    // Only submit mappings if their corresponding role box is checked
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
      setShowForm(false);
      setContactForm(defaultForm);
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

  // --- FILTERING LOGIC ---
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

  if (loading) return <div className="min-h-screen bg-slate-50 dark:bg-[#09090b] flex justify-center items-center">Loading Contacts...</div>;

  const inputClasses = "w-full mt-1 p-2.5 md:p-2 border border-slate-200 dark:border-zinc-800 rounded-lg bg-slate-50 dark:bg-zinc-950 outline-none focus:ring-2 focus:ring-blue-500 text-sm";

  return (
    <div className="min-h-screen text-slate-900 dark:text-zinc-100 pb-12 bg-slate-50/50 dark:bg-[#09090b]">
      <TopNav />
      <Toaster position="bottom-right" />

      <ConfirmModal
        isOpen={deleteModal?.isOpen || false}
        title="Delete Global Contact"
        message={`Are you sure you want to permanently delete ${deleteModal?.email}? This will remove them from all Country and Asset mappings.`}
        onConfirm={handleDelete}
        onCancel={() => setDeleteModal(null)}
      />

      <div className="pt-28 md:pt-32 px-4 md:px-6 max-w-7xl mx-auto">

        {/* Header & Controls */}
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-end mb-6 gap-4 w-full">
          <div>
            <h1 className="text-2xl md:text-3xl font-black flex items-center gap-2 tracking-tight"><Users size={28} className="text-blue-600" /> Global Contacts</h1>
            <p className="text-sm text-slate-500 mt-1 font-medium">Manage stakeholders and developers across all countries and assets.</p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full lg:w-auto">
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input type="text" placeholder="Search name or email..." className="w-full pl-10 pr-4 py-2.5 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl text-sm outline-none focus:ring-2 focus:ring-blue-500 shadow-sm" value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
            </div>
            <div className="flex items-center gap-2 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl px-3 shadow-sm h-[42px] w-full sm:w-auto overflow-x-auto no-scrollbar">
              <Filter size={16} className="text-slate-400 shrink-0" />
              <select className="bg-transparent text-sm font-bold outline-none cursor-pointer shrink-0" value={filterRole} onChange={e => setFilterRole(e.target.value as any)}>
                <option value="all">All Roles</option><option value="stakeholder">Stakeholders</option><option value="developer">Developers</option>
              </select>
              <div className="w-px h-5 bg-slate-200 dark:bg-zinc-800 mx-1 shrink-0"></div>
              <MapPin size={16} className="text-slate-400 shrink-0" />
              <select className="bg-transparent text-sm font-bold outline-none cursor-pointer max-w-[120px] truncate shrink-0" value={filterCountry} onChange={e => setFilterCountry(e.target.value)}>
                <option value="all">All Countries</option>
                {countries.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <button onClick={() => { setShowForm(!showForm); setContactForm(defaultForm); }} className="bg-blue-600 hover:bg-blue-700 text-white px-4 rounded-xl text-sm font-medium flex justify-center items-center gap-2 h-[42px] shadow-sm shrink-0">
              <Plus size={16} /> Add Contact
            </button>
          </div>
        </div>

        {/* --- CREATION / EDIT FORM --- */}
        {showForm && (
          <form onSubmit={submitContact} className="bg-white dark:bg-zinc-900 p-4 md:p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 mb-6 shadow-sm animate-in fade-in slide-in-from-top-4">
            <h3 className="font-bold text-lg text-slate-900 dark:text-zinc-100 mb-4">{contactForm.contact_id ? 'Edit Contact & Roles' : 'Add New Contact'}</h3>

            {/* Basic Info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Email Address <input type="email" className={inputClasses} value={contactForm.email} onChange={e => setContactForm({...contactForm, email: e.target.value.toLowerCase()})} required placeholder="contact@company.com" /></label>
              <label className="text-sm font-bold text-slate-700 dark:text-zinc-300">Full Name (Optional) <input type="text" className={inputClasses} value={contactForm.full_name} onChange={e => setContactForm({...contactForm, full_name: e.target.value})} placeholder="John Doe" /></label>
            </div>

            {/* Role Toggles */}
            <div className="flex gap-6 mb-6 pb-4 border-b border-slate-100 dark:border-zinc-800">
              <label className="flex items-center gap-2 text-sm font-bold cursor-pointer text-amber-700 dark:text-amber-500">
                <input type="checkbox" className="w-4 h-4 accent-amber-600" checked={contactForm.isStakeholder} onChange={e => setContactForm({...contactForm, isStakeholder: e.target.checked})} />
                <Shield size={18}/> Assign as Stakeholder
              </label>
              <label className="flex items-center gap-2 text-sm font-bold cursor-pointer text-indigo-700 dark:text-indigo-500">
                <input type="checkbox" className="w-4 h-4 accent-indigo-600" checked={contactForm.isDeveloper} onChange={e => setContactForm({...contactForm, isDeveloper: e.target.checked})} />
                <Code size={18}/> Assign as Developer
              </label>
            </div>

            {/* Conditional Role Mapping Sections */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

              {/* Stakeholder -> Countries */}
              {contactForm.isStakeholder && (
                <div className="bg-amber-50/50 dark:bg-amber-950/10 p-4 rounded-xl border border-amber-200 dark:border-amber-900/30 animate-in fade-in">
                  <h4 className="font-bold text-sm flex items-center gap-2 mb-3 text-amber-800 dark:text-amber-500"><MapPin size={16}/> Stakeholder Countries</h4>
                  <div className="space-y-2 mb-4 max-h-40 overflow-y-auto pr-2">
                    {contactForm.countries.map(c => (
                      <div key={c.id} className="flex justify-between items-center bg-white dark:bg-zinc-900 p-2 rounded border border-slate-200 dark:border-zinc-800 text-xs shadow-sm">
                        <span className="font-bold truncate pr-2">{c.name}</span>
                        <button type="button" onClick={() => setContactForm({...contactForm, countries: contactForm.countries.filter(x => x.id !== c.id)})} className="text-slate-400 hover:text-red-500"><Trash2 size={14}/></button>
                      </div>
                    ))}
                    {contactForm.countries.length === 0 && <span className="text-xs text-slate-500 italic">No countries assigned.</span>}
                  </div>
                  <div className="flex gap-2">
                    <select className="flex-1 p-2 text-xs border border-slate-200 dark:border-zinc-700 rounded bg-white dark:bg-zinc-900 outline-none" value={newCountryId} onChange={e => setNewCountryId(e.target.value)}>
                      <option value="">Select Country to add...</option>
                      {countries.filter(c => !contactForm.countries.find(existing => existing.id === c.id)).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                    <button type="button" disabled={!newCountryId} onClick={() => {
                      const countryName = countries.find(c => c.id === newCountryId)?.name;
                      setContactForm({...contactForm, countries: [...contactForm.countries, { id: newCountryId, name: countryName }]});
                      setNewCountryId('');
                    }} className="bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold px-4 rounded disabled:opacity-50 transition-colors">Add</button>
                  </div>
                </div>
              )}

              {/* Developer -> Assets */}
              {contactForm.isDeveloper && (
                <div className="bg-indigo-50/50 dark:bg-indigo-950/10 p-4 rounded-xl border border-indigo-200 dark:border-indigo-900/30 animate-in fade-in">
                  <h4 className="font-bold text-sm flex items-center gap-2 mb-3 text-indigo-800 dark:text-indigo-500"><Server size={16}/> Developer Assets</h4>
                  <div className="space-y-2 mb-4 max-h-40 overflow-y-auto pr-2">
                    {contactForm.assets.map(a => (
                      <div key={a.id} className="flex justify-between items-center bg-white dark:bg-zinc-900 p-2 rounded border border-slate-200 dark:border-zinc-800 text-xs shadow-sm">
                        <span className="font-bold truncate pr-2">{a.name}</span>
                        <button type="button" onClick={() => setContactForm({...contactForm, assets: contactForm.assets.filter(x => x.id !== a.id)})} className="text-slate-400 hover:text-red-500"><Trash2 size={14}/></button>
                      </div>
                    ))}
                    {contactForm.assets.length === 0 && <span className="text-xs text-slate-500 italic">No assets assigned.</span>}
                  </div>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <select className="sm:w-1/3 p-2 text-xs border border-slate-200 dark:border-zinc-700 rounded bg-white dark:bg-zinc-900 outline-none" value={devCountryFilter} onChange={e => { setDevCountryFilter(e.target.value); setNewAssetId(''); }}>
                      <option value="">Filter by Country...</option>
                      {countries.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                    <select disabled={!devCountryFilter} className="flex-1 p-2 text-xs border border-slate-200 dark:border-zinc-700 rounded bg-white dark:bg-zinc-900 outline-none disabled:opacity-50" value={newAssetId} onChange={e => setNewAssetId(e.target.value)}>
                      <option value="">Select Asset from Pool...</option>
                      {poolAssets.filter(pa => pa.country_id === devCountryFilter && !contactForm.assets.find(existing => existing.id === pa.raw_asset_id)).map(pa => <option key={pa.raw_asset_id} value={pa.raw_asset_id}>{pa.name}</option>)}
                    </select>
                    <button type="button" disabled={!newAssetId} onClick={() => {
                      const assetName = poolAssets.find(pa => pa.raw_asset_id === newAssetId)?.name;
                      setContactForm({...contactForm, assets: [...contactForm.assets, { id: newAssetId, name: assetName }]});
                      setNewAssetId('');
                    }} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-4 py-2 sm:py-0 rounded disabled:opacity-50 transition-colors">Add</button>
                  </div>
                </div>
              )}

            </div>

            <div className="flex justify-end gap-3 pt-5 mt-5 border-t border-slate-100 dark:border-zinc-800">
              <button type="button" onClick={() => setShowForm(false)} className="px-5 py-2 text-sm font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg">Cancel</button>
              <button type="submit" className="px-5 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm">Save Complete Profile</button>
            </div>
          </form>
        )}

        {/* Contact List */}
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl shadow-sm overflow-hidden flex flex-col min-h-[500px]">
          <table className="hidden md:table w-full text-left text-sm">
            <thead className="bg-slate-50 dark:bg-zinc-900/50 border-b border-slate-200 dark:border-zinc-800">
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
                  <tr key={c.id} className="hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors">
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold shrink-0">
                          {c.full_name ? c.full_name.charAt(0).toUpperCase() : <Mail size={18}/>}
                        </div>
                        <div className="min-w-0">
                          <div className="font-bold text-base text-slate-900 dark:text-zinc-100 truncate">{c.full_name || 'No Name Provided'}</div>
                          <div className="text-slate-500 dark:text-zinc-500 text-sm truncate">{c.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="p-4">
                      <div className="flex flex-col gap-2">
                        {mappedCountries.length > 0 && (
                          <div className="flex gap-1.5 flex-wrap">
                            {mappedCountries.map((mc: any, idx: number) => (
                               <span key={`c-${idx}`} className="px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-[10px] font-bold text-amber-700 flex gap-1 items-center">
                                 <Shield size={10}/> {mc.country_name}
                               </span>
                            ))}
                          </div>
                        )}
                        {mappedAssets.length > 0 && (
                          <div className="flex gap-1.5 flex-wrap">
                            {mappedAssets.map((ma: any, idx: number) => (
                               <span key={`a-${idx}`} className="px-2 py-0.5 rounded-full bg-indigo-50 border border-indigo-200 text-[10px] font-bold text-indigo-700 flex gap-1 items-center">
                                 <Code size={10}/> {ma.asset_name}
                               </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="p-4 text-right">
                      <div className="flex justify-end gap-2">
                        {/* EDIT BUTTON LOGIC */}
                        <button onClick={() => {
                          const isStakeholder = mappedCountries.length > 0;
                          const isDeveloper = mappedAssets.length > 0;
                          setContactForm({
                            contact_id: c.id, email: c.email, full_name: c.full_name || '',
                            isStakeholder, isDeveloper,
                            countries: mappedCountries.map((m: any) => ({ id: m.country_id, name: m.country_name })),
                            assets: mappedAssets.map((m: any) => ({ id: m.raw_asset_id, name: m.asset_name }))
                          });
                          setDevCountryFilter('');
                          setNewCountryId('');
                          setNewAssetId('');
                          setShowForm(true);
                          window.scrollTo({ top: 0, behavior: 'smooth' });
                        }} className="text-slate-400 hover:text-blue-500 hover:bg-blue-50 p-2 rounded-lg transition-colors"><Edit2 size={18} /></button>

                        <button onClick={() => setDeleteModal({isOpen: true, id: c.id, email: c.email})} className="text-slate-400 hover:text-red-500 hover:bg-red-50 p-2 rounded-lg transition-colors">
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {/* MOBILE LIST */}
          <div className="md:hidden divide-y divide-slate-100 dark:divide-zinc-800">
            {paginatedContacts.map(c => {
               const mappedCountries = c.country_mappings || [];
               const mappedAssets = c.asset_mappings || [];

               return (
                <div key={c.id} className="p-4 flex flex-col gap-3">
                  <div className="flex justify-between items-start gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold shrink-0">
                        {c.full_name ? c.full_name.charAt(0).toUpperCase() : <Mail size={18}/>}
                      </div>
                      <div className="min-w-0">
                        <div className="font-bold text-base text-slate-900 dark:text-zinc-100 truncate">{c.full_name || 'No Name Provided'}</div>
                        <div className="text-slate-500 dark:text-zinc-500 text-sm truncate">{c.email}</div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => {
                          const isStakeholder = mappedCountries.length > 0;
                          const isDeveloper = mappedAssets.length > 0;
                          setContactForm({
                            contact_id: c.id, email: c.email, full_name: c.full_name || '',
                            isStakeholder, isDeveloper,
                            countries: mappedCountries.map((m: any) => ({ id: m.country_id, name: m.country_name })),
                            assets: mappedAssets.map((m: any) => ({ id: m.raw_asset_id, name: m.asset_name }))
                          });
                          setShowForm(true);
                          window.scrollTo({ top: 0, behavior: 'smooth' });
                      }} className="text-slate-400 hover:text-blue-500 bg-slate-100 p-2 rounded-lg"><Edit2 size={16} /></button>
                      <button onClick={() => setDeleteModal({isOpen: true, id: c.id, email: c.email})} className="text-red-500 bg-red-50 p-2 rounded-lg shrink-0">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="flex flex-col gap-1.5 bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                    <div className="flex gap-1.5 flex-wrap">
                      {mappedCountries.map((mc: any, idx: number) => (
                        <span key={`mc-${idx}`} className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 border border-amber-200 text-[9px] font-extrabold uppercase tracking-wider text-amber-700"><Shield size={10}/> {mc.country_name}</span>
                      ))}
                    </div>
                    <div className="flex gap-1.5 flex-wrap">
                      {mappedAssets.map((ma: any, idx: number) => (
                        <span key={`ma-${idx}`} className="flex items-center gap-1 px-2 py-0.5 rounded bg-indigo-50 border border-indigo-200 text-[9px] font-extrabold uppercase tracking-wider text-indigo-700"><Code size={10}/> {ma.asset_name}</span>
                      ))}
                    </div>
                  </div>
                </div>
               )
            })}
          </div>

          {filteredContacts.length === 0 && (
            <div className="flex-1 flex items-center justify-center text-slate-500 text-sm p-12">No contacts found matching your filters.</div>
          )}

          {filteredContacts.length > 0 && (
            <div className="px-4 py-3 border-t border-slate-200 dark:border-zinc-800 flex justify-between items-center bg-slate-50 dark:bg-zinc-950/50 mt-auto">
              <span className="text-xs md:text-sm text-slate-500 dark:text-zinc-400">Page {currentPage} of {totalPages}</span>
              <div className="flex gap-2">
                <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1} className="px-3 py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg disabled:opacity-50 hover:bg-white dark:hover:bg-zinc-800 transition-colors text-sm font-medium text-slate-700 dark:text-zinc-300"><ChevronLeft size={16}/></button>
                <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages} className="px-3 py-1.5 border border-slate-300 dark:border-zinc-700 rounded-lg disabled:opacity-50 hover:bg-white dark:hover:bg-zinc-800 transition-colors text-sm font-medium text-slate-700 dark:text-zinc-300"><ChevronRight size={16}/></button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}