/**
 * services/auth.js
 * ────────────────
 * Token storage helpers + a JWT-authenticated axios instance.
 *
 * Usage:
 *   import { authApi, login, logout, getRole, isAdmin } from './auth';
 *
 *   const { access_token, role } = await login('admin', 'changeme123!');
 *   const subjects = await authApi.get('/subjects');
 */

import axios from 'axios';

const TOKEN_KEY = 'wai_token';
const ROLE_KEY  = 'wai_role';

// ── Token helpers ────────────────────────────────────────────────────────────

export const saveSession = (token, role) => {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ROLE_KEY, role);
};

export const clearSession = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
};

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const getRole  = () => localStorage.getItem(ROLE_KEY);
export const isAdmin  = () => getRole() === 'admin';
export const isLoggedIn = () => !!getToken();

// ── Authenticated axios instance ─────────────────────────────────────────────

export const authApi = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Inject the JWT on every request; let browser set Content-Type for FormData
authApi.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers['Authorization'] = `Bearer ${token}`;
  if (config.data instanceof FormData) delete config.headers['Content-Type'];
  return config;
});

// ── Auth actions ─────────────────────────────────────────────────────────────

/**
 * POST /api/auth/login — returns { access_token, token_type, role }
 * Also persists the session to localStorage.
 */
export const login = async (loginField, password) => {
  const { data } = await authApi.post('/auth/login', {
    login: loginField,
    password,
  });
  saveSession(data.access_token, data.role);
  return data;
};

export const logout = () => {
  clearSession();
};
