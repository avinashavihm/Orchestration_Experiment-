import React, { useState } from 'react';
import axios from 'axios';
import { Upload, FileText, Activity, ArrowRight, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

function App() {
    const [files, setFiles] = useState([]);
    const [status, setStatus] = useState('idle'); // idle, analyzing, success, error
    const [result, setResult] = useState(null);
    const [plannerSummary, setPlannerSummary] = useState(null);
    const [combinedAnalysis, setCombinedAnalysis] = useState(null);
    const [error, setError] = useState(null);

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files.length > 0) {
            setFiles(Array.from(e.target.files));
            setStatus('idle');
            setResult(null);
            setPlannerSummary(null);
            setError(null);
        }
    };

    const handleUpload = async () => {
        if (files.length === 0) return;

        setStatus('analyzing');
        const formData = new FormData();
        files.forEach(file => {
            formData.append('files', file);
        });

        try {
            const response = await axios.post('http://localhost:8002/analyze', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });

            setResult(response.data.analysis_results);
            setPlannerSummary(response.data.planner_summary);
            setCombinedAnalysis(response.data.combined_analysis);
            setStatus('success');
        } catch (err) {
            console.error(err);
            setError(err.response?.data?.detail || 'An error occurred during analysis');
            setStatus('error');
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
            {/* Header */}
            <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
                <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white">
                            <Activity size={20} />
                        </div>
                        <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 to-violet-600">
                            Clinical Operations Planner
                        </h1>
                    </div>
                    <div className="text-sm text-slate-500">
                        Orchestrator Agent
                    </div>
                </div>
            </header>

            <main className="max-w-5xl mx-auto px-6 py-12">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                    {/* Left Panel: Upload */}
                    <div className="lg:col-span-1 space-y-6">
                        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
                            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                                <Upload size={20} className="text-indigo-600" />
                                Upload Data
                            </h2>

                            <div className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center hover:border-indigo-400 transition-colors cursor-pointer relative">
                                <input
                                    type="file"
                                    multiple
                                    onChange={handleFileChange}
                                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                />
                                <div className="flex flex-col items-center gap-3 pointer-events-none">
                                    <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center">
                                        <FileText size={24} />
                                    </div>
                                    <div className="text-sm font-medium text-slate-700">
                                        {files.length > 0 ? `${files.length} files selected` : "Drop files or click to upload"}
                                    </div>
                                    <div className="text-xs text-slate-400">
                                        PDF, XLSX, CSV supported (any number of files)
                                    </div>
                                </div>
                            </div>

                            {files.length > 0 && (
                                <div className="mt-4 space-y-2">
                                    {files.map((f, i) => (
                                        <div key={i} className="text-xs text-slate-600 flex items-center gap-2">
                                            <FileText size={12} /> {f.name}
                                        </div>
                                    ))}
                                </div>
                            )}

                            <button
                                onClick={handleUpload}
                                disabled={files.length === 0 || status === 'analyzing'}
                                className={`w-full mt-4 py-2.5 px-4 rounded-lg font-medium text-white transition-all ${files.length === 0 || status === 'analyzing'
                                    ? 'bg-slate-300 cursor-not-allowed'
                                    : 'bg-indigo-600 hover:bg-indigo-700 shadow-md hover:shadow-lg'
                                    }`}
                            >
                                {status === 'analyzing' ? (
                                    <span className="flex items-center justify-center gap-2">
                                        <Loader2 size={18} className="animate-spin" />
                                        Analyzing...
                                    </span>
                                ) : (
                                    'Start Analysis'
                                )}
                            </button>
                        </div>

                        {/* Status Card */}
                        {status !== 'idle' && (
                            <div className={`rounded-xl p-4 border ${status === 'error' ? 'bg-red-50 border-red-100 text-red-700' :
                                status === 'success' ? 'bg-emerald-50 border-emerald-100 text-emerald-700' :
                                    'bg-blue-50 border-blue-100 text-blue-700'
                                }`}>
                                <div className="flex items-start gap-3">
                                    {status === 'analyzing' && <Loader2 className="animate-spin mt-0.5" size={18} />}
                                    {status === 'success' && <CheckCircle className="mt-0.5" size={18} />}
                                    {status === 'error' && <AlertCircle className="mt-0.5" size={18} />}

                                    <div>
                                        <div className="font-medium">
                                            {status === 'analyzing' && 'Planner is analyzing files...'}
                                            {status === 'success' && 'Analysis Complete'}
                                            {status === 'error' && 'Analysis Failed'}
                                        </div>
                                        <div className="text-sm opacity-90 mt-1">
                                            {status === 'analyzing' && 'Checking file completeness and routing to agents...'}
                                            {status === 'success' && (
                                                <div className="space-y-2 mt-2">
                                                    {plannerSummary?.recruitment?.can_analyze ? (
                                                        <div className="flex items-center gap-2">
                                                            <CheckCircle size={14} />
                                                            <span>Recruitment: {plannerSummary.recruitment.matched_files?.length || 0} files ready</span>
                                                        </div>
                                                    ) : (
                                                        <div className="flex items-center gap-2">
                                                            <AlertCircle size={14} />
                                                            <span>Recruitment: Missing {plannerSummary?.recruitment?.missing_files?.length || 0} files</span>
                                                        </div>
                                                    )}
                                                    {plannerSummary?.supply?.can_analyze ? (
                                                        <div className="flex items-center gap-2">
                                                            <CheckCircle size={14} />
                                                            <span>Supply: {plannerSummary.supply.matched_files?.length || 0} files ready</span>
                                                        </div>
                                                    ) : (
                                                        <div className="flex items-center gap-2">
                                                            <AlertCircle size={14} />
                                                            <span>Supply: Missing {plannerSummary?.supply?.missing_files?.length || 0} files</span>
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                            {status === 'error' && error}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Right Panel: Results */}
                    <div className="lg:col-span-2 space-y-6">
                        {result ? (
                            <>
                                {/* Combined Analysis */}
                                {combinedAnalysis && (
                                    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                                        <div className="border-b border-slate-100 p-4 bg-slate-50">
                                            <h3 className="font-semibold text-slate-700 mb-2">Combined Analysis</h3>
                                            <div className="flex gap-2 flex-wrap">
                                                {combinedAnalysis.summary?.recruitment_analyzed && (
                                                    <span className="px-2 py-1 rounded text-xs bg-blue-100 text-blue-700">Recruitment</span>
                                                )}
                                                {combinedAnalysis.summary?.supply_analyzed && (
                                                    <span className="px-2 py-1 rounded text-xs bg-emerald-100 text-emerald-700">Supply</span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="p-6 space-y-4">
                                            {/* Insights */}
                                            {combinedAnalysis.insights && combinedAnalysis.insights.length > 0 && (
                                                <div>
                                                    <h4 className="font-medium text-slate-700 mb-2">Insights</h4>
                                                    <div className="space-y-2">
                                                        {combinedAnalysis.insights.map((insight, idx) => (
                                                            <div key={idx} className="p-3 bg-blue-50 rounded-lg border border-blue-100">
                                                                <div className="text-sm font-medium text-blue-900">{insight.message}</div>
                                                                {insight.data && (
                                                                    <div className="text-xs text-blue-700 mt-1">
                                                                        {insight.type === 'enrollment_forecast' && (
                                                                            <div>Total Enrollment: {insight.data.total_enrollment}</div>
                                                                        )}
                                                                        {insight.type === 'supply_requirements' && (
                                                                            <div>Sites needing resupply: {insight.data.sites_needing_resupply} | Quantity: {insight.data.total_quantity}</div>
                                                                        )}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                            {/* Recommendations */}
                                            {combinedAnalysis.recommendations && combinedAnalysis.recommendations.length > 0 && (
                                                <div>
                                                    <h4 className="font-medium text-slate-700 mb-2">Recommendations</h4>
                                                    <div className="space-y-2">
                                                        {combinedAnalysis.recommendations.map((rec, idx) => (
                                                            <div key={idx} className={`p-3 rounded-lg border ${
                                                                rec.priority === 'high' ? 'bg-amber-50 border-amber-200' : 'bg-slate-50 border-slate-200'
                                                            }`}>
                                                                <div className="text-sm font-medium text-slate-900">{rec.message}</div>
                                                                {rec.action && (
                                                                    <div className="text-xs text-slate-600 mt-1">{rec.action}</div>
                                                                )}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}

                                {/* Individual Agent Results */}
                                {result.recruitment && (
                                    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                                        <div className="border-b border-slate-100 p-4 bg-slate-50 flex items-center justify-between">
                                            <h3 className="font-semibold text-slate-700">Patient Recruitment Analysis</h3>
                                            <span className="px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700 uppercase tracking-wide">
                                                Recruitment Agent
                                            </span>
                                        </div>
                                        <div className="p-6">
                                            {result.recruitment.error ? (
                                                <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                                                    <div className="text-sm font-medium text-red-900 mb-2">Error</div>
                                                    <div className="text-xs text-red-700">{result.recruitment.error}</div>
                                                </div>
                                            ) : (
                                                <div className="space-y-4">
                                                    {/* Structured Summary */}
                                                    {result.recruitment.status === 'success' && (
                                                        <div className="space-y-3">
                                                            <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                                                                <div className="text-sm font-medium text-green-900">✓ {result.recruitment.message || 'Analysis completed successfully'}</div>
                                                                {result.recruitment.filename && (
                                                                    <div className="text-xs text-green-700 mt-1">File: {result.recruitment.filename}</div>
                                                                )}
                                                            </div>
                                                            
                                                            {/* Metadata Summary */}
                                                            {result.recruitment.metadata && (
                                                                <div className="space-y-2">
                                                                    <h4 className="text-sm font-semibold text-slate-700">Summary</h4>
                                                                    {result.recruitment.metadata.counts && (
                                                                        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                                                                            <div className="grid grid-cols-3 gap-4 text-sm">
                                                                                <div>
                                                                                    <div className="text-xs text-slate-500">Total Patients</div>
                                                                                    <div className="font-semibold text-slate-900">{result.recruitment.metadata.counts.patients}</div>
                                                                                </div>
                                                                                <div>
                                                                                    <div className="text-xs text-slate-500">Eligible</div>
                                                                                    <div className="font-semibold text-green-700">{result.recruitment.metadata.counts.eligible_true}</div>
                                                                                </div>
                                                                                <div>
                                                                                    <div className="text-xs text-slate-500">Inconclusive</div>
                                                                                    <div className="font-semibold text-amber-700">{result.recruitment.metadata.counts.inconclusive || 0}</div>
                                                                                </div>
                                                                            </div>
                                                                        </div>
                                                                    )}
                                                                    
                                                                    {/* A2A Integration Results */}
                                                                    {result.recruitment.metadata.a2a_integration && result.recruitment.metadata.a2a_integration.enabled && (
                                                                        <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                                                                            <div className="text-sm font-medium text-blue-900 mb-2">Supply Forecast (A2A)</div>
                                                                            {result.recruitment.metadata.a2a_integration.supply_forecast?.summary && (
                                                                                <div className="text-xs text-blue-700 space-y-1">
                                                                                    <div>Total Enrollment: {result.recruitment.metadata.a2a_integration.total_enrollment || 0}</div>
                                                                                    <div>Total Kits Needed: {result.recruitment.metadata.a2a_integration.supply_forecast.summary.total_kits_needed || 0}</div>
                                                                                    <div>Sites Covered: {result.recruitment.metadata.a2a_integration.supply_forecast.summary.sites_covered || 0}</div>
                                                                                </div>
                                                                            )}
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}
                                                    
                                                    {/* Full JSON (Collapsible) */}
                                                    <details className="mt-4">
                                                        <summary className="cursor-pointer text-sm font-medium text-slate-700 hover:text-slate-900 mb-2">
                                                            View Full JSON Response
                                                        </summary>
                                                        <div className="mt-2 overflow-auto max-h-[400px]">
                                                            <pre className="text-xs font-mono text-slate-600 bg-slate-50 p-4 rounded-lg border border-slate-200 whitespace-pre-wrap">
                                                                {JSON.stringify(result.recruitment, null, 2)}
                                                            </pre>
                                                        </div>
                                                    </details>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}

                                {result.supply && (
                                    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                                        <div className="border-b border-slate-100 p-4 bg-slate-50 flex items-center justify-between">
                                            <h3 className="font-semibold text-slate-700">Clinical Supply Analysis</h3>
                                            <span className="px-3 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700 uppercase tracking-wide">
                                                Supply Agent
                                            </span>
                                        </div>
                                        <div className="p-6">
                                            {result.supply.error ? (
                                                <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                                                    <div className="text-sm font-medium text-red-900 mb-2">Error</div>
                                                    <div className="text-xs text-red-700 font-mono">{result.supply.error}</div>
                                                </div>
                                            ) : (
                                                <div className="space-y-4">
                                                    {/* Structured Summary */}
                                                    {result.supply.summary && (
                                                        <div className="space-y-2">
                                                            <h4 className="text-sm font-semibold text-slate-700">Summary</h4>
                                                            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                                                                <div className="grid grid-cols-2 gap-4 text-sm">
                                                                    <div>
                                                                        <div className="text-xs text-slate-500">Total Sites</div>
                                                                        <div className="font-semibold text-slate-900">{result.supply.summary.total_sites || 0}</div>
                                                                    </div>
                                                                    <div>
                                                                        <div className="text-xs text-slate-500">Sites Needing Resupply</div>
                                                                        <div className="font-semibold text-amber-700">{result.supply.summary.sites_needing_resupply || 0}</div>
                                                                    </div>
                                                                    <div>
                                                                        <div className="text-xs text-slate-500">Total Quantity</div>
                                                                        <div className="font-semibold text-slate-900">{result.supply.summary.total_quantity || 0}</div>
                                                                    </div>
                                                                    <div>
                                                                        <div className="text-xs text-slate-500">Avg Projected Demand</div>
                                                                        <div className="font-semibold text-slate-900">{result.supply.summary.avg_projected_demand?.toFixed(1) || 0}</div>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    )}
                                                    
                                                    {/* Results Table */}
                                                    {result.supply.results && result.supply.results.length > 0 && (
                                                        <div className="space-y-2">
                                                            <h4 className="text-sm font-semibold text-slate-700">Site Details</h4>
                                                            <div className="overflow-auto max-h-[300px] border border-slate-200 rounded-lg">
                                                                <table className="w-full text-xs">
                                                                    <thead className="bg-slate-50 sticky top-0">
                                                                        <tr>
                                                                            <th className="px-3 py-2 text-left text-slate-700 font-semibold">Site ID</th>
                                                                            <th className="px-3 py-2 text-left text-slate-700 font-semibold">Action</th>
                                                                            <th className="px-3 py-2 text-left text-slate-700 font-semibold">Quantity</th>
                                                                            <th className="px-3 py-2 text-left text-slate-700 font-semibold">Urgency</th>
                                                                        </tr>
                                                                    </thead>
                                                                    <tbody className="divide-y divide-slate-200">
                                                                        {result.supply.results.slice(0, 10).map((site, idx) => (
                                                                            <tr key={idx} className="hover:bg-slate-50">
                                                                                <td className="px-3 py-2 text-slate-900">{site.site_id || 'N/A'}</td>
                                                                                <td className="px-3 py-2">
                                                                                    <span className={`px-2 py-1 rounded text-xs ${
                                                                                        site.action === 'resupply' ? 'bg-amber-100 text-amber-700' :
                                                                                        site.action === 'monitor' ? 'bg-blue-100 text-blue-700' :
                                                                                        'bg-green-100 text-green-700'
                                                                                    }`}>
                                                                                        {site.action || 'N/A'}
                                                                                    </span>
                                                                                </td>
                                                                                <td className="px-3 py-2 text-slate-900">{site.quantity || 0}</td>
                                                                                <td className="px-3 py-2 text-slate-900">{site.urgency_score?.toFixed(2) || 'N/A'}</td>
                                                                            </tr>
                                                                        ))}
                                                                    </tbody>
                                                                </table>
                                                                {result.supply.results.length > 10 && (
                                                                    <div className="p-2 text-xs text-slate-500 text-center bg-slate-50">
                                                                        Showing 10 of {result.supply.results.length} sites
                                                                    </div>
                                                                )}
                                                            </div>
                                                        </div>
                                                    )}
                                                    
                                                    {/* Full JSON (Collapsible) */}
                                                    <details className="mt-4">
                                                        <summary className="cursor-pointer text-sm font-medium text-slate-700 hover:text-slate-900 mb-2">
                                                            View Full JSON Response
                                                        </summary>
                                                        <div className="mt-2 overflow-auto max-h-[400px]">
                                                            <pre className="text-xs font-mono text-slate-600 bg-slate-50 p-4 rounded-lg border border-slate-200 whitespace-pre-wrap">
                                                                {JSON.stringify(result.supply, null, 2)}
                                                            </pre>
                                                        </div>
                                                    </details>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}

                                {Object.keys(result).length === 0 && (
                                    <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6">
                                        <div className="flex items-center gap-2 text-amber-800">
                                            <AlertCircle size={20} />
                                            <span className="font-medium">No agents were called</span>
                                        </div>
                                        <p className="text-sm text-amber-700 mt-2">
                                            No agents had all required files. Check the summary for missing files.
                                        </p>
                                    </div>
                                )}
                            </>
                        ) : (
                            <div className="h-full min-h-[400px] flex flex-col items-center justify-center text-slate-400 border-2 border-dashed border-slate-200 rounded-2xl bg-slate-50/50">
                                <Activity size={48} className="mb-4 opacity-20" />
                                <p className="font-medium">No analysis results yet</p>
                                <p className="text-sm">Upload files to start the planning process</p>
                            </div>
                        )}
                    </div>

                </div>
            </main>
        </div>
    );
}

export default App;
