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

export default api;
