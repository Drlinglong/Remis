import { useCallback } from 'react';

import notificationService from '../services/notificationService';
import translationService from '../services/translationService';
import { buildIncrementalUpdatePayload, getArchivedTargetLanguages } from './incrementalTranslationPayload';


export function useIncrementalPreScan(options) {
  const {
    archiveInfo, checkReferenceLibrary, connectWebSocket, executionInFlightRef,
    loading, executing, notificationStyle, preScanInFlightRef, referenceReuseBypassed,
    selectedLangs, selectedProject, setActive, setConflictingTaskId, setCurrentTaskId,
    setCurrentTaskMode, setLoading, setLogs, setProgress, setProgressInfo, setScanResults,
    t,
  } = options;

  return useCallback(async (actionOptions = {}) => {
    const busy = loading || executing || preScanInFlightRef.current || executionInFlightRef.current;
    if (!selectedProject || !options.customSourcePath || busy) return;
    const skipReferenceReuse = actionOptions?.skipReferenceReuse === true;
    const targetLangCodes = selectedLangs.length > 0
      ? selectedLangs
      : getArchivedTargetLanguages(archiveInfo);
    if (targetLangCodes.length === 0) {
      notificationService.error(t('incremental_translation.no_archived_target_languages'), notificationStyle);
      return;
    }
    if (await checkReferenceLibrary({ skip: skipReferenceReuse })) return;

    preScanInFlightRef.current = true;
    try {
      setLoading(true);
      setProgress(0);
      setProgressInfo({
        percent: 0,
        stage_code: 'initializing',
        stage: t('incremental_translation.progress_stage_initializing'),
      });
      setLogs([t('incremental_translation.pre_scan_bootstrap_log')]);
      const payload = buildIncrementalUpdatePayload({
        ...options,
        dryRun: true,
        projectId: selectedProject.project_id,
        referenceReuseEnabled: options.referenceReuseEnabled
          && !referenceReuseBypassed
          && !skipReferenceReuse,
        targetLangCodes,
      });
      const response = await translationService.startIncrementalUpdate(
        selectedProject.project_id,
        payload,
      );
      const taskId = response.data.task_id;
      if (taskId) {
        setConflictingTaskId(null);
        setCurrentTaskId(taskId);
        setCurrentTaskMode('pre_scan');
        connectWebSocket(taskId, true);
        return;
      }
      if (response.data.status === 'warning') {
        notificationService.info(
          response.data.message || t('incremental_translation.no_files_warning'),
          notificationStyle,
        );
      }
      setScanResults({
        ...(response.data.summary || {}),
        file_summaries: response.data.file_summaries || [],
        telemetry: response.data.telemetry || null,
      });
      setActive(2);
      setLoading(false);
    } catch (error) {
      console.error('Pre-scan error:', error);
      const detail = error?.response?.data?.detail;
      const duplicateTaskId = detail?.code === 'duplicate_task' ? detail.existing_task_id : null;
      if (duplicateTaskId) {
        setConflictingTaskId(duplicateTaskId);
        setCurrentTaskId(duplicateTaskId);
        notificationService.info(t('incremental_translation.conflicting_task_notice'), notificationStyle);
      } else {
        notificationService.error(t('notification.error_generic'), notificationStyle);
      }
      setLoading(false);
      preScanInFlightRef.current = false;
    }
  }, [
    archiveInfo, checkReferenceLibrary, connectWebSocket, executing, executionInFlightRef,
    loading, notificationStyle, options, preScanInFlightRef, referenceReuseBypassed,
    selectedLangs, selectedProject, setActive, setConflictingTaskId, setCurrentTaskId,
    setCurrentTaskMode, setLoading, setLogs, setProgress, setProgressInfo, setScanResults, t,
  ]);
}
