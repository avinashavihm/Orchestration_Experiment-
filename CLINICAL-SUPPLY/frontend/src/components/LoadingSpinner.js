import React from 'react';
import './LoadingSpinner.css';

function LoadingSpinner() {
  return (
    <div className="loading-container">
      <div className="loading-card">
        <div className="spinner"></div>
        <h2 className="loading-title">Processing Your Data</h2>
        <p className="loading-description">
          Running forecasting analysis and generating recommendations...
        </p>
        <div className="loading-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </div>
  );
}

export default LoadingSpinner;

