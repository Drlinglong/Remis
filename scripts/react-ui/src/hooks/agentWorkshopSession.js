export const AGENT_WORKSHOP_STORAGE_KEY = 'agent_workshop_state_v2';

export const createAgentWorkshopSnapshot = (state, override = {}) => ({
  active: state.active,
  selectedProjectId: state.selectedProjectId,
  archiveInfo: state.archiveInfo,
  projectHistory: state.projectHistory,
  issues: state.issues,
  fixedIssues: state.fixedIssues,
  isCached: state.isCached,
  searchQuery: state.searchQuery,
  gameFilter: state.gameFilter,
  selectedProvider: state.selectedProvider,
  selectedModel: state.selectedModel,
  batchSizeLimit: state.batchSizeLimit,
  concurrencyLimit: state.concurrencyLimit,
  rpmLimit: state.rpmLimit,
  executing: state.executing,
  progress: state.progress,
  executionLogs: state.executionLogs,
  executionStats: state.executionStats,
  ...override,
});

export const readAgentWorkshopSnapshot = (storage = sessionStorage) => {
  try {
    const rawState = storage.getItem(AGENT_WORKSHOP_STORAGE_KEY);
    return rawState ? JSON.parse(rawState) : {};
  } catch (error) {
    console.error('Failed to read Agent Workshop session state:', error);
    return {};
  }
};

export const writeAgentWorkshopSnapshot = (snapshot, storage = sessionStorage) => {
  storage.setItem(AGENT_WORKSHOP_STORAGE_KEY, JSON.stringify(snapshot));
};

export const clearAgentWorkshopSnapshot = (storage = sessionStorage) => {
  storage.removeItem(AGENT_WORKSHOP_STORAGE_KEY);
};

export const appendAgentWorkshopLogSnapshot = (message, storage = sessionStorage) => {
  const current = readAgentWorkshopSnapshot(storage);
  const nextLogs = [
    ...(Array.isArray(current.executionLogs) ? current.executionLogs : []),
    `[${new Date().toLocaleTimeString()}] ${message}`,
  ];
  writeAgentWorkshopSnapshot({ ...current, executionLogs: nextLogs }, storage);
  return nextLogs;
};
