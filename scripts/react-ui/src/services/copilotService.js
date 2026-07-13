import api from '../utils/api';

/**
 * Phase 1 Help Copilot API.
 * provider defaults to lm_studio on the backend for local testing.
 * provider/model are already accepted so a UI picker can be added later.
 */
export async function sendCopilotChat({
  messages,
  provider = 'lm_studio',
  model = null,
  locale = 'zh',
  pageContext = null,
  signal,
} = {}) {
  const payload = {
    messages,
    provider,
    locale,
  };
  if (pageContext) payload.page_context = pageContext;
  if (model) {
    payload.model = model;
  }
  const response = await api.post('/api/copilot/chat', payload, { signal });
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
