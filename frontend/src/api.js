import axios from 'axios';

const api = axios.create({
  baseURL: '', // Vite proxy handles this
  headers: {
    'Content-Type': 'application/json',
    'X-Tenant-ID': 'demo-tenant', // Default tenant for now
  },
});

export default api;
