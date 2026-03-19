import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 401 interceptor — clear auth and redirect to login on token expiry
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.reload();
    }
    return Promise.reject(error);
  }
);

export async function login(email, password) {
  const res = await api.post('/auth/login', { email, password });
  return res.data;
}

export async function getProperties() {
  const res = await api.get('/properties');
  return res.data;
}

export async function runDiagnostic(propertyId) {
  const res = await api.post(`/properties/${propertyId}/diagnostic/run`);
  return res.data;
}

export async function getDiagnosticRun(runId) {
  const res = await api.get(`/diagnostic/${runId}`);
  return res.data;
}

export async function getSlides(runId) {
  const res = await api.get(`/diagnostic/${runId}/slides`);
  return res.data;
}

export async function getDiagnosticHistory(propertyId) {
  const res = await api.get(`/properties/${propertyId}/diagnostic/history`);
  return res.data;
}

export async function getConfig(propertyId) {
  const res = await api.get(`/properties/${propertyId}/config`);
  return res.data;
}

export async function saveConfig(propertyId, config) {
  const res = await api.post(`/properties/${propertyId}/config`, config);
  return res.data;
}

export async function previewDiagnosis(propertyId, config) {
  const res = await api.post(`/properties/${propertyId}/config/preview`, config);
  return res.data;
}

export async function getComps(propertyId) {
  const res = await api.get(`/properties/${propertyId}/comps`);
  return res.data;
}

export async function getCompTrends(propertyId) {
  const res = await api.get(`/properties/${propertyId}/comps/trends`);
  return res.data;
}

export async function refreshComps() {
  const res = await api.post('/comps/refresh');
  return res.data;
}

export async function getSnapshots(propertyId) {
  const res = await api.get(`/properties/${propertyId}/snapshots`);
  return res.data;
}

export async function getExperiments(propertyId) {
  const res = await api.get(`/properties/${propertyId}/experiments`);
  return res.data;
}

export async function approveExperiment(experimentId) {
  const res = await api.post(`/experiments/${experimentId}/approve`);
  return res.data;
}

export async function cancelExperiment(experimentId) {
  const res = await api.post(`/experiments/${experimentId}/cancel`);
  return res.data;
}

export async function getAuditLog() {
  const res = await api.get('/audit');
  return res.data;
}

export async function getPropertySummary(propertyId) {
  const res = await api.get(`/properties/${propertyId}/summary`);
  return res.data;
}

export async function getConfigTemplates() {
  const res = await api.get('/config/templates');
  return res.data;
}

export async function applyTemplate(propertyId, templateId) {
  const res = await api.post(`/properties/${propertyId}/config/from-template`, { template_id: templateId });
  return res.data;
}

export async function chatWithAI(propertyId, message, latestRunId) {
  const res = await api.post(`/properties/${propertyId}/chat`, {
    message,
    latest_run_id: latestRunId || null,
  });
  return res.data;
}

export async function runPortfolioDiagnostic() {
  const res = await api.post('/diagnostic/portfolio/run');
  return res.data;
}

export async function getPortfolioDiagnosticHistory() {
  const res = await api.get('/diagnostic/portfolio/history');
  return res.data;
}

export async function createPricingDecision(decision) {
  const res = await api.post('/pricing-decisions', decision);
  return res.data;
}

export async function getPricingDecisions(params = {}) {
  const res = await api.get('/pricing-decisions', { params });
  return res.data;
}

export async function getLatestDecisions(propertyId, decisionType = 'PRICING') {
  const res = await api.get('/pricing-decisions/latest', {
    params: { property_id: propertyId, decision_type: decisionType },
  });
  return res.data;
}

export async function createBatchDecisions(decisions) {
  const res = await api.post('/pricing-decisions/batch', { decisions });
  return res.data;
}

export async function getExpiringLeases(propertyId, targetMonth) {
  const res = await api.get('/renewals/expiring', {
    params: { property_id: propertyId, target_month: targetMonth },
  });
  return res.data;
}

export async function previewRenewalPricing(params) {
  const res = await api.post('/renewals/preview', params);
  return res.data;
}

export async function saveRenewalRule(rule) {
  const res = await api.post('/renewal-rules', rule);
  return res.data;
}

export async function getRenewalRules(propertyId, targetMonth) {
  const params = { property_id: propertyId };
  if (targetMonth) params.target_month = targetMonth;
  const res = await api.get('/renewal-rules', { params });
  return res.data;
}

export default api;
