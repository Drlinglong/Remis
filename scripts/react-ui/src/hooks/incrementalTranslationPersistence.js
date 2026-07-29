import { INCREMENTAL_STATE_STORAGE_KEY } from './incrementalTranslationPayload';

export const buildIncrementalStateSnapshot = ({
  active,
  archiveInfo,
  batchSizeLimit,
  checkpointFound,
  checkpointInfo,
  completionSource,
  concurrencyLimit,
  currentTaskId,
  currentTaskMode,
  customSourcePath,
  embeddedWorkshopBatchSize,
  embeddedWorkshopConcurrency,
  embeddedWorkshopEnabled,
  embeddedWorkshopFollowPrimary,
  embeddedWorkshopModel,
  embeddedWorkshopProvider,
  embeddedWorkshopRpm,
  errorKey,
  executing,
  finalSummary,
  loading,
  logs,
  progress,
  progressInfo,
  rpmLimit,
  scanResults,
  selectedLangs,
  selectedModel,
  selectedProject,
  selectedProvider,
  showResumeDetails,
  showWorkshopSettings,
  useResume,
}) => ({
  active,
  loading,
  selectedProject,
  selectedProvider,
  selectedModel,
  customSourcePath,
  selectedLangs,
  batchSizeLimit,
  concurrencyLimit,
  rpmLimit,
  archiveInfo,
  scanResults,
  errorKey,
  executing,
  progress,
  progressInfo,
  logs,
  finalSummary,
  checkpointFound,
  checkpointInfo,
  useResume,
  showResumeDetails,
  embeddedWorkshopEnabled,
  embeddedWorkshopFollowPrimary,
  embeddedWorkshopProvider,
  embeddedWorkshopModel,
  embeddedWorkshopBatchSize,
  embeddedWorkshopConcurrency,
  embeddedWorkshopRpm,
  showWorkshopSettings,
  currentTaskId,
  currentTaskMode,
  completionSource,
});

export const readIncrementalStateSnapshot = (storage = sessionStorage) => {
  const rawState = storage.getItem(INCREMENTAL_STATE_STORAGE_KEY);
  return rawState ? JSON.parse(rawState) : null;
};

export const writeIncrementalStateSnapshot = (snapshot, storage = sessionStorage) => {
  storage.setItem(INCREMENTAL_STATE_STORAGE_KEY, JSON.stringify(snapshot));
};

export const resolvePersistedProject = (persistedProject, projects = []) => {
  if (!persistedProject?.project_id) return null;
  return projects.find((project) => project.project_id === persistedProject.project_id) || persistedProject;
};

export const resolveInFlightIncrementalTaskId = ({
  currentTaskId,
  executionInFlight = false,
  preScanInFlight = false,
} = {}) => (
  currentTaskId && (executionInFlight || preScanInFlight)
    ? currentTaskId
    : null
);

export const applyIncrementalStateSnapshot = (snapshot, setters, refs = {}) => {
  if (!snapshot) return;

  const matchedProject = resolvePersistedProject(snapshot.selectedProject, refs.projects);

  if (matchedProject) setters.setSelectedProject(matchedProject);
  if (typeof snapshot.active === 'number') setters.setActive(snapshot.active);
  if (typeof snapshot.loading === 'boolean') setters.setLoading(snapshot.loading);
  if (snapshot.customSourcePath) setters.setCustomSourcePath(snapshot.customSourcePath);
  if (Array.isArray(snapshot.selectedLangs)) setters.setSelectedLangs(snapshot.selectedLangs);
  if (snapshot.archiveInfo) setters.setArchiveInfo(snapshot.archiveInfo);
  if (snapshot.scanResults) setters.setScanResults(snapshot.scanResults);
  if (snapshot.errorKey) setters.setErrorKey(snapshot.errorKey);
  if (typeof snapshot.executing === 'boolean') setters.setExecuting(snapshot.executing);
  if (typeof snapshot.progress === 'number') setters.setProgress(snapshot.progress);
  if (snapshot.progressInfo) setters.setProgressInfo(snapshot.progressInfo);
  if (Array.isArray(snapshot.logs)) setters.setLogs(snapshot.logs);
  if (snapshot.finalSummary) setters.setFinalSummary(snapshot.finalSummary);
  if (typeof snapshot.checkpointFound === 'boolean') setters.setCheckpointFound(snapshot.checkpointFound);
  if (snapshot.checkpointInfo) setters.setCheckpointInfo(snapshot.checkpointInfo);
  if (typeof snapshot.useResume === 'boolean') setters.setUseResume(snapshot.useResume);
  if (typeof snapshot.showResumeDetails === 'boolean') setters.setShowResumeDetails(snapshot.showResumeDetails);
  if (typeof snapshot.embeddedWorkshopEnabled === 'boolean') setters.setEmbeddedWorkshopEnabled(snapshot.embeddedWorkshopEnabled);
  if (typeof snapshot.embeddedWorkshopFollowPrimary === 'boolean') setters.setEmbeddedWorkshopFollowPrimary(snapshot.embeddedWorkshopFollowPrimary);
  if (snapshot.embeddedWorkshopProvider) setters.setEmbeddedWorkshopProvider(snapshot.embeddedWorkshopProvider);
  if (snapshot.embeddedWorkshopModel) setters.setEmbeddedWorkshopModel(snapshot.embeddedWorkshopModel);
  if (snapshot.embeddedWorkshopBatchSize) setters.setEmbeddedWorkshopBatchSize(String(snapshot.embeddedWorkshopBatchSize));
  if (snapshot.embeddedWorkshopConcurrency) setters.setEmbeddedWorkshopConcurrency(String(snapshot.embeddedWorkshopConcurrency));
  if (snapshot.embeddedWorkshopRpm) setters.setEmbeddedWorkshopRpm(String(snapshot.embeddedWorkshopRpm));
  if (typeof snapshot.showWorkshopSettings === 'boolean') setters.setShowWorkshopSettings(snapshot.showWorkshopSettings);
  if (snapshot.currentTaskId) setters.setCurrentTaskId(snapshot.currentTaskId);
  if (snapshot.currentTaskMode) setters.setCurrentTaskMode(snapshot.currentTaskMode);
  if (snapshot.completionSource && refs.completionSourceRef) {
    refs.completionSourceRef.current = snapshot.completionSource;
  }
};
