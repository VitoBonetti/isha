import React, { useState, useEffect } from 'react';
import Xarrow, { Xwrapper } from 'react-xarrows';


export default function SnitcherDashboard() {
    const [allMetrics, setAllMetrics] = useState<any[]>([]);
    const [data, setData] = useState<any>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(function() {
        async function fetchMetrics() {
            try {
                const res = await fetch('/api/snitcher/');
                const metrics = await res.json();
                if (metrics && metrics.length !== 0) {
                    setAllMetrics(metrics);
                    setData(metrics[0]);
                }
            } catch (error) {
                console.error("Failed to fetch metrics", error);
            } finally {
                setIsLoading(false); // Turn off loading when the request completes
            }
        }
        
        fetchMetrics();
    }, []);

    function handlePeriodChange(e: any) {
        const selectedPeriod = e.target.value;
        const selectedData = allMetrics.find(function(m) { 
            return m.period === selectedPeriod; 
        });
        if (selectedData) {
            setData(selectedData);
        }
    }

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <div className="text-xl font-bold text-gray-500 animate-pulse">Loading Metrics...</div>
            </div>
        );
    }

    if (!data) {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50">
                <div className="bg-white p-10 rounded-xl shadow-md text-center max-w-lg border border-gray-200">
                    <h2 className="text-2xl font-bold text-gray-800 mb-2">No Metrics Available</h2>
                    <p className="text-gray-500">There is currently no weekly data in the database. Please trigger a sync to generate the dashboard.</p>
                </div>
            </div>
        );
    }

    const totalUnableToRetest = data.total_unable_to_retest;
    const totalNotFixedReopened = data.total_not_fixed_reopened;
    const totalClosed = data.total_closed;

    const gostWaiting = data.end_waiting_to_retest - data.devoteam_waiting_to_retest;
    const gostUnable = data.end_unable_to_retest - data.devoteam_unable_to_retest;

    return (
        <div className="min-h-screen bg-gray-50 p-8 font-sans overflow-x-hidden">
            
            <div className="flex justify-center items-center mb-12 space-x-4">
                <h1 className="text-3xl font-bold text-center">Actions of the Week:</h1>
                <select 
                    className="text-2xl font-bold bg-white border-2 border-gray-300 rounded-lg px-4 py-2 shadow-sm focus:outline-none focus:border-blue-500 cursor-pointer text-gray-700"
                    value={data.period} 
                    onChange={handlePeriodChange}
                >
                    {allMetrics.map(function(m) {
                        return (
                            <option key={m.id} value={m.period}>
                                {m.period}
                            </option>
                        );
                    })}
                </select>
            </div>

            <Xwrapper>
                <div className="grid grid-cols-12 gap-6">
                    
                    {/* LEFT COLUMN: Beginning of the Week */}
                    <div className="col-span-2 flex flex-col space-y-12 items-center relative">
                        <div className="bg-yellow-200 rounded-full px-6 py-4 font-bold text-center mb-4">
                            Beginning of<br/>the Week
                        </div>
                        
                        <div id="start-open" className="w-32 bg-gray-300 text-center p-4 rounded shadow-md z-10">
                            <div className="text-sm font-bold">Open</div>
                            <div className="text-2xl mt-2 bg-white/50 rounded">{data.start_new_open}</div>
                        </div>

                        {/* Grouped Waiting & Unable */}
                        <div id="start-group" className="border-2 border-dashed border-purple-300 p-4 rounded-xl flex flex-col space-y-6 w-40 items-center bg-purple-50/50 z-10">
                            <div id="start-waiting" className="w-32 bg-purple-400 text-white text-center p-4 rounded shadow-md">
                                <div className="text-sm font-bold">Waiting to Retest</div>
                                <div className="text-2xl mt-2 bg-white/30 rounded">{data.start_waiting_to_retest}</div>
                            </div>

                            <div id="start-unable" className="w-32 bg-purple-800 text-white text-center p-4 rounded shadow-md">
                                <div className="text-sm font-bold">Unable to Retest</div>
                                <div className="text-2xl mt-2 bg-white/30 rounded">{data.start_unable_to_retest}</div>
                            </div>
                        </div>

                        <div id="start-parked" className="w-32 bg-teal-600 text-white text-center p-4 rounded shadow-md z-10">
                            <div className="text-sm font-bold">Parked</div>
                            <div className="text-2xl mt-2 bg-white/30 rounded">{data.start_parked}</div>
                        </div>
                    </div>

                    {/* MIDDLE COLUMN: Left Actions, Matrix, Right Actions */}
                    <div className="col-span-8 flex flex-row items-stretch justify-between border-2 border-dashed border-gray-200 p-6 rounded-xl bg-white">
                        
                        {/* Intermediate Left Actions */}
                        <div className="flex flex-col justify-between w-36 z-10 py-4">
                             <div className="flex flex-col space-y-6">
                                 <div id="moved-parked" className="bg-teal-500 text-white p-2 rounded shadow text-center text-sm">
                                     Open → Parked<br/><span className="text-lg font-bold">{data.parked}</span>
                                 </div>
                                 <div id="moved-validating" className="bg-purple-500 text-white p-2 rounded shadow text-center text-sm">
                                     Open → Validating<br/><span className="text-lg font-bold">{data.solved}</span>
                                 </div>
                             </div>

                             <div className="flex flex-col space-y-12">
                                 <div id="unable-waiting" className="bg-purple-700 text-white p-2 rounded shadow text-center text-sm">
                                     Unable → Waiting<br/><span className="text-lg font-bold">{data.unable_to_waiting}</span>
                                 </div>
                                 <div id="parked-open" className="bg-teal-600 text-white p-2 rounded shadow text-center text-sm">
                                     Parked → Open<br/><span className="text-lg font-bold">{data.unparked}</span>
                                 </div>
                             </div>
                        </div>

                        {/* Central Matrix */}
                        <div id="central-matrix" className="flex-1 bg-gray-50 rounded-lg shadow-inner p-4 border border-gray-100 mx-6 z-10 self-center">
                            <table className="w-full text-center table-fixed">
                                <thead>
                                    <tr className="text-gray-500 font-medium">
                                        <th className="w-1/4"></th>
                                        <th>Andre</th><th>Emin</th><th>Francesco</th><th>Goncalo</th><th>Hugo</th>
                                        <th>Iuri</th><th>Rodrigo</th><th>Timothy</th><th>Vito</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr id="row-unable" className="bg-red-500 text-white font-bold h-12">
                                        <td className="text-left pl-4 text-black bg-transparent">Unable to Retest</td>
                                        <td>{data.am_utr}</td><td>{data.et_utr}</td><td>{data.fe_utr}</td>
                                        <td>{data.ga_utr}</td><td>{data.hp_utr}</td><td>{data.ipm_utr}</td>
                                        <td>{data.rm_utr}</td><td>{data.ttal_utr}</td><td>{data.vb_utr}</td>
                                    </tr>
                                    <tr id="row-notfixed" className="bg-orange-400 text-white font-bold h-12 mt-2 border-t-4 border-gray-50">
                                        <td className="text-left pl-4 text-black bg-transparent">Not fixed</td>
                                        <td>{data.am_nf}</td><td>{data.et_nf}</td><td>{data.fe_nf}</td>
                                        <td>{data.ga_nf}</td><td>{data.hp_nf}</td><td>{data.ipm_nf}</td>
                                        <td>{data.rm_nf}</td><td>{data.ttal_nf}</td><td>{data.vb_nf}</td>
                                    </tr>
                                    <tr id="row-closed" className="bg-green-600 text-white font-bold h-12 mt-2 border-t-4 border-gray-50">
                                        <td className="text-left pl-4 text-black bg-transparent">Closed</td>
                                        <td>{data.am_c}</td><td>{data.et_c}</td><td>{data.fe_c}</td>
                                        <td>{data.ga_c}</td><td>{data.hp_c}</td><td>{data.ipm_c}</td>
                                        <td>{data.rm_c}</td><td>{data.ttal_c}</td><td>{data.vb_c}</td>
                                    </tr>
                                </tbody>
                                <tfoot>
                                    <tr className="bg-gray-300 font-bold h-10 border-t-8 border-gray-50">
                                        <td className="text-left pl-4 text-black bg-transparent">Total</td>
                                        <td className="text-gray-700">{(data.am_utr || 0) + (data.am_nf || 0) + (data.am_c || 0)}</td>
                                        <td className="text-gray-700">{(data.et_utr || 0) + (data.et_nf || 0) + (data.et_c || 0)}</td>
                                        <td className="text-gray-700">{(data.fe_utr || 0) + (data.fe_nf || 0) + (data.fe_c || 0)}</td>
                                        <td className="text-gray-700">{(data.ga_utr || 0) + (data.ga_nf || 0) + (data.ga_c || 0)}</td>
                                        <td className="text-gray-700">{(data.hp_utr || 0) + (data.hp_nf || 0) + (data.hp_c || 0)}</td>
                                        <td className="text-gray-700">{(data.ipm_utr || 0) + (data.ipm_nf || 0) + (data.ipm_c || 0)}</td>
                                        <td className="text-gray-700">{(data.rm_utr || 0) + (data.rm_nf || 0) + (data.rm_c || 0)}</td>
                                        <td className="text-gray-700">{(data.ttal_utr || 0) + (data.ttal_nf || 0) + (data.ttal_c || 0)}</td>
                                        <td className="text-gray-700">{(data.vb_utr || 0) + (data.vb_nf || 0) + (data.vb_c || 0)}</td>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>

                        {/* Intermediate Right Actions */}
                        <div className="flex flex-col w-32 z-10 mt-6 space-y-16">
                             <div id="new-finding" className="bg-blue-400 text-white text-center p-3 rounded shadow">
                                 <div className="text-xs">New Finding</div>
                                 <div className="text-xl font-bold">{data.newly_added}</div>
                             </div>
                             
                             {/* Grouped Bottom Actions */}
                             <div className="flex flex-col space-y-4">
                                 <div id="action-unable" className="bg-red-600 text-white text-center p-3 rounded shadow">
                                     <div className="text-xs">Unable to Retest</div>
                                     <div className="text-xl font-bold">{totalUnableToRetest}</div>
                                 </div>
                                 <div id="reopened" className="bg-orange-500 text-white text-center p-3 rounded shadow">
                                     <div className="text-xs">Reopened</div>
                                     <div className="text-xl font-bold">{totalNotFixedReopened}</div>
                                 </div>
                                 <div id="end-closed" className="bg-green-600 text-white text-center p-3 rounded shadow">
                                     <div className="text-xs font-bold">Closed</div>
                                     <div className="text-xl font-bold">{totalClosed}</div>
                                 </div>
                             </div>
                        </div>

                    </div>

                    {/* RIGHT COLUMN: End of the Week */}
                    <div className="col-span-2 flex flex-col space-y-12 items-center relative">
                        <div className="bg-yellow-200 rounded-full px-6 py-4 font-bold text-center mb-4">
                            End of the<br/>Week
                        </div>

                        <div id="end-open" className="w-32 bg-gray-400 text-center p-4 rounded shadow-md z-10">
                            <div className="text-sm font-bold text-white">Open</div>
                            <div className="text-3xl text-white mt-2 font-bold">{data.end_new_open}</div>
                        </div>

                        {/* Grouped End Unable & Waiting */}
                        <div id="end-group" className="border-2 border-dashed border-purple-300 p-4 rounded-xl flex flex-col space-y-6 w-56 items-center bg-purple-50/50 z-10">
                            <div id="end-unable" className="w-48 bg-purple-100 border border-purple-300 p-2 rounded shadow-md flex items-center">
                                 <div className="bg-purple-800 text-white text-center p-2 rounded w-1/2">
                                     <div className="text-xs">Unable</div>
                                     <div className="text-2xl font-bold">{data.end_unable_to_retest}</div>
                                 </div>
                                 <div className="w-1/2 text-xs font-bold pl-2">
                                     <div className="bg-purple-600 text-white rounded mb-1 px-1">GOST: {gostUnable}</div>
                                     <div className="bg-purple-900 text-white rounded px-1">DEVO: {data.devoteam_unable_to_retest}</div>
                                 </div>
                            </div>

                            <div id="end-waiting" className="w-48 bg-purple-100 border border-purple-300 p-2 rounded shadow-md flex items-center">
                                 <div className="bg-purple-500 text-white text-center p-2 rounded w-1/2">
                                     <div className="text-xs">Waiting</div>
                                     <div className="text-2xl font-bold">{data.end_waiting_to_retest}</div>
                                 </div>
                                 <div className="w-1/2 text-xs font-bold pl-2">
                                     <div className="bg-purple-400 text-white rounded mb-1 px-1">GOST: {gostWaiting}</div>
                                     <div className="bg-purple-700 text-white rounded px-1">DEVO: {data.devoteam_waiting_to_retest}</div>
                                 </div>
                            </div>
                        </div>

                        <div id="end-parked" className="w-32 bg-teal-500 text-white text-center p-4 rounded shadow-md z-10">
                            <div className="text-sm font-bold">Parked</div>
                            <div className="text-3xl mt-2 font-bold">{data.end_parked}</div>
                        </div>
                    </div>
                </div>

                {/* DRAWING THE ARROWS - LEFT SIDE */}
                <Xarrow start="start-open" end="moved-parked" color="#14b8a6" strokeWidth={2} path="smooth" />
                <Xarrow start="start-open" end="moved-validating" color="#a855f7" strokeWidth={2} path="smooth" />
                <Xarrow start="start-group" end="central-matrix" color="#9333ea" strokeWidth={2} path="smooth" />
                <Xarrow start="start-unable" end="unable-waiting" color="#7e22ce" strokeWidth={2} path="smooth" />
                <Xarrow start="start-parked" end="parked-open" color="#0f766e" strokeWidth={2} path="smooth" />

                {/* DRAWING THE ARROWS - RIGHT SIDE (Rows to Action Cards - added zIndex 20) */}
                <Xarrow start="row-unable" end="action-unable" color="#dc2626" strokeWidth={2} path="smooth" zIndex={20} />
                <Xarrow start="row-notfixed" end="reopened" color="#f97316" strokeWidth={2} path="smooth" zIndex={20} />
                <Xarrow start="row-closed" end="end-closed" color="#16a34a" strokeWidth={2} path="smooth" zIndex={20} />

                {/* DRAWING THE ARROWS - ACTION CARDS TO END */}
                <Xarrow start="new-finding" end="end-open" color="#3b82f6" strokeWidth={2} path="smooth" />
                <Xarrow start="action-unable" end="end-unable" color="#dc2626" strokeWidth={2} path="smooth" />
                <Xarrow start="reopened" end="end-open" color="#f97316" strokeWidth={2} path="smooth" />

            </Xwrapper>
        </div>
    );
}