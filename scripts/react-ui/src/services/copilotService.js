import api from '../utils/api';

/**
 * Phase 1 Help Copilot API.
 * Provider/model are resolved from the server-owned shared Copilot settings.
 */
export async function sendCopilotChat({
  messages,
  locale = 'zh',
  pageContext = null,
  signal,
} = {}) {
  const payload = {
    messages,
    locale,
  };
  if (pageContext) payload.page_context = pageContext;
  const response = await api.post('/api/copilot/chat', payload, { signal });
  return response.data;
}

export async function fetchCopilotSettings() {
  const response = await api.get('/api/copilot/settings');
  return response.data;
}

export async function saveCopilotSettings(payload) {
  const response = await api.put('/api/copilot/settings', payload);
  return response.data;
}

export async function fetchCopilotStatus() {
  const response = await api.get('/api/copilot/status');
  return response.data;
}

export async function fetchCopilotActions() {
  const response = await api.get('/api/copilot/actions');
  return response.data;
}

export async function fetchCopilotActionDetail(actionId) {
  const response = await api.get(`/api/copilot/actions/${actionId}`);
  return response.data;
}

export async function planLocalizationWorkflow(payload) {
  const response = await api.post('/api/copilot/workflows/localize-mod/plan', payload);
  return response.data;
}

export async function executeCopilotWorkflow(planId) {
  const response = await api.post('/api/copilot/workflows/execute', { plan_id: planId });
  return response.data;
}

export async function executeGuidedLocalizationWorkflow(planId) {
  const response = await api.post('/api/copilot/workflows/localize-mod/execute', { plan_id: planId });
  return response.data;
}

export async function planInitialTranslationWorkflow(payload) {
  const response = await api.post('/api/copilot/workflows/initial-translation/plan', payload);
  return response.data;
}

export async function executeInitialTranslationWorkflow(planId) {
  const response = await api.post('/api/copilot/workflows/initial-translation/execute', { plan_id: planId });
  return response.data;
}

export async function recommendInitialTranslationWorkflow(payload) {
  const response = await api.post('/api/copilot/workflows/initial-translation/recommend', payload);
  return response.data;
}
