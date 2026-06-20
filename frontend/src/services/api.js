import axios from 'axios';

/**
 * Wings of AI - Centralized API Service
 * Handles multi-tenant header injection and base configuration.
 */

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor for Tenant ID injection
api.interceptors.request.use(
  (config) => {
    // MVP Phase 1: Hardcoded Tenant ID for school-alpha-01
    // TODO: Move to JWT or localStorage retrieval in Phase 2
    config.headers['X-Tenant-ID'] = 'school-alpha-01';

    // Handle Multipart Form Data (PDF Uploads)
    // Axios usually sets the correct boundary automatically if we don't override Content-Type
    // for FormData instances. However, if it's already set to JSON, we need to ensure 
    // it doesn't conflict when sending FormData.
    if (config.data instanceof FormData) {
      // Deleting Content-Type allows the browser to set it with the correct boundary
      delete config.headers['Content-Type'];
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default api;
