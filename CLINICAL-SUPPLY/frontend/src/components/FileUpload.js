import React, { useState } from 'react';
import './FileUpload.css';

const REQUIRED_FILES = [
  { key: 'sites', name: 'sites.csv', description: 'Site information' },
  { key: 'enrollment', name: 'enrollment.csv', description: 'Enrollment data' },
  { key: 'dispense', name: 'dispense.csv', description: 'Dispense records' },
  { key: 'inventory', name: 'inventory.csv', description: 'Current inventory' },
  { key: 'shipment', name: 'shipment_logs.csv', description: 'Shipment logs' },
  { key: 'waste', name: 'waste.csv', description: 'Waste records' },
];

function FileUpload({ onUpload, onRunDefault }) {
  const [files, setFiles] = useState({});
  const [dragActive, setDragActive] = useState({});
  const [enableA2A, setEnableA2A] = useState(false);

  const handleFileChange = (key, event) => {
    const file = event.target.files[0];
    if (file) {
      setFiles((prev) => ({ ...prev, [key]: file }));
    }
  };

  const handleDrag = (e, key) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive((prev) => ({ ...prev, [key]: true }));
    } else if (e.type === 'dragleave') {
      setDragActive((prev) => ({ ...prev, [key]: false }));
    }
  };

  const handleDrop = (e, key) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive((prev) => ({ ...prev, [key]: false }));

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFiles((prev) => ({ ...prev, [key]: e.dataTransfer.files[0] }));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    const formData = new FormData();
    let allFilesPresent = true;
    const missingFiles = [];

    REQUIRED_FILES.forEach((fileInfo) => {
      const file = files[fileInfo.key];
      if (!file) {
        allFilesPresent = false;
        missingFiles.push(fileInfo.name);
      } else {
        formData.append(fileInfo.key, file);
      }
    });

    if (!allFilesPresent) {
      alert(`Please upload all required files. Missing: ${missingFiles.join(', ')}`);
      return;
    }

    onUpload(formData, enableA2A);
  };

  const allFilesUploaded = REQUIRED_FILES.every((fileInfo) => files[fileInfo.key]);

  return (
    <div className="upload-container">
      <div className="upload-card">
        <h2 className="upload-title">Upload CSV Files</h2>
        <p className="upload-description">
          Upload all 6 required CSV files to run the forecasting analysis
        </p>

        <form onSubmit={handleSubmit} className="upload-form">
          <div className="files-grid">
            {REQUIRED_FILES.map((fileInfo) => (
              <div
                key={fileInfo.key}
                className={`file-upload-item ${dragActive[fileInfo.key] ? 'drag-active' : ''} ${files[fileInfo.key] ? 'file-selected' : ''}`}
                onDragEnter={(e) => handleDrag(e, fileInfo.key)}
                onDragLeave={(e) => handleDrag(e, fileInfo.key)}
                onDragOver={(e) => handleDrag(e, fileInfo.key)}
                onDrop={(e) => handleDrop(e, fileInfo.key)}
              >
                <input
                  type="file"
                  id={fileInfo.key}
                  accept=".csv"
                  onChange={(e) => handleFileChange(fileInfo.key, e)}
                  className="file-input"
                />
                <label htmlFor={fileInfo.key} className="file-label">
                  <div className="file-icon">
                    {files[fileInfo.key] ? '✓' : '📄'}
                  </div>
                  <div className="file-info">
                    <div className="file-name">{fileInfo.name}</div>
                    <div className="file-description">{fileInfo.description}</div>
                    {files[fileInfo.key] && (
                      <div className="file-selected-name">
                        {files[fileInfo.key].name}
                      </div>
                    )}
                  </div>
                </label>
              </div>
            ))}
          </div>

          <div className="upload-options">
            <label className="a2a-checkbox">
              <input
                type="checkbox"
                checked={enableA2A}
                onChange={(e) => setEnableA2A(e.target.checked)}
                className="checkbox-input"
              />
              <span className="checkbox-label">
                🔗 Enable A2A Integration (Get enrollment forecast from Recruitment agent)
              </span>
            </label>
          </div>

          <div className="upload-actions">
            <button
              type="submit"
              className="submit-button"
              disabled={!allFilesUploaded}
            >
              Run Analysis
            </button>
            <button
              type="button"
              className="default-button"
              onClick={onRunDefault}
            >
              Use Default Data
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default FileUpload;

