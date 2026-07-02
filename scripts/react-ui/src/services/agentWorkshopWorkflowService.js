import configService from './configService';
import projectService from './projectService';
import workshopService from './workshopService';
import { normalizeArrayPayload } from '../utils/payload';

export const LOCAL_AGENT_WORKSHOP_PROVIDERS = [
  'ollama',
  'lm_studio',
  'vllm',
  'koboldcpp',
  'oobabooga',
  'text-generation-webui',
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export const buildAgentWorkshopModelOptions = (provider = {}) => [
  ...(provider?.available_models || []),
  ...(provider?.custom_models || []),
];

export const isLocalAgentWorkshopProvider = (providerValue) =>
  LOCAL_AGENT_WORKSHOP_PROVIDERS.includes(providerValue || '');

export const loadAgentWorkshopBootstrap = async () => {
  const [projectsRes, configRes] = await Promise.all([
    projectService.getActiveProjects(),
    configService.getConfig(),
  ]);

  return {
    projects: normalizeArrayPayload(projectsRes.data, ['projects', 'items', 'data', 'results']),
    providers: normalizeArrayPayload(configRes.data?.api_providers, ['items', 'data', 'results']),
  };
};

export const selectAgentWorkshopProvider = ({ providers, providerValue, preferredModel }) => {
  const selectedProvider = providerValue || providers[0]?.value || '';
  const provider = providers.find((item) => item.value === selectedProvider) || providers[0];
  const models = buildAgentWorkshopModelOptions(provider);

  return {
    selectedProvider,
    selectedModel: preferredModel || provider?.selected_model || models[0] || '',
    batchSizeLimit: isLocalAgentWorkshopProvider(selectedProvider) ? '3' : '10',
  };
};

export const loadAgentWorkshopProjectContext = async (projectId) => {
  const [archiveRes, historyRes] = await Promise.all([
    projectService.checkArchive(projectId),
    projectService.getProjectHistory(projectId),
  ]);

  return {
    archiveInfo: archiveRes.data || null,
    projectHistory: Array.isArray(historyRes.data) ? historyRes.data : [],
  };
};

export const scanAgentWorkshopProject = async (projectId) => {
  const response = await workshopService.scanProject(projectId);
  return normalizeArrayPayload(response.data, ['issues', 'items', 'data', 'results']);
};

export const requestAgentWorkshopIssueFix = async ({
  issue,
  projectId,
  selectedModel,
  selectedProvider,
}) => {
  const response = await workshopService.fixIssue({
    project_id: projectId,
    api_provider: selectedProvider,
    api_model: selectedModel,
    ...issue,
  });

  return response.data;
};

export const runAgentWorkshopFixBatches = async ({
  addExecutionLog,
  batchSizeLimit,
  concurrencyLimit,
  issues,
  onIssueFixed,
  onProgress,
  projectId,
  rpmLimit,
  selectedModel,
  selectedProvider,
}) => {
  const batchSize = Math.max(
    1,
    Number(batchSizeLimit) || (isLocalAgentWorkshopProvider(selectedProvider) ? 3 : 10)
  );
  const total = issues.length;
  const concurrency = Math.max(1, Number(concurrencyLimit) || 1);
  const rpm = Math.max(1, Number(rpmLimit) || 1);
  const intervalMs = Math.ceil(60000 / rpm);
  const snapshot = [...issues];
  const batches = Array.from({ length: Math.ceil(snapshot.length / batchSize) }, (_, index) =>
    snapshot.slice(index * batchSize, (index + 1) * batchSize)
  );
  const maxRetries = 3;
  const startedAt = Date.now();
  let nextBatchIndex = 0;
  let nextDispatchAt = Date.now();
  let completed = 0;
  let successCount = 0;
  let failedCount = 0;

  addExecutionLog(`Starting fix run for ${total} issue(s) in ${batches.length} batch(es) of up to ${batchSize}; max ${maxRetries} attempt(s) per batch.`);
  if (isLocalAgentWorkshopProvider(selectedProvider) && batchSize < 10) {
    addExecutionLog('Using smaller local batches to avoid context overflow on the selected local model.');
  }

  const claimBatch = async () => {
    if (nextBatchIndex >= batches.length) return null;
    const batchNumber = nextBatchIndex + 1;
    const batch = batches[nextBatchIndex++];
    const now = Date.now();
    const waitMs = Math.max(0, nextDispatchAt - now);
    nextDispatchAt = Math.max(now, nextDispatchAt) + intervalMs;
    if (waitMs > 0) await sleep(waitMs);
    return { batchNumber, batch };
  };

  const worker = async (workerId) => {
    while (true) {
      const claimed = await claimBatch();
      if (!claimed) return;

      const { batchNumber, batch } = claimed;
      addExecutionLog(`Worker ${workerId}: fixing batch ${batchNumber}/${batches.length} (${batch.length} issue(s), up to ${maxRetries} attempt(s))`);

      try {
        const response = await workshopService.fixBatch({
          project_id: projectId,
          api_provider: selectedProvider,
          api_model: selectedModel,
          max_retries: maxRetries,
          issues: batch,
        });
        const results = Array.isArray(response.data?.results) ? response.data.results : [];
        const attempts = Array.isArray(response.data?.attempts) ? response.data.attempts : [];

        attempts.forEach((attempt) => {
          const reflectionNote = attempt.used_reflection
            ? `, ${attempt.reflections_generated || 0} reflection(s)`
            : '';
          const message = attempt.message ? ` (${attempt.message})` : '';
          addExecutionLog(
            `Batch ${batchNumber} attempt ${attempt.attempt}/${attempt.max_retries}: ${attempt.active_count} active${reflectionNote}, ${attempt.fixed_count} fixed, ${attempt.remaining_count} remaining, ${attempt.status}.${message}`
          );
        });

        const fixedByKey = new Map(results.map((item) => [`${item.file_name}::${item.key}`, item]));
        batch.forEach((issue) => {
          const result = fixedByKey.get(`${issue.file_name}::${issue.key}`);
          if (result?.status === 'SUCCESS') {
            successCount += 1;
            onIssueFixed(issue, result);
          } else {
            failedCount += 1;
          }
        });

        addExecutionLog(`Batch ${batchNumber} completed: ${results.filter((item) => item.status === 'SUCCESS').length}/${batch.length} fixed.`);
      } catch (error) {
        failedCount += batch.length;
        addExecutionLog(`Batch ${batchNumber} failed: ${error?.response?.data?.detail || error.message}`);
      } finally {
        completed += batch.length;
        const stats = {
          total,
          completed,
          successCount,
          failedCount,
          durationMs: Date.now() - startedAt,
          batchSize,
          totalBatches: batches.length,
        };
        onProgress({
          percent: Math.round((completed / total) * 100),
          stats,
        });
      }
    }
  };

  await Promise.all(Array.from({ length: Math.min(concurrency, batches.length) }, (_, index) => worker(index + 1)));

  return {
    total,
    completed: total,
    successCount,
    failedCount,
    durationMs: Date.now() - startedAt,
    batchSize,
    totalBatches: batches.length,
  };
};
