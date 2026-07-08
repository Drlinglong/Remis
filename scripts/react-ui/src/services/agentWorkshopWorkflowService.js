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

export const scanAgentWorkshopProject = async (projectId, sidecarPath = null) => {
  const response = await workshopService.scanProject(projectId, sidecarPath);
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

export const startAgentWorkshopFixRun = async ({
  batchSizeLimit,
  concurrencyLimit,
  issues,
  projectId,
  rpmLimit,
  selectedModel,
  selectedProvider,
}) => {
  const response = await workshopService.startFixRun({
    project_id: projectId,
    api_provider: selectedProvider,
    api_model: selectedModel,
    batch_size_limit: Number(batchSizeLimit) || (isLocalAgentWorkshopProvider(selectedProvider) ? 3 : 10),
    concurrency_limit: Number(concurrencyLimit) || 1,
    rpm_limit: Number(rpmLimit) || 40,
    max_retries: 3,
    issues,
  });

  return response.data;
};

export const getAgentWorkshopRunStatus = async (taskId) => {
  const response = await projectService.getTaskStatus(taskId);
  return response.data;
};
