import React, { useState } from 'react';
import { Download, CheckCircle2, XCircle, AlertTriangle, FileSpreadsheet, ChevronDown, ChevronUp, CheckCircle, Package, TrendingUp, Activity, Building2 } from 'lucide-react';
import ExcelTableViewer from './ExcelTableViewer';

const ResultsDisplay = ({ results, onDownload }) => {
  const [errorsExpanded, setErrorsExpanded] = useState(false);
  const [a2aExpanded, setA2AExpanded] = useState(false);

  if (!results) return null;

  const { counts, errors, downloadUrl, filename, blob, a2aIntegration } = results;

  const handleDownload = () => {
    if (downloadUrl) {
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename || 'eligibility_results.xlsx';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } else if (onDownload) {
      onDownload();
    }
  };

  return (
    <div className="card space-y-6">
      {/* Success Message - matching Streamlit's st.success */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <div className="flex items-center space-x-2">
          <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
          <p className="text-green-800 font-medium">Done! Download your results below.</p>
        </div>
      </div>

      {/* Download Button */}
      {downloadUrl && (
        <div className="flex justify-center">
          <button
            onClick={handleDownload}
            className="btn-primary flex items-center space-x-2"
          >
            <Download className="w-5 h-5" />
            <span>Download XLSX results</span>
          </button>
        </div>
      )}

      {/* Summary Section - matching Streamlit's st.subheader and st.metric */}
      {counts && (
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-4">Summary</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
              <div className="flex items-center space-x-2 mb-2">
                <FileSpreadsheet className="w-5 h-5 text-blue-600" />
                <h3 className="font-semibold text-blue-900">Total Patients</h3>
              </div>
              <p className="text-3xl font-bold text-blue-700">{counts.patients || 0}</p>
            </div>

            <div className="bg-green-50 rounded-lg p-4 border border-green-200">
              <div className="flex items-center space-x-2 mb-2">
                <CheckCircle2 className="w-5 h-5 text-green-600" />
                <h3 className="font-semibold text-green-900">Eligible = True</h3>
              </div>
              <p className="text-3xl font-bold text-green-700">{counts.eligible_true || 0}</p>
            </div>

            <div className="bg-yellow-50 rounded-lg p-4 border border-yellow-200">
              <div className="flex items-center space-x-2 mb-2">
                <AlertTriangle className="w-5 h-5 text-yellow-600" />
                <h3 className="font-semibold text-yellow-900">Inconclusive</h3>
              </div>
              <p className="text-3xl font-bold text-yellow-700">{counts.inconclusive || 0}</p>
            </div>
          </div>
        </div>
      )}

      {/* Excel Table Viewer */}
      {blob && (
        <div className="border-t border-gray-200 pt-6">
          <ExcelTableViewer blob={blob} filename={filename} />
        </div>
      )}

      {/* A2A Integration Results Section */}
      {a2aIntegration && a2aIntegration.enabled && (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              <Activity className="w-5 h-5 text-purple-600 flex-shrink-0" />
              <h3 className="font-semibold text-purple-900">A2A Integration: Supply Forecast</h3>
            </div>
            {a2aIntegration.status !== 'failed' && (
              <button
                onClick={() => setA2AExpanded(!a2aExpanded)}
                className="flex items-center space-x-2 text-purple-800 hover:text-purple-900 font-medium text-sm"
              >
                <span>{a2aExpanded ? 'Hide Details' : 'Show Details'}</span>
                {a2aExpanded ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
              </button>
            )}
          </div>

          {a2aIntegration.status === 'failed' ? (
            <div className="text-red-800 text-sm">
              <p className="font-medium mb-1">A2A integration failed:</p>
              <p className="font-mono text-xs">{a2aIntegration.error || 'Unknown error'}</p>
            </div>
          ) : a2aIntegration.supply_forecast ? (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                <div className="bg-white rounded-lg p-3 border border-purple-100">
                  <div className="flex items-center space-x-2 mb-1">
                    <TrendingUp className="w-4 h-4 text-purple-600" />
                    <span className="text-xs font-medium text-purple-900">Total Enrollment</span>
                  </div>
                  <p className="text-2xl font-bold text-purple-700">
                    {a2aIntegration.total_enrollment || 0}
                  </p>
                </div>

                <div className="bg-white rounded-lg p-3 border border-purple-100">
                  <div className="flex items-center space-x-2 mb-1">
                    <Package className="w-4 h-4 text-purple-600" />
                    <span className="text-xs font-medium text-purple-900">Total Kits Needed</span>
                  </div>
                  <p className="text-2xl font-bold text-purple-700">
                    {a2aIntegration.supply_forecast?.summary?.total_kits_needed || 0}
                  </p>
                </div>

                <div className="bg-white rounded-lg p-3 border border-purple-100">
                  <div className="flex items-center space-x-2 mb-1">
                    <Building2 className="w-4 h-4 text-purple-600" />
                    <span className="text-xs font-medium text-purple-900">Sites Covered</span>
                  </div>
                  <p className="text-2xl font-bold text-purple-700">
                    {a2aIntegration.supply_forecast?.summary?.sites_covered || 0}
                  </p>
                </div>

                <div className="bg-white rounded-lg p-3 border border-purple-100">
                  <div className="flex items-center space-x-2 mb-1">
                    <CheckCircle className="w-4 h-4 text-purple-600" />
                    <span className="text-xs font-medium text-purple-900">Demand Met</span>
                  </div>
                  <p className="text-2xl font-bold text-purple-700">
                    {a2aIntegration.supply_forecast?.summary?.demand_met_percentage?.toFixed(1) || 0}%
                  </p>
                </div>
              </div>

              {/* Expanded Details */}
              {a2aExpanded && (
                <div className="mt-4 space-y-4 bg-white rounded-lg p-4 border border-purple-100">
                  {/* Enrollment Curve */}
                  {a2aIntegration.enrollment_curve && (
                    <div>
                      <h4 className="font-semibold text-purple-900 mb-2 text-sm">
                        12-Month Enrollment Curve:
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {a2aIntegration.enrollment_curve.map((value, index) => (
                          <div
                            key={index}
                            className="bg-purple-100 text-purple-900 px-2 py-1 rounded text-xs font-mono"
                          >
                            M{index + 1}: {value}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Depot Forecast */}
                  {a2aIntegration.supply_forecast?.depot_forecast && (
                    <div>
                      <h4 className="font-semibold text-purple-900 mb-2 text-sm">
                        Depot Forecast:
                      </h4>
                      <div className="text-sm text-gray-700 space-y-1">
                        <p>
                          Total Kits Required:{' '}
                          <span className="font-semibold">
                            {a2aIntegration.supply_forecast.depot_forecast.total_kits_required || 0}
                          </span>
                        </p>
                        {a2aIntegration.supply_forecast.depot_forecast.depot_inventory_required && (
                          <div className="mt-2">
                            <p className="font-medium mb-1">Depot Inventory Required:</p>
                            <div className="space-y-1">
                              {Object.entries(
                                a2aIntegration.supply_forecast.depot_forecast.depot_inventory_required
                              ).map(([depot, quantity]) => (
                                <p key={depot} className="text-xs font-mono ml-4">
                                  {depot}: {quantity} kits
                                </p>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Safety Stock */}
                  {a2aIntegration.supply_forecast?.expiry_and_safety_stock && (
                    <div>
                      <h4 className="font-semibold text-purple-900 mb-2 text-sm">
                        Safety Stock:
                      </h4>
                      <p className="text-sm text-gray-700">
                        Total Safety Stock:{' '}
                        <span className="font-semibold">
                          {a2aIntegration.supply_forecast.expiry_and_safety_stock.total_safety_stock || 0} kits
                        </span>
                      </p>
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-purple-800">
              A2A integration enabled but no supply forecast received.
            </p>
          )}
        </div>
      )}

      {/* Errors Section - matching Streamlit's st.warning and st.expander */}
      {errors && errors.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center space-x-2 mb-2">
            <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0" />
            <p className="text-yellow-800 font-medium">Some batches reported errors.</p>
          </div>
          
          {/* Expandable errors section - matching Streamlit's st.expander */}
          <button
            onClick={() => setErrorsExpanded(!errorsExpanded)}
            className="mt-2 flex items-center space-x-2 text-yellow-800 hover:text-yellow-900 font-medium text-sm"
          >
            <span>Show errors</span>
            {errorsExpanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>
          
          {errorsExpanded && (
            <div className="mt-3 space-y-2">
              {errors.map((error, index) => (
                <div
                  key={index}
                  className="bg-white rounded p-3 border border-yellow-300 font-mono text-xs text-gray-800 overflow-x-auto"
                >
                  {typeof error === 'string' ? error : JSON.stringify(error, null, 2)}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ResultsDisplay;

