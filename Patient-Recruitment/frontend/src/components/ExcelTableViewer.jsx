import React, { useState, useEffect } from 'react';
import { FileSpreadsheet, ChevronRight, ChevronDown } from 'lucide-react';
import * as XLSX from 'xlsx';

const ExcelTableViewer = ({ blob, filename }) => {
  const [sheets, setSheets] = useState(null);
  const [expandedSheets, setExpandedSheets] = useState(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!blob) {
      setLoading(false);
      return;
    }

    setLoading(true);
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target.result);
        const workbook = XLSX.read(data, { type: 'array' });
        
        const parsedSheets = {};
        workbook.SheetNames.forEach((sheetName) => {
          const worksheet = workbook.Sheets[sheetName];
          const jsonData = XLSX.utils.sheet_to_json(worksheet, { 
            header: 1,
            defval: '', // Default value for empty cells
            raw: false // Convert all values to strings for display
          });
          
          if (jsonData.length > 0) {
            parsedSheets[sheetName] = jsonData;
          }
        });
        
        setSheets(parsedSheets);
        // Expand first sheet by default
        if (Object.keys(parsedSheets).length > 0) {
          setExpandedSheets(new Set([Object.keys(parsedSheets)[0]]));
        }
        setLoading(false);
      } catch (error) {
        console.error('Error parsing Excel file:', error);
        setLoading(false);
      }
    };
    
    reader.onerror = () => {
      console.error('Error reading file');
      setLoading(false);
    };
    
    reader.readAsArrayBuffer(blob);
  }, [blob]);

  const toggleSheet = (sheetName) => {
    const newExpanded = new Set(expandedSheets);
    if (newExpanded.has(sheetName)) {
      newExpanded.delete(sheetName);
    } else {
      newExpanded.add(sheetName);
    }
    setExpandedSheets(newExpanded);
  };

  if (loading) {
    return (
      <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
        <p className="text-gray-600">Loading Excel data...</p>
      </div>
    );
  }

  if (!sheets || Object.keys(sheets).length === 0) {
    return (
      <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
        <p className="text-gray-600">No data available in Excel file</p>
      </div>
    );
  }

  const renderTable = (sheetName, data) => {
    if (!data || data.length === 0) {
      return <p className="text-gray-500 text-sm">No data available</p>;
    }

    // Special handling for "Extracted Criteria" sheet - it's usually just text
    if (sheetName === 'Extracted Criteria' && data.length > 0) {
      const textContent = data.map(row => row[0]).filter(cell => cell).join('\n');
      return (
        <div className="bg-gray-50 rounded p-4 border border-gray-200">
          <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans max-h-96 overflow-y-auto">
            {textContent}
          </pre>
        </div>
      );
    }

    // First row is headers
    const headers = data[0] || [];
    const rows = data.slice(1);

    // Filter out completely empty rows
    const validRows = rows.filter(row => row.some(cell => cell !== '' && cell !== null && cell !== undefined));

    return (
      <div className="overflow-x-auto max-h-[600px] overflow-y-auto border border-gray-300 rounded">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50 sticky top-0 z-10">
            <tr>
              {headers.map((header, idx) => (
                <th
                  key={idx}
                  className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider border-r border-gray-300 last:border-r-0"
                >
                  {header || `Column ${idx + 1}`}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {validRows.map((row, rowIdx) => (
              <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white hover:bg-gray-50' : 'bg-gray-50 hover:bg-gray-100'}>
                {headers.map((_, colIdx) => (
                  <td
                    key={colIdx}
                    className="px-4 py-2 text-sm text-gray-700 border-r border-gray-200 last:border-r-0"
                  >
                    {row[colIdx] !== undefined && row[colIdx] !== null && row[colIdx] !== '' 
                      ? String(row[colIdx]) 
                      : <span className="text-gray-400">—</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="bg-gray-50 px-4 py-2 text-xs text-gray-500 border-t border-gray-200">
          Showing {validRows.length} row{validRows.length !== 1 ? 's' : ''} (excluding header)
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center space-x-2 mb-4">
        <FileSpreadsheet className="w-5 h-5 text-blue-600" />
        <h3 className="text-lg font-semibold text-gray-900">Excel Sheets</h3>
        <span className="text-sm text-gray-500">({Object.keys(sheets).length} sheet{Object.keys(sheets).length !== 1 ? 's' : ''})</span>
      </div>

      <div className="space-y-2">
        {Object.keys(sheets).map((sheetName) => {
          const isExpanded = expandedSheets.has(sheetName);
          const data = sheets[sheetName];
          const rowCount = data.length > 0 ? data.length - 1 : 0; // Exclude header row

          return (
            <div key={sheetName} className="border border-gray-200 rounded-lg overflow-hidden">
              <button
                onClick={() => toggleSheet(sheetName)}
                className="w-full px-4 py-3 bg-gray-50 hover:bg-gray-100 flex items-center justify-between transition-colors"
              >
                <div className="flex items-center space-x-2">
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-gray-600" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-600" />
                  )}
                  <span className="font-medium text-gray-900">{sheetName}</span>
                  <span className="text-sm text-gray-500">({rowCount} rows)</span>
                </div>
              </button>
              
              {isExpanded && (
                <div className="p-4 bg-white">
                  {renderTable(sheetName, data)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ExcelTableViewer;

