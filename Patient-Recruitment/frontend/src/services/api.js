import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 900000, // 15 minutes for large file processing with LLM calls
  headers: {
    'Content-Type': 'multipart/form-data',
  },
});

// Interceptor to handle blob error responses
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    // If error response is a blob (from responseType: 'blob'), convert it to JSON
    if (error.response?.data instanceof Blob) {
      const contentType = error.response.headers['content-type'];
      if (contentType && contentType.includes('application/json')) {
        try {
          const text = await error.response.data.text();
          error.response.data = JSON.parse(text);
        } catch (parseErr) {
          console.error('Failed to parse error response:', parseErr);
        }
      }
    }
    return Promise.reject(error);
  }
);

export const runPipeline = async (files, onProgress) => {
  const formData = new FormData();
  
  formData.append('protocol_pdf', files.protocolPdf);
  formData.append('patients_xlsx', files.patientsXlsx);
  formData.append('mapping_xlsx', files.mappingXlsx);
  formData.append('site_history_xlsx', files.siteHistoryXlsx);

  const response = await api.post('/run', formData, {
    responseType: 'blob', // Important for downloading files
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        );
        onProgress(percentCompleted);
      }
    },
  });

  // Extract metadata from response headers
  // Axios normalizes headers to lowercase, so check 'x-metadata'
  let metadata = null;
  const metadataHeader = response.headers['x-metadata'] || 
                         response.headers['X-Metadata'] ||
                         response.headers['X-METADATA'];
  
  if (metadataHeader) {
    try {
      // Try parsing directly first
      metadata = JSON.parse(metadataHeader);
      console.log('Successfully parsed metadata:', metadata);
    } catch (e) {
      // If that fails, try URL decoding first
      try {
        metadata = JSON.parse(decodeURIComponent(metadataHeader));
        console.log('Successfully parsed metadata (after URL decode):', metadata);
      } catch (e2) {
        console.warn('Failed to parse metadata from headers:', e2);
        console.warn('Metadata header value:', metadataHeader);
        console.warn('All response headers:', Object.keys(response.headers));
      }
    }
  } else {
    console.warn('No metadata header found in response');
    console.warn('Available headers:', Object.keys(response.headers));
  }

  return {
    data: response.data,
    headers: response.headers,
    metadata: metadata,
  };
};

export const checkHealth = async () => {
  try {
    // Use a shorter timeout for health checks
    const response = await axios.get(`${API_BASE_URL}/health`, {
      timeout: 5000, // 5 second timeout for health checks
    });
    return response.data;
  } catch (error) {
    console.error('Health check failed:', error);
    console.error('Error details:', {
      message: error.message,
      code: error.code,
      response: error.response?.data,
      status: error.response?.status,
      url: error.config?.url,
      baseURL: API_BASE_URL,
    });
    throw error;
  }
};

export default api;

