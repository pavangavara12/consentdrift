import {
  ConsentListItem,
  ConsentDetail,
  ConsentCreateInput,
  EvidenceCreateInput,
  AnalysisRead,
  EvaluationResults,
  User,
  Alert,
  AlertEvent,
  ComplaintDraft,
  NotificationItem,
  TimelineEvent,
  AnalyticsData
} from './types';

const API_BASE = 'http://localhost:8000/api';

let isRefreshing = false;
let failedQueue: Array<() => void> = [];

const processQueue = () => {
  failedQueue.forEach((cb) => cb());
  failedQueue = [];
};

async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const defaultHeaders: HeadersInit = {};
  if (!(options.body instanceof FormData)) {
    defaultHeaders['Content-Type'] = 'application/json';
  }

  const config: RequestInit = {
    ...options,
    credentials: 'include',
    headers: {
      ...defaultHeaders,
      ...options.headers
    }
  };

  let response = await fetch(url, config);

  // Auto-refresh token on 401 for authenticated endpoints
  if (response.status === 401 && !endpoint.startsWith('/auth/login') && !endpoint.startsWith('/auth/register') && !endpoint.startsWith('/auth/refresh') && !endpoint.startsWith('/playground')) {
    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          credentials: 'include'
        });
        if (refreshRes.ok) {
          isRefreshing = false;
          processQueue();
          response = await fetch(url, config);
        } else {
          isRefreshing = false;
          // Clear any state and let app redirect to login
          throw new Error('Session expired. Please log in again.');
        }
      } catch (err) {
        isRefreshing = false;
        throw err;
      }
    } else {
      return new Promise<T>((resolve, reject) => {
        failedQueue.push(async () => {
          try {
            const retryRes = await fetch(url, config);
            if (!retryRes.ok) {
              const errData = await retryRes.json().catch(() => ({}));
              reject(new Error(errData.detail || `Request failed with status ${retryRes.status}`));
            } else {
              resolve(await retryRes.json());
            }
          } catch (e) {
            reject(e);
          }
        });
      });
    }
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Request failed with status ${response.status}`);
  }

  return response.json();
}

export const api = {
  // --- AUTH ---
  register: (data: { full_name: string; email: string; password: string; phone?: string }) =>
    apiFetch<User>('/auth/register', { method: 'POST', body: JSON.stringify(data) }),

  login: (data: { email: string; password: string }) =>
    apiFetch<User>('/auth/login', { method: 'POST', body: JSON.stringify(data) }),

  logout: () =>
    apiFetch<{ message: string }>('/auth/logout', { method: 'POST' }),

  getMe: () =>
    apiFetch<User>('/auth/me'),

  forgotPassword: (email: string) =>
    apiFetch<{ message: string }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email })
    }),

  resetPassword: (token: string, new_password: string) =>
    apiFetch<{ message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password })
    }),

  changePassword: (current_password: string, new_password: string) =>
    apiFetch<{ message: string }>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password })
    }),

  deleteAccount: (password: string, confirm_text: string) =>
    apiFetch<{ message: string }>('/auth/account', {
      method: 'DELETE',
      body: JSON.stringify({ password, confirm_text })
    }),

  // --- PLAYGROUND (No Auth Required) ---
  analyzePlayground: (original_purpose: string, evidence_text: string) =>
    apiFetch<AnalysisRead>('/playground/analyze', {
      method: 'POST',
      body: JSON.stringify({ original_purpose, evidence_text })
    }),

  // --- CONSENTS ---
  getConsents: () =>
    apiFetch<ConsentListItem[]>('/consents'),

  getConsent: (id: number) =>
    apiFetch<ConsentDetail>(`/consents/${id}`),

  createConsent: (data: ConsentCreateInput) =>
    apiFetch<ConsentDetail>('/consents', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  deleteConsent: (id: number) =>
    apiFetch<{ message: string }>(`/consents/${id}`, {
      method: 'DELETE'
    }),

  getConsentTimeline: (id: number) =>
    apiFetch<TimelineEvent[]>(`/consents/${id}/timeline`),

  exportConsentJson: (id: number) =>
    apiFetch<any>(`/consents/${id}/export`),

  comparePolicies: (id: number, evidence_id_1: number, evidence_id_2: number) =>
    apiFetch<any>(`/consents/${id}/policy-diff`, {
      method: 'POST',
      body: JSON.stringify({ evidence_id_1, evidence_id_2 })
    }),

  // --- EVIDENCE ---
  submitEvidence: (data: EvidenceCreateInput) =>
    apiFetch<{ analysis: AnalysisRead; evidence_id: number; consent_id: number }>('/evidence', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  uploadEvidenceFile: (formData: FormData) =>
    apiFetch<{ analysis: AnalysisRead; evidence_id: number; consent_id: number }>('/evidence/upload', {
      method: 'POST',
      body: formData
    }),

  // --- ANALYSES ---
  getAnalysis: (id: number) =>
    apiFetch<AnalysisRead>(`/analyses/${id}`),

  createClarificationDraft: (id: number, template: string = 'general') =>
    apiFetch<ComplaintDraft>(`/analyses/${id}/clarification`, {
      method: 'POST',
      body: JSON.stringify({ template })
    }),

  generateClarification: (id: number, template: string = 'general') =>
    apiFetch<ComplaintDraft>(`/analyses/${id}/clarification`, {
      method: 'POST',
      body: JSON.stringify({ template })
    }),

  // --- ALERTS ---
  getAlerts: (params?: { risk?: string; status?: string; q?: string }) => {
    const query = new URLSearchParams();
    if (params?.risk) query.append('risk', params.risk);
    if (params?.status) query.append('status', params.status);
    if (params?.q) query.append('q', params.q);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return apiFetch<Alert[]>(`/alerts${qs}`);
  },

  updateAlert: (id: number, data: { status?: string; notes?: string }) =>
    apiFetch<Alert>(`/alerts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  getAlertEvents: (id: number) =>
    apiFetch<AlertEvent[]>(`/alerts/${id}/events`),

  // --- COMPLAINT DRAFTS ---
  getDrafts: () =>
    apiFetch<ComplaintDraft[]>('/drafts'),

  getDraft: (id: number) =>
    apiFetch<ComplaintDraft>(`/drafts/${id}`),

  createDraft: (data: { consent_id: number; analysis_id?: number; template: string; subject: string; body: string }) =>
    apiFetch<ComplaintDraft>('/drafts', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateDraft: (id: number, data: { template?: string; subject?: string; body?: string; status?: string }) =>
    apiFetch<ComplaintDraft>(`/drafts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  deleteDraft: (id: number) =>
    apiFetch<{ message: string }>(`/drafts/${id}`, {
      method: 'DELETE'
    }),

  getDraftPdfUrl: (id: number) => `${API_BASE}/drafts/${id}/pdf`,

  // --- NOTIFICATIONS ---
  getNotifications: () =>
    apiFetch<NotificationItem[]>('/notifications'),

  markNotificationsRead: () =>
    apiFetch<{ message: string }>('/notifications/read-all', { method: 'POST' }),

  // --- ANALYTICS ---
  getAnalytics: () =>
    apiFetch<AnalyticsData>('/analytics'),

  // --- ACCOUNT & SYSTEM ---
  exportAccountJson: () =>
    apiFetch<any>('/account/export'),

  getAccountReportPdfUrl: () => `${API_BASE}/account/report.pdf`,

  getHealth: () =>
    apiFetch<{ status: string; mode: string; llm_available: boolean; llm_model?: string }>('/health'),

  seedDemo: () =>
    apiFetch<{ status: string; message: string }>('/seed', { method: 'POST' }),

  getEvalResults: () =>
    apiFetch<EvaluationResults>('/eval/results')
};
