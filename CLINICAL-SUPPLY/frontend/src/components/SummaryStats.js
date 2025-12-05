import React from 'react';
import './SummaryStats.css';

function SummaryStats({ summary, sessionId, a2aIntegration }) {
  if (!summary) return null;

  const stats = [
    {
      label: 'Total Sites',
      value: summary.total_sites,
      icon: '🏢',
      color: '#667eea',
    },
    {
      label: 'Sites Needing Resupply',
      value: summary.sites_needing_resupply,
      icon: '📦',
      color: '#f59e0b',
    },
    {
      label: 'Total Quantity',
      value: summary.total_quantity.toLocaleString(),
      icon: '📊',
      color: '#10b981',
    },
    {
      label: 'Avg Projected Demand',
      value: summary.avg_projected_demand.toFixed(1),
      icon: '📈',
      color: '#3b82f6',
    },
    {
      label: 'Avg Processing Time',
      value: `${summary.avg_latency_ms.toFixed(0)}ms`,
      icon: '⚡',
      color: '#8b5cf6',
    },
  ];

  // Add new analysis stats if available
  if (summary.waste_analysis) {
    stats.push({
      label: 'Total Waste',
      value: summary.waste_analysis.total_waste || 0,
      icon: '🗑️',
      color: '#ef4444',
    });
  }

  if (summary.temp_excursions) {
    stats.push({
      label: 'Temp Excursions',
      value: summary.temp_excursions.total_excursions || 0,
      icon: '🌡️',
      color: '#f97316',
    });
  }

  if (summary.depot_optimization) {
    stats.push({
      label: 'Depot Optimization Score',
      value: `${summary.depot_optimization.optimization_score.toFixed(1)}%`,
      icon: '🏭',
      color: '#06b6d4',
    });
  }

  return (
    <div className="summary-container">
      <div className="summary-header">
        <h3>Summary Statistics</h3>
        {sessionId && (
          <div className="session-id">
            Session: <span>{sessionId}</span>
          </div>
        )}
      </div>
      <div className="stats-grid">
        {stats.map((stat, index) => (
          <div key={index} className="stat-card">
            <div className="stat-icon" style={{ background: `${stat.color}20`, color: stat.color }}>
              {stat.icon}
            </div>
            <div className="stat-content">
              <div className="stat-value">{stat.value}</div>
              <div className="stat-label">{stat.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* A2A Integration Results */}
      {a2aIntegration && a2aIntegration.enabled && (
        <div className="a2a-integration-section" style={{
          marginTop: '20px',
          padding: '16px',
          background: 'linear-gradient(135deg, #667eea15 0%, #764ba215 100%)',
          border: '2px solid #667eea',
          borderRadius: '8px'
        }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            marginBottom: '12px',
            gap: '8px'
          }}>
            <span style={{ fontSize: '20px' }}>🔗</span>
            <h4 style={{ 
              margin: 0, 
              color: '#667eea', 
              fontWeight: 'bold',
              fontSize: '16px'
            }}>
              A2A Integration: Enrollment Projection
            </h4>
          </div>

          {a2aIntegration.status === 'failed' ? (
            <div style={{ 
              padding: '12px', 
              background: '#fee2e2', 
              border: '1px solid #fca5a5',
              borderRadius: '4px',
              color: '#991b1b'
            }}>
              <strong>Error:</strong> {a2aIntegration.error || 'Unknown error'}
            </div>
          ) : a2aIntegration.enrollment_projection ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
              <div style={{ 
                background: 'white', 
                padding: '12px', 
                borderRadius: '6px',
                border: '1px solid #e5e7eb'
              }}>
                <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>
                  Total Enrollment
                </div>
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#667eea' }}>
                  {a2aIntegration.enrollment_projection.projected_total_enrollment || 0}
                </div>
              </div>

              <div style={{ 
                background: 'white', 
                padding: '12px', 
                borderRadius: '6px',
                border: '1px solid #e5e7eb'
              }}>
                <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>
                  Total Sites
                </div>
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#667eea' }}>
                  {a2aIntegration.enrollment_projection.total_sites || 0}
                </div>
              </div>

              <div style={{ 
                background: 'white', 
                padding: '12px', 
                borderRadius: '6px',
                border: '1px solid #e5e7eb'
              }}>
                <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>
                  Screen Fail Rate
                </div>
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#667eea' }}>
                  {((a2aIntegration.enrollment_projection.screen_fail_rate || 0) * 100).toFixed(1)}%
                </div>
              </div>

              {a2aIntegration.enrollment_projection.enrollment_curve && (
                <div style={{ 
                  gridColumn: '1 / -1',
                  background: 'white', 
                  padding: '12px', 
                  borderRadius: '6px',
                  border: '1px solid #e5e7eb',
                  marginTop: '8px'
                }}>
                  <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '8px', fontWeight: '500' }}>
                    12-Month Enrollment Curve:
                  </div>
                  <div style={{ 
                    display: 'flex', 
                    flexWrap: 'wrap', 
                    gap: '6px',
                    fontFamily: 'monospace',
                    fontSize: '11px'
                  }}>
                    {a2aIntegration.enrollment_projection.enrollment_curve.map((value, index) => (
                      <span 
                        key={index}
                        style={{
                          background: '#667eea20',
                          color: '#667eea',
                          padding: '4px 8px',
                          borderRadius: '4px',
                          fontWeight: '500'
                        }}
                      >
                        M{index + 1}: {value}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ color: '#6b7280', fontSize: '14px' }}>
              A2A integration enabled but no enrollment projection received.
            </div>
          )}

          {/* Supply Forecast Section */}
          {a2aIntegration.supply_forecast && !a2aIntegration.supply_forecast.error && (
            <div style={{
              marginTop: '20px',
              padding: '16px',
              background: 'linear-gradient(135deg, #10b98115 0%, #05966915 100%)',
              border: '2px solid #10b981',
              borderRadius: '8px'
            }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                marginBottom: '12px',
                gap: '8px'
              }}>
                <span style={{ fontSize: '20px' }}>📦</span>
                <h4 style={{ 
                  margin: 0, 
                  color: '#10b981', 
                  fontWeight: 'bold',
                  fontSize: '16px'
                }}>
                  Clinical Supply Forecast
                </h4>
              </div>

              {a2aIntegration.supply_forecast.summary && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
                  <div style={{ 
                    background: 'white', 
                    padding: '12px', 
                    borderRadius: '6px',
                    border: '1px solid #e5e7eb'
                  }}>
                    <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>
                      Total Enrollment
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#10b981' }}>
                      {a2aIntegration.supply_forecast.summary.total_enrollment || 0}
                    </div>
                  </div>

                  <div style={{ 
                    background: 'white', 
                    padding: '12px', 
                    borderRadius: '6px',
                    border: '1px solid #e5e7eb'
                  }}>
                    <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>
                      Total Kits Needed
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#10b981' }}>
                      {a2aIntegration.supply_forecast.summary.total_kits_needed?.toLocaleString() || 0}
                    </div>
                  </div>

                  <div style={{ 
                    background: 'white', 
                    padding: '12px', 
                    borderRadius: '6px',
                    border: '1px solid #e5e7eb'
                  }}>
                    <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>
                      Sites Covered
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#10b981' }}>
                      {a2aIntegration.supply_forecast.summary.sites_covered || 0}
                    </div>
                  </div>

                  {a2aIntegration.supply_forecast.summary.demand_met_percentage !== undefined && (
                    <div style={{ 
                      background: 'white', 
                      padding: '12px', 
                      borderRadius: '6px',
                      border: '1px solid #e5e7eb'
                    }}>
                      <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>
                        Demand Met
                      </div>
                      <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#10b981' }}>
                        {a2aIntegration.supply_forecast.summary.demand_met_percentage.toFixed(1)}%
                      </div>
                    </div>
                  )}
                </div>
              )}

              {a2aIntegration.supply_forecast.error && (
                <div style={{ 
                  padding: '12px', 
                  background: '#fee2e2', 
                  border: '1px solid #fca5a5',
                  borderRadius: '4px',
                  color: '#991b1b',
                  marginTop: '12px'
                }}>
                  <strong>Supply Forecast Error:</strong> {a2aIntegration.supply_forecast.error}
                </div>
              )}
            </div>
          )}

          {/* Show error if supply forecast calculation failed */}
          {a2aIntegration.supply_forecast && a2aIntegration.supply_forecast.error && (
            <div style={{
              marginTop: '20px',
              padding: '12px', 
              background: '#fee2e2', 
              border: '1px solid #fca5a5',
              borderRadius: '4px',
              color: '#991b1b'
            }}>
              <strong>Supply Forecast Error:</strong> {a2aIntegration.supply_forecast.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default SummaryStats;

