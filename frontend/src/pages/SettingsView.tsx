import { useState } from 'react';
import { useSettings } from '../hooks/useSettings';
import TopNav from '../components/TopNav';
import { Toaster } from 'react-hot-toast';
import { Users, MapPin, Activity, Tags, Globe, Flag, Server, Trash2, Download, AlertTriangle, Plus, Database, Terminal, Edit2 } from 'lucide-react';

export default function SettingsView() {
  const {
    activeTab, setActiveTab,
    users, locations, services, categories, regions, countries, logs, isLoading,
    handleSave, handleDelete, downloadLog, handleWipeSystem
  } = useSettings();

  const [showForm, setShowForm] = useState<string | null>(null);

  const defaultUserForm = { email: '', name: '', role: 'read_only', base_capacity: 1.0, location_id: '', start_week: 1, start_year: new Date().getFullYear(), end_week: '', end_year: '' };
  const [userForm, setUserForm] = useState(defaultUserForm);
  const [editUserId, setEditUserId] = useState<string | null>(null);

  const [locForm, setLocForm] = useState({ name: '', is_active: true });
  const [serviceForm, setServiceForm] = useState({ name: '', theme_color: '#3b82f6', default_credits: 2.0, default_duration_weeks: 1, max_concurrent_per_week: 5, match_keywords: '', display_order: 99, is_active: true });
  const [catForm, setCatForm] = useState({ name: '', target_goal: 0, service_lane_id: '' });
  const [regionForm, setRegionForm] = useState({ name: '', is_active: true });
  const [countryForm, setCountryForm] = useState({ code: '', name: '', region_id: '', is_active: true });

  const submitUser = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      ...userForm,
      location_id: userForm.location_id === '' ? null : userForm.location_id,
      end_week: userForm.end_week === '' ? null : parseInt(userForm.end_week as string),
      end_year: userForm.end_year === '' ? null : parseInt(userForm.end_year as string)
    };
    if (await handleSave('/api/users/', payload, !!editUserId, editUserId)) {
      setShowForm(null);
      setEditUserId(null);
      setUserForm(defaultUserForm);
    }
  };

  const submitLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await handleSave('/api/locations/', locForm, false)) setShowForm(null);
  };

  const submitService = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = { ...serviceForm, match_keywords: serviceForm.match_keywords.split(',').map(s => s.trim()) };
    if (await handleSave('/api/services/', payload, false)) setShowForm(null);
  };

  const submitCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = { ...catForm, service_lane_id: catForm.service_lane_id === '' ? null : catForm.service_lane_id };
    if (await handleSave('/api/board/categories/', payload, false)) setShowForm(null);
  };

  const submitRegion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await handleSave('/api/regions/', regionForm, false)) setShowForm(null);
  };

  const submitCountry = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = { ...countryForm, region_id: countryForm.region_id === '' ? null : countryForm.region_id };
    if (await handleSave('/api/countries/', payload, false)) setShowForm(null);
  };

  if (isLoading) return <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-500">Loading settings...</div>;

  const renderSimpleList = (title: string, desc: string, data: any[], endpoint: string, formType: string) => (
    <div className="fade-in">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold">{title}</h2>
          <p className="text-sm text-slate-500">{desc}</p>
        </div>
        <button onClick={() => setShowForm(formType)} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors">
          <Plus size={16} /> Add {title.split(' ')[0]}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {data?.map((item: any) => (
          <div key={item.id} className="border border-slate-200 p-5 rounded-2xl flex justify-between items-start hover:border-blue-500 transition-colors bg-white shadow-sm hover:shadow-md">
            <div>
              <div className="font-bold text-lg flex items-center gap-2">
                {item.theme_color && <div className="w-4 h-4 rounded-full shadow-sm" style={{backgroundColor: item.theme_color}}></div>}
                {item.name || item.code || item.regions}
              </div>

              <div className="mt-2 space-y-1">
                {item.region_name && <div className="text-sm text-slate-500 font-medium">Region: <span className="text-slate-900">{item.region_name}</span></div>}
                {item.target_goal !== undefined && <div className="text-sm text-slate-500 font-medium">Target Goal: <span className="text-slate-900">{item.target_goal}</span></div>}
                {item.default_credits !== undefined && <div className="text-sm text-slate-500 font-medium">Credits: <span className="text-slate-900">{item.default_credits}cr</span> / Duration: <span className="text-slate-900">{item.default_duration_weeks}w</span></div>}
              </div>

              <div className="mt-4 px-2.5 py-1 rounded-full bg-emerald-100 border border-emerald-200 text-emerald-800 text-[10px] font-extrabold uppercase tracking-wider w-fit shadow-sm">
                {item.is_active !== false ? 'Active' : 'Inactive'}
              </div>
            </div>
            <button onClick={() => handleDelete(endpoint, item.id)} className="text-slate-400 hover:text-red-500 hover:bg-red-50 p-2 rounded-lg transition-colors">
              <Trash2 size={18} />
            </button>
          </div>
        ))}
        {(!data || data.length === 0) && (
          <div className="col-span-full p-12 text-center text-slate-500 border-2 border-dashed border-slate-200 rounded-2xl bg-slate-50/50">
            No records found. Click the button above to add one.
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
      <TopNav />
      <Toaster position="bottom-right" />

      <main className="flex-1 pt-32 pb-12 px-6 max-w-7xl mx-auto w-full flex flex-col md:flex-row gap-8">
        <aside className="w-full md:w-64 shrink-0">
          <div className="bg-white border border-slate-200 rounded-2xl p-3 shadow-sm sticky top-32">
            <h3 className="text-xs font-bold uppercase text-slate-400 mb-3 px-3">Platform Settings</h3>
            <nav className="flex flex-col gap-1">
              <button onClick={() => { setActiveTab('users'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'users' ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100'}`}><Users size={18} /> Users</button>
              <button onClick={() => { setActiveTab('locations'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'locations' ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100'}`}><MapPin size={18} /> Locations</button>
              <button onClick={() => { setActiveTab('services'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'services' ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100'}`}><Activity size={18} /> Services</button>
              <button onClick={() => { setActiveTab('categories'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'categories' ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100'}`}><Tags size={18} /> Categories</button>
              <button onClick={() => { setActiveTab('regions'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'regions' ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100'}`}><Globe size={18} /> Regions</button>
              <button onClick={() => { setActiveTab('countries'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'countries' ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100'}`}><Flag size={18} /> Countries</button>
              <button onClick={() => { setActiveTab('system'); setShowForm(null); }} className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${activeTab === 'system' ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100'}`}><Server size={18} /> System Logs</button>
            </nav>
          </div>
        </aside>

        <section className="flex-1 bg-white border border-slate-200 rounded-2xl p-8 shadow-sm min-h-[600px]">

          {/* USERS */}
          {activeTab === 'users' && (
            <div className="fade-in">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h2 className="text-xl font-bold">User Management</h2>
                  <p className="text-sm text-slate-500">Manage access roles, capacities, and active intervals.</p>
                </div>
                <button onClick={() => { setEditUserId(null); setUserForm(defaultUserForm); setShowForm('users'); }} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
                  <Plus size={16} /> Add User
                </button>
              </div>

              {showForm === 'users' && (
                <form onSubmit={submitUser} className="bg-slate-50 p-6 rounded-2xl border border-slate-200 mb-8 space-y-4 shadow-inner">
                  <h3 className="font-bold text-lg mb-2">{editUserId ? 'Edit User' : 'Create New User'}</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <label className="text-sm font-bold text-slate-700">Name <input className="w-full mt-1 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={userForm.name} onChange={e => setUserForm({...userForm, name: e.target.value})} required /></label>
                    <label className="text-sm font-bold text-slate-700">Email <input type="email" disabled={!!editUserId} className="w-full mt-1 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none disabled:opacity-50" value={userForm.email} onChange={e => setUserForm({...userForm, email: e.target.value})} required /></label>

                    <label className="text-sm font-bold text-slate-700">Role
                      <select className="w-full mt-1 p-2.5 border rounded-lg bg-white focus:ring-2 focus:ring-blue-500 outline-none" value={userForm.role} onChange={e => setUserForm({...userForm, role: e.target.value})}>
                        <option value="read_only">Read Only</option>
                        <option value="pentester">Pentester</option>
                        <option value="admin">Admin</option>
                      </select>
                    </label>

                    <label className="text-sm font-bold text-slate-700">Location
                      <select className="w-full mt-1 p-2.5 border rounded-lg bg-white focus:ring-2 focus:ring-blue-500 outline-none" value={userForm.location_id} onChange={e => setUserForm({...userForm, location_id: e.target.value})} required>
                        <option value="">-- Select Location --</option>
                        {locations?.map(loc => <option key={loc.id} value={loc.id}>{loc.name}</option>)}
                      </select>
                    </label>

                    <label className="text-sm font-bold text-slate-700">Capacity <input type="number" step="0.1" className="w-full mt-1 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={userForm.base_capacity} onChange={e => setUserForm({...userForm, base_capacity: parseFloat(e.target.value)})} required /></label>

                    <div className="flex gap-4">
                      <label className="text-sm font-bold text-slate-700 w-1/2">Start Year <input type="number" className="w-full mt-1 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={userForm.start_year} onChange={e => setUserForm({...userForm, start_year: parseInt(e.target.value)})} required /></label>
                      <label className="text-sm font-bold text-slate-700 w-1/2">Start Wk <input type="number" className="w-full mt-1 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={userForm.start_week} onChange={e => setUserForm({...userForm, start_week: parseInt(e.target.value)})} required /></label>
                    </div>

                    <div className="flex gap-4 col-span-1 md:col-span-2 bg-red-50/50 p-4 rounded-xl border border-red-100">
                      <label className="text-sm font-bold w-1/2 text-red-800">Offboard Year (Optional) <input type="number" className="w-full mt-1 p-2.5 border border-red-200 rounded-lg focus:ring-2 focus:ring-red-500 outline-none" value={userForm.end_year} onChange={e => setUserForm({...userForm, end_year: e.target.value})} placeholder="Leave blank if active"/></label>
                      <label className="text-sm font-bold w-1/2 text-red-800">Offboard Wk (Optional) <input type="number" className="w-full mt-1 p-2.5 border border-red-200 rounded-lg focus:ring-2 focus:ring-red-500 outline-none" value={userForm.end_week} onChange={e => setUserForm({...userForm, end_week: e.target.value})} placeholder="Leave blank if active"/></label>
                    </div>
                  </div>
                  <div className="flex justify-end gap-3 pt-4 border-t border-slate-200">
                    <button type="button" onClick={() => {setShowForm(null); setEditUserId(null);}} className="px-5 py-2.5 text-sm font-medium bg-slate-200 hover:bg-slate-300 rounded-lg transition-colors">Cancel</button>
                    <button type="submit" className="px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm transition-colors">{editUserId ? 'Update User' : 'Save User'}</button>
                  </div>
                </form>
              )}

              <div className="border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="p-4 font-bold text-slate-600">User Details</th>
                      <th className="p-4 font-bold text-slate-600">Role</th>
                      <th className="p-4 font-bold text-slate-600">Capacity</th>
                      <th className="p-4 font-bold text-slate-600 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {users?.map(u => (
                      <tr key={u.id} className="hover:bg-slate-50 transition-colors">
                        <td className="p-4">
                          <div className="flex items-center gap-3">
                            {u.avatar_url ? (
                              <img src={u.avatar_url} alt={u.name} className="w-9 h-9 rounded-full border border-slate-200" />
                            ) : (
                              <div className="w-9 h-9 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center font-bold">
                                {u.name.charAt(0)}
                              </div>
                            )}
                            <div>
                              <div className="font-bold text-base text-slate-900">{u.name}</div>
                              <div className="text-slate-500 mt-0.5">{u.email}</div>
                            </div>
                          </div>
                        </td>
                        <td className="p-4">
                          <span className="px-2.5 py-1 rounded-full bg-slate-100 border border-slate-200 text-[11px] font-extrabold uppercase tracking-wider text-slate-700">
                            {u.role.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="p-4 font-medium text-slate-700">{u.base_capacity} cr/wk</td>
                        <td className="p-4 text-right">
                          <div className="flex justify-end gap-2">
                            <button onClick={() => {
                              setEditUserId(u.id);
                              setUserForm({
                                email: u.email, name: u.name, role: u.role, base_capacity: u.base_capacity,
                                location_id: u.location_id || '', start_week: u.start_week || 1, start_year: u.start_year || new Date().getFullYear(),
                                end_week: u.end_week || '', end_year: u.end_year || ''
                              });
                              setShowForm('users');
                            }} className="text-slate-400 hover:text-blue-500 hover:bg-blue-50 p-2 rounded-lg transition-colors">
                              <Edit2 size={18} />
                            </button>
                            <button onClick={() => handleDelete('/api/users/', u.id)} className="text-slate-400 hover:text-red-500 hover:bg-red-50 p-2 rounded-lg transition-colors">
                              <Trash2 size={18} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(!users || users.length === 0) && <div className="p-12 text-center text-slate-500 bg-slate-50/50">No users found.</div>}
              </div>
            </div>
          )}

          {/* LOCATIONS */}
          {activeTab === 'locations' && (
            <div>
              {renderSimpleList('Locations', 'Geographic bases for calculating national holidays.', locations, '/api/locations/', 'locations')}
              {showForm === 'locations' && (
                <form onSubmit={submitLocation} className="bg-slate-50 p-6 rounded-2xl border border-slate-200 my-6 shadow-inner">
                  <h3 className="font-bold text-lg mb-4">Add Location</h3>
                  <label className="text-sm font-bold text-slate-700 block mb-6">Location Name <input className="w-full mt-2 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={locForm.name} onChange={e => setLocForm({...locForm, name: e.target.value})} required placeholder="e.g. London" /></label>
                  <div className="flex justify-end gap-3 border-t border-slate-200 pt-4"><button type="button" onClick={() => setShowForm(null)} className="px-5 py-2.5 text-sm font-medium bg-slate-200 hover:bg-slate-300 rounded-lg">Cancel</button><button type="submit" className="px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm">Save</button></div>
                </form>
              )}
            </div>
          )}

          {/* SERVICES */}
          {activeTab === 'services' && (
            <div>
              {renderSimpleList('Dynamic Service Lanes', 'Define distinct testing lanes, default credits, and visual themes.', services, '/api/services/', 'services')}
              {showForm === 'services' && (
                <form onSubmit={submitService} className="bg-slate-50 p-6 rounded-2xl border border-slate-200 my-6 space-y-4 shadow-inner">
                  <h3 className="font-bold text-lg mb-2">Add Service Lane</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <label className="text-sm font-bold text-slate-700">Name <input className="w-full mt-1 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={serviceForm.name} onChange={e => setServiceForm({...serviceForm, name: e.target.value})} required /></label>
                    <label className="text-sm font-bold text-slate-700">Theme Color <input type="color" className="w-full mt-1 h-11 border-none rounded-lg cursor-pointer bg-white" value={serviceForm.theme_color} onChange={e => setServiceForm({...serviceForm, theme_color: e.target.value})} required /></label>
                    <label className="text-sm font-bold text-slate-700">Default Credits <input type="number" step="0.1" className="w-full mt-1 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={serviceForm.default_credits} onChange={e => setServiceForm({...serviceForm, default_credits: parseFloat(e.target.value)})} required /></label>
                    <label className="text-sm font-bold text-slate-700">Default Duration (Wks) <input type="number" className="w-full mt-1 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={serviceForm.default_duration_weeks} onChange={e => setServiceForm({...serviceForm, default_duration_weeks: parseInt(e.target.value)})} required /></label>
                    <label className="text-sm font-bold text-slate-700 col-span-1 md:col-span-2">Match Keywords (comma separated) <input className="w-full mt-1 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={serviceForm.match_keywords} onChange={e => setServiceForm({...serviceForm, match_keywords: e.target.value})} placeholder="e.g. web, dast, external" /></label>
                  </div>
                  <div className="flex justify-end gap-3 pt-4 border-t border-slate-200"><button type="button" onClick={() => setShowForm(null)} className="px-5 py-2.5 text-sm font-medium bg-slate-200 hover:bg-slate-300 rounded-lg">Cancel</button><button type="submit" className="px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm">Save</button></div>
                </form>
              )}
            </div>
          )}

          {/* CATEGORIES */}
          {activeTab === 'categories' && (
            <div>
              {renderSimpleList('Service Forecasts', 'Specific target goals mapped to service lanes.', categories, '/api/board/categories/', 'categories')}
              {showForm === 'categories' && (
                <form onSubmit={submitCategory} className="bg-slate-50 p-6 rounded-2xl border border-slate-200 my-6 space-y-4 shadow-inner">
                  <h3 className="font-bold text-lg mb-2">Add Category</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <label className="text-sm font-bold text-slate-700 col-span-1 md:col-span-2">Name <input className="w-full mt-1 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={catForm.name} onChange={e => setCatForm({...catForm, name: e.target.value})} required /></label>
                    <label className="text-sm font-bold text-slate-700">Target Goal <input type="number" className="w-full mt-1 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={catForm.target_goal} onChange={e => setCatForm({...catForm, target_goal: parseInt(e.target.value)})} required /></label>
                    <label className="text-sm font-bold text-slate-700">Link to Service Lane
                      <select className="w-full mt-1 p-2.5 border rounded-lg bg-white focus:ring-2 focus:ring-blue-500 outline-none" value={catForm.service_lane_id} onChange={e => setCatForm({...catForm, service_lane_id: e.target.value})}>
                        <option value="">-- None --</option>
                        {services?.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                      </select>
                    </label>
                  </div>
                  <div className="flex justify-end gap-3 pt-4 border-t border-slate-200"><button type="button" onClick={() => setShowForm(null)} className="px-5 py-2.5 text-sm font-medium bg-slate-200 hover:bg-slate-300 rounded-lg">Cancel</button><button type="submit" className="px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm">Save</button></div>
                </form>
              )}
            </div>
          )}

          {/* REGIONS */}
          {activeTab === 'regions' && (
            <div>
              {renderSimpleList('Regions', 'Broad operational boundaries.', regions, '/api/regions/', 'regions')}
              {showForm === 'regions' && (
                <form onSubmit={submitRegion} className="bg-slate-50 p-6 rounded-2xl border border-slate-200 my-6 shadow-inner">
                  <h3 className="font-bold text-lg mb-4">Add Region</h3>
                  <label className="text-sm font-bold text-slate-700 block mb-6">Region Name <input className="w-full mt-2 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={regionForm.name} onChange={e => setRegionForm({...regionForm, name: e.target.value})} required /></label>
                  <div className="flex justify-end gap-3 border-t border-slate-200 pt-4"><button type="button" onClick={() => setShowForm(null)} className="px-5 py-2.5 text-sm font-medium bg-slate-200 hover:bg-slate-300 rounded-lg">Cancel</button><button type="submit" className="px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm">Save</button></div>
                </form>
              )}
            </div>
          )}

          {/* COUNTRIES */}
          {activeTab === 'countries' && (
            <div>
              {renderSimpleList('Countries', 'Manage operating countries and analytics mappings.', countries, '/api/countries/', 'countries')}
              {showForm === 'countries' && (
                <form onSubmit={submitCountry} className="bg-slate-50 p-6 rounded-2xl border border-slate-200 my-6 space-y-4 shadow-inner">
                  <h3 className="font-bold text-lg mb-2">Add Country</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <label className="text-sm font-bold text-slate-700">Code (e.g. US) <input className="w-full mt-1 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={countryForm.code} onChange={e => setCountryForm({...countryForm, code: e.target.value.toUpperCase()})} required /></label>
                    <label className="text-sm font-bold text-slate-700">Name <input className="w-full mt-1 p-2.5 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" value={countryForm.name} onChange={e => setCountryForm({...countryForm, name: e.target.value})} required /></label>
                    <label className="text-sm font-bold text-slate-700 col-span-1 md:col-span-2">Region
                      <select className="w-full mt-1 p-2.5 border rounded-lg bg-white focus:ring-2 focus:ring-blue-500 outline-none" value={countryForm.region_id} onChange={e => setCountryForm({...countryForm, region_id: e.target.value})}>
                        <option value="">-- None --</option>
                        {regions?.map(r => <option key={r.id} value={r.id}>{r.name || r.regions}</option>)}
                      </select>
                    </label>
                  </div>
                  <div className="flex justify-end gap-3 pt-4 border-t border-slate-200"><button type="button" onClick={() => setShowForm(null)} className="px-5 py-2.5 text-sm font-medium bg-slate-200 hover:bg-slate-300 rounded-lg">Cancel</button><button type="submit" className="px-5 py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-sm">Save</button></div>
                </form>
              )}
            </div>
          )}

          {/* SYSTEM */}
          {activeTab === 'system' && (
            <div className="space-y-8 fade-in">
              <div>
                <h2 className="text-xl font-bold mb-4 flex items-center gap-2"><Database size={20} className="text-blue-500"/> Infrastructure Logic</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="border border-slate-200 rounded-2xl p-5 flex justify-between items-center bg-slate-50 shadow-sm">
                    <span className="font-bold text-slate-700">PostgreSQL Primary</span>
                    <span className="flex items-center gap-2 text-sm text-emerald-700 font-extrabold uppercase tracking-wider bg-emerald-100 px-3 py-1.5 rounded-full"><div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div> Connected</span>
                  </div>
                </div>
              </div>

              <div>
                <h2 className="text-xl font-bold mb-4 flex items-center gap-2"><Terminal size={20} className="text-slate-500"/> Security Audit Logs</h2>
                <div className="border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                  {(!logs || logs?.length === 0) ? <div className="p-12 text-center text-slate-500 bg-slate-50/50">No text logs generated yet in the backend /logs folder.</div> :
                    <ul className="divide-y divide-slate-100">
                      {logs.map(log => (
                        <li key={log} className="p-4 flex justify-between items-center hover:bg-slate-50 transition-colors">
                          <span className="font-mono text-sm font-medium text-slate-700">{log}</span>
                          <button onClick={() => downloadLog(log)} className="text-blue-600 hover:bg-blue-50 hover:text-blue-700 px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-bold transition-colors"><Download size={16} /> Download</button>
                        </li>
                      ))}
                    </ul>
                  }
                </div>
              </div>
              <div className="pt-6 border-t border-slate-200">
                <h2 className="text-xl font-bold text-red-600 mb-2 flex items-center gap-2"><AlertTriangle size={20} /> Danger Zone</h2>
                <button onClick={handleWipeSystem} className="bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-8 rounded-xl shadow-sm mt-4 transition-colors focus:ring-4 focus:ring-red-500/20">Execute Factory Reset</button>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}