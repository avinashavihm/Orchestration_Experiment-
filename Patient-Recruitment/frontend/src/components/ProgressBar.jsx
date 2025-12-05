import React from 'react';
import { Loader2 } from 'lucide-react';

const ProgressBar = ({ progress, status, message }) => {
  return (
    <div className="w-full space-y-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-gray-700">{status}</span>
        {progress !== null && (
          <span className="text-gray-500">{progress}%</span>
        )}
      </div>
      
      <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
        <div
          className="bg-primary-600 h-2.5 rounded-full transition-all duration-300 ease-out"
          style={{
            width: progress !== null ? `${progress}%` : '100%',
          }}
        />
      </div>
      
      {message && (
        <div className="flex items-center space-x-2 text-sm text-gray-600">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>{message}</span>
        </div>
      )}
    </div>
  );
};

export default ProgressBar;

