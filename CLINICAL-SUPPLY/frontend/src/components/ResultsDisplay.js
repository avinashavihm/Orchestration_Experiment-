import React, { useState } from 'react';
import './ResultsDisplay.css';

// Function to format justification text into structured sections
function formatJustification(text) {
  if (!text) return null;
  
  // Split text into lines
  const lines = text.split('\n');
  
  const sections = [];
  let currentSection = null;
  let documentTitle = null;
  let foundFirstSection = false;
  
  lines.forEach((line) => {
    const trimmedLine = line.trim();
    
    // Skip empty lines
    if (!trimmedLine) {
      return;
    }
    
    // Check if line is a section header (ends with colon, doesn't start with dash or asterisk)
    // Section headers are typically title case or have multiple words
    const endsWithColon = trimmedLine.endsWith(':');
    const notListItem = !trimmedLine.startsWith('-') && !trimmedLine.startsWith('*');
    const looksLikeHeader = endsWithColon && notListItem && 
                            (trimmedLine.split(' ').length > 1 || 
                             /^[A-Z][a-z]/.test(trimmedLine)); // Title case or proper noun
    
    if (looksLikeHeader) {
      // Save previous section if exists
      if (currentSection) {
        sections.push(currentSection);
      }
      
      foundFirstSection = true;
      
      // Start new section
      const headerText = trimmedLine.replace(/:\s*$/, '').trim();
      currentSection = {
        title: headerText,
        content: []
      };
    } else if (!foundFirstSection) {
      // Text before first section (document title)
      // Usually all caps or a prominent title
      if (!documentTitle) {
        documentTitle = trimmedLine;
      }
    } else if (currentSection) {
      // Add content to current section
      if (trimmedLine.startsWith('-') || trimmedLine.startsWith('*')) {
        // List item - remove leading dash/asterisk and any extra whitespace
        const listText = trimmedLine.replace(/^[-*]\s+/, '').trim();
        if (listText) {
          currentSection.content.push({
            type: 'list',
            text: listText
          });
        }
      } else if (trimmedLine) {
        // Regular paragraph
        currentSection.content.push({
          type: 'paragraph',
          text: trimmedLine
        });
      }
    }
  });
  
  // Add last section
  if (currentSection) {
    sections.push(currentSection);
  }
  
  // Render sections
  return (
    <div className="justification-sections">
      {documentTitle && (
        <div className="justification-document-title">{documentTitle}</div>
      )}
      {sections.map((section, sectionIdx) => (
        <div key={sectionIdx} className="justification-section">
          {section.title && (
            <h6 className="justification-section-title">{section.title}</h6>
          )}
          <div className="justification-section-content">
            {section.content.length > 0 ? (
              section.content.map((item, itemIdx) => {
                if (item.type === 'list') {
                  return (
                    <div key={itemIdx} className="justification-list-item">
                      <span className="justification-bullet">•</span>
                      <span className="justification-list-text">{item.text}</span>
                    </div>
                  );
                } else {
                  return (
                    <p key={itemIdx} className="justification-paragraph">{item.text}</p>
                  );
                }
              })
            ) : (
              <p className="justification-paragraph">No content available.</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function ResultsDisplay({ results }) {
  const [expandedSite, setExpandedSite] = useState(null);
  const [filter, setFilter] = useState('all'); // all, resupply, no_resupply
  const [sortBy, setSortBy] = useState('urgency'); // urgency, demand, inventory

  if (!results || results.length === 0) {
    return (
      <div className="no-results">
        <p>No results to display</p>
      </div>
    );
  }

  const filteredResults = results.filter((result) => {
    if (filter === 'all') return true;
    return result.action === filter;
  });

  const sortedResults = [...filteredResults].sort((a, b) => {
    switch (sortBy) {
      case 'urgency':
        return b.urgency_score - a.urgency_score;
      case 'demand':
        return b.projected_30d_demand - a.projected_30d_demand;
      case 'inventory':
        return a.current_inventory - b.current_inventory;
      default:
        return 0;
    }
  });

  const toggleExpand = (siteId) => {
    setExpandedSite(expandedSite === siteId ? null : siteId);
  };

  const getActionBadgeClass = (action) => {
    return action === 'resupply' ? 'badge-resupply' : 'badge-no-resupply';
  };

  const getUrgencyClass = (urgency) => {
    if (urgency >= 3) return 'urgency-high';
    if (urgency >= 2) return 'urgency-medium';
    return 'urgency-low';
  };

  return (
    <div className="results-display">
      <div className="results-controls">
        <div className="filter-group">
          <label>Filter:</label>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="filter-select"
          >
            <option value="all">All Sites</option>
            <option value="resupply">Needs Resupply</option>
            <option value="no_resupply">No Resupply</option>
          </select>
        </div>

        <div className="sort-group">
          <label>Sort by:</label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="sort-select"
          >
            <option value="urgency">Urgency Score</option>
            <option value="demand">Projected Demand</option>
            <option value="inventory">Current Inventory</option>
          </select>
        </div>
      </div>

      <div className="results-list">
        {sortedResults.map((result, index) => (
          <div key={result.site_id || index} className="result-card">
            <div className="result-header" onClick={() => toggleExpand(result.site_id)}>
              <div className="result-main-info">
                <div className="result-site-info">
                  <h4 className="site-name">{result.site_name || result.site_id}</h4>
                  <div className="site-meta">
                    <span className="site-id">ID: {result.site_id}</span>
                    {result.region && (
                      <span className="site-region">📍 {result.region}</span>
                    )}
                  </div>
                </div>

                <div className="result-metrics">
                  <div className="metric">
                    <span className="metric-label">Inventory</span>
                    <span className="metric-value">{result.current_inventory}</span>
                  </div>
                  <div className="metric">
                    <span className="metric-label">30d Demand</span>
                    <span className="metric-value">{result.projected_30d_demand}</span>
                  </div>
                  <div className="metric">
                    <span className="metric-label">Urgency</span>
                    <span className={`metric-value ${getUrgencyClass(result.urgency_score)}`}>
                      {result.urgency_score.toFixed(1)}
                    </span>
                  </div>
                </div>

                <div className="result-action">
                  <span className={`action-badge ${getActionBadgeClass(result.action)}`}>
                    {result.action === 'resupply' ? '📦 Resupply' : '✓ No Action'}
                  </span>
                  {result.action === 'resupply' && (
                    <span className="quantity-badge">
                      Qty: {result.quantity}
                    </span>
                  )}
                </div>
              </div>

              <button className="expand-button">
                {expandedSite === result.site_id ? '▼' : '▶'}
              </button>
            </div>

            {expandedSite === result.site_id && (
              <div className="result-details">
                <div className="details-grid">
                  <div className="detail-item">
                    <span className="detail-label">Weekly Dispense:</span>
                    <span className="detail-value">
                      {result.weekly_dispense_kits?.toFixed(2) || 'N/A'} kits/week
                    </span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Days to Expiry:</span>
                    <span className="detail-value">
                      {result.days_to_expiry || 'N/A'} days
                    </span>
                  </div>
                  {result.latency_ms && (
                    <div className="detail-item">
                      <span className="detail-label">Processing Time:</span>
                      <span className="detail-value">
                        {result.latency_ms.toFixed(0)}ms
                      </span>
                    </div>
                  )}
                </div>

                <div className="reason-section">
                  <h5 className="reason-title">Recommendation Reason:</h5>
                  <p className="reason-text">{result.reason || 'No reason provided'}</p>
                </div>

                {result.llm && result.llm.structured_result && (
                  <div className="llm-section">
                    <h5 className="llm-title">AI Analysis Details:</h5>
                    <div className="llm-details">
                      <div className="llm-confidence">
                        <span className="llm-label">Confidence:</span>
                        <span className="llm-value">
                          {(result.llm.structured_result.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                      {result.llm.structured_result.reasons && result.llm.structured_result.reasons.length > 0 && (
                        <div className="llm-reasons">
                          <div className="llm-reasons-label">Key Reasons:</div>
                          <ul className="llm-reasons-list">
                            {result.llm.structured_result.reasons.map((reason, idx) => (
                              <li key={idx} className="llm-reason-item">
                                {reason}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Enrollment Predictions */}
                {(result.predicted_30d_enrollment !== undefined || result.enrollment_trend || result.screen_fail_rate !== undefined) && (
                  <div className="enrollment-section">
                    <h5 className="section-title">📊 Enrollment Predictions:</h5>
                    <div className="enrollment-content">
                      {result.predicted_30d_enrollment !== undefined && (
                        <div className="enrollment-item">
                          <span className="enrollment-label">Predicted 30d Enrollment:</span>
                          <span className="enrollment-value">{result.predicted_30d_enrollment}</span>
                        </div>
                      )}
                      {result.enrollment_trend && (
                        <div className="enrollment-item">
                          <span className="enrollment-label">Enrollment Trend:</span>
                          <span className="enrollment-value">{result.enrollment_trend}</span>
                        </div>
                      )}
                      {result.screen_fail_rate !== undefined && (
                        <div className="enrollment-item">
                          <span className="enrollment-label">Screen Fail Rate:</span>
                          <span className="enrollment-value">{(result.screen_fail_rate * 100).toFixed(1)}%</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Waste Analysis */}
                {result.waste_data && result.waste_data.total_waste > 0 && (
                  <div className="waste-section">
                    <h5 className="section-title">🗑️ Waste Analysis:</h5>
                    <div className="waste-content">
                      <div className="waste-item">
                        <span className="waste-label">Total Waste:</span>
                        <span className="waste-value">{result.waste_data.total_waste} kits</span>
                      </div>
                      {result.waste_data.waste_by_reason && Object.keys(result.waste_data.waste_by_reason).length > 0 && (
                        <div className="waste-reasons-container">
                          <span className="waste-label">By Reason:</span>
                          <div className="waste-reasons-list">
                            {Object.entries(result.waste_data.waste_by_reason).map(([reason, qty]) => (
                              <div key={reason} className="waste-reason-badge">
                                <span className="waste-reason-name">{reason}:</span>
                                <span className="waste-reason-qty">{qty}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Temperature Excursions */}
                {result.temp_excursions && result.temp_excursions.total_excursions > 0 && (
                  <div className="temp-excursion-section">
                    <h5 className="section-title">🌡️ Temperature Excursions:</h5>
                    <div className="temp-excursion-content">
                      <div className="temp-excursion-metrics">
                        <div className="temp-excursion-item">
                          <span className="temp-excursion-label">Total Excursions:</span>
                          <span className="temp-excursion-value warning">{result.temp_excursions.total_excursions}</span>
                        </div>
                        <div className="temp-excursion-item">
                          <span className="temp-excursion-label">Quantity Affected:</span>
                          <span className="temp-excursion-value">{result.temp_excursions.total_quantity_affected} kits</span>
                        </div>
                        {result.temp_excursions.excursion_rate > 0 && (
                          <div className="temp-excursion-item">
                            <span className="temp-excursion-label">Excursion Rate:</span>
                            <span className="temp-excursion-value">{(result.temp_excursions.excursion_rate * 100).toFixed(1)}%</span>
                          </div>
                        )}
                      </div>
                      {result.temp_excursions.justification && (
                        <div className="justification-container">
                          <div className="justification-title">Regulatory Justification:</div>
                          <div className="justification-content">
                            {formatJustification(result.temp_excursions.justification)}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default ResultsDisplay;

