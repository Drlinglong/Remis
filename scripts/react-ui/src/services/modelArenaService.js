import api from '../utils/api';
import configService from './configService';
import projectService from './projectService';
import { normalizeArrayPayload } from '../utils/payload';

const unwrapRunPayload = (payload) => payload?.run || payload?.data?.run || payload?.data || payload;

export const normalizeModelArenaRun = (payload) => {
  const run = unwrapRunPayload(payload);
  if (!run || typeof run !== 'object') return run;
  const outputs = Array.isArray(run.outputs) ? run.outputs : [];
  const votes = Array.isArray(run.votes) ? run.votes : [];
  return {
    ...run,
    samples: (run.samples || []).map((sample) => ({
      ...sample,
      outputs: [...(sample.outputs || outputs.filter(
        (output) => output.sample_id === sample.sample_id,
      ))].sort((left, right) => String(left.candidate_id || '').localeCompare(
          String(right.candidate_id || ''),
        )),
      vote: sample.vote || votes.find((vote) => vote.sample_id === sample.sample_id) || null,
    })),
  };
};

export const createModelArenaIdempotencyKey = (runId) => {
  const randomPart = globalThis.crypto?.randomUUID?.()
    || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `model-arena:${runId}:${randomPart}`;
};

export const buildModelArenaModelOptions = (provider = {}) => (
  Array.from(new Set([
    ...(provider.available_models || []),
    ...(provider.custom_models || []),
    provider.selected_model,
  ].filter(Boolean)))
);

export const loadModelArenaBootstrap = async () => {
  const [projectsResponse, configResponse, providerStatusResponse] = await Promise.all([
    projectService.getActiveProjects(),
    configService.getConfig(),
    api.get('/api/api-keys'),
  ]);
  const providerStatuses = normalizeArrayPayload(
    providerStatusResponse.data,
    ['providers', 'items', 'data', 'results'],
  );
  const statusById = new Map(providerStatuses.map((provider) => [provider.id, provider]));
  const providers = normalizeArrayPayload(
    configResponse.data?.api_providers,
    ['items', 'data', 'results'],
  ).map((provider) => {
    const status = statusById.get(provider.value || provider.id);
    return {
      ...provider,
      configured: status ? Boolean(status.is_keyless || status.has_key) : true,
    };
  });

  return {
    projects: normalizeArrayPayload(
      projectsResponse.data,
      ['projects', 'items', 'data', 'results'],
    ),
    providers,
    languages: configResponse.data?.languages || {},
  };
};

export const modelArenaService = {
  loadBootstrap: loadModelArenaBootstrap,

  async createRun(payload) {
    const response = await api.post('/api/model-arena/runs', payload);
    return normalizeModelArenaRun(response.data);
  },

  async resample(runId) {
    const response = await api.post(`/api/model-arena/runs/${encodeURIComponent(runId)}/resample`);
    return normalizeModelArenaRun(response.data);
  },

  async startRun(runId, idempotencyKey = createModelArenaIdempotencyKey(runId)) {
    const response = await api.post(
      `/api/model-arena/runs/${encodeURIComponent(runId)}/start`,
      {
        confirmed_model_calls: true,
        idempotency_key: idempotencyKey,
      },
    );
    return normalizeModelArenaRun(response.data);
  },

  async getRun(runId) {
    const response = await api.get(`/api/model-arena/runs/${encodeURIComponent(runId)}`);
    return normalizeModelArenaRun(response.data);
  },

  async saveVote(runId, sampleId, vote) {
    const response = await api.put(
      `/api/model-arena/runs/${encodeURIComponent(runId)}/samples/${encodeURIComponent(sampleId)}/vote`,
      vote,
    );
    return response.data?.vote || response.data;
  },

  async completeRun(runId) {
    const response = await api.post(`/api/model-arena/runs/${encodeURIComponent(runId)}/complete`);
    return normalizeModelArenaRun(response.data);
  },

  async retryFailures(runId, idempotencyKey = createModelArenaIdempotencyKey(runId)) {
    const response = await api.post(
      `/api/model-arena/runs/${encodeURIComponent(runId)}/retry-failures`,
      {
        confirmed_model_calls: true,
        idempotency_key: idempotencyKey,
      },
    );
    return normalizeModelArenaRun(response.data);
  },

  async listRuns(params = {}) {
    const response = await api.get('/api/model-arena/runs', { params });
    return {
      runs: normalizeArrayPayload(response.data, ['runs', 'items', 'data', 'results'])
        .map(normalizeModelArenaRun),
      totalCount: Number(response.data?.total_count ?? response.data?.total ?? 0),
    };
  },

  async getExportPreview(runId, mode = 'evidence') {
    const response = await api.get(
      `/api/model-arena/runs/${encodeURIComponent(runId)}/export-preview`,
      { params: { mode } },
    );
    return response.data;
  },

  async exportRun(runId, mode = 'evidence') {
    const response = await api.post(
      `/api/model-arena/runs/${encodeURIComponent(runId)}/export`,
      { approved: true, mode },
      { responseType: 'blob' },
    );
    return response;
  },

  async openExportPath(path) {
    await api.post('/api/system/open_folder', { path });
  },

  async deleteRun(runId) {
    await api.delete(`/api/model-arena/runs/${encodeURIComponent(runId)}`, {
      params: { confirmed: true },
    });
  },
};

export default modelArenaService;
