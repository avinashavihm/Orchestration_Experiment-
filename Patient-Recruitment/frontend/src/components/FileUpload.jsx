import React, { useRef, useState } from 'react';
import { Upload, File, X, CheckCircle2, AlertCircle } from 'lucide-react';

const FileUpload = ({ label, accept, file, onChange, required, description }) => {
  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.type.includes(accept.split('/')[1] || accept.split('.')[1])) {
      onChange(droppedFile);
    }
  };

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      onChange(selectedFile);
    }
  };

  const handleRemove = (e) => {
    e.stopPropagation();
    onChange(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="w-full">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      {description && (
        <p className="text-xs text-gray-500 mb-3">{description}</p>
      )}
      
      <div
        className={`file-upload-area ${isDragging ? 'dragover' : ''} ${file ? 'border-green-300 bg-green-50' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={accept}
          onChange={handleFileSelect}
          className="hidden"
        />
        
        {file ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <CheckCircle2 className="w-6 h-6 text-green-600" />
              <div className="text-left">
                <p className="font-medium text-gray-900">{file.name}</p>
                <p className="text-sm text-gray-500">{formatFileSize(file.size)}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleRemove}
              className="p-2 hover:bg-red-100 rounded-full transition-colors"
              aria-label="Remove file"
            >
              <X className="w-5 h-5 text-red-600" />
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center space-y-2">
            <Upload className="w-10 h-10 text-gray-400" />
            <div className="text-center">
              <p className="text-sm font-medium text-gray-700">
                Click to upload or drag and drop
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {accept.includes('pdf') ? 'PDF file' : 'Excel file (.xlsx)'}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FileUpload;

