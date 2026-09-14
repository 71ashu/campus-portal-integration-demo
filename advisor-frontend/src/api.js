/**
 * API client for AI Course Advisor backend.
 * Uses fetch with credentials for session-based auth.
 */

// In local dev, Vite proxies same-origin '/api' to the backend (vite.config.js),
// so no env var is needed. In production the frontend (Vercel) and backend
// (Render) are different origins — set VITE_API_BASE to the backend's full
// URL (e.g. https://campus-advisor-backend.onrender.com/api) at build time.
const API_BASE = import.meta.env.VITE_API_BASE || '/api';

async function request(endpoint, options = {}) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed: ${res.status}`);
  }
  return data;
}

export const api = {
  // Auth — mock campus SSO. No password: the portal hands the advisor a
  // campus ID and the advisor looks the student up in the SIS.
  ssoLogin: (sisId) => request('/auth/sso', { method: 'POST', body: JSON.stringify({ sisId }) }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me'),

  // SIS sync
  syncFromSis: () => request('/sync', { method: 'POST' }),

  // Profile (only the fields the SIS doesn't own — interests, career goals)
  getProfile: () => request('/profile'),
  updateProfile: (data) => request('/profile', { method: 'PUT', body: JSON.stringify(data) }),

  // Courses
  getCourses: () => request('/courses'),
  getPrograms: () => request('/programs'),

  // Conversations
  listConversations: () => request('/conversations'),
  createConversation: () => request('/conversations', { method: 'POST' }),
  getConversation: (id) => request(`/conversations/${id}`),
  renameConversation: (id, title) => request(`/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  }),
  deleteConversation: (id) => request(`/conversations/${id}`, { method: 'DELETE' }),

  // Advisor
  getRecommendations: (query, { conversationId = null, history = [] } = {}) => request('/recommend', {
    method: 'POST',
    body: JSON.stringify({ query, conversationId, history }),
  }),
  getProgress: () => request('/progress'),

  // Prerequisite Graph
  getPrerequisitePath: (target) => request(`/prerequisite-path?target=${encodeURIComponent(target)}`),
  getPrerequisiteGraph: () => request('/prerequisite-graph'),
};
