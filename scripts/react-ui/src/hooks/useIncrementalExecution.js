import { useCallback } from 'react';

import notificationService from '../services/notificationService';
import translationService from '../services/translationService';
import { formatLocalizedDateTime, getResolvedInterfaceLocale } from '../utils/localizedDateTime';
import { buildIncrementalUpdatePayload, getArchivedTargetLanguages } from './incrementalTranslationPayload';


export function useIncrementalExecution(options) {
  const {
    addLog, archiveInfo, completionSourceRef, connectWebSocket, executing, executionInFlightRef,
    i18n, loading, notificationStyle, preScanInFlightRef, selectedLangs, selectedProject,
    referenceReuseBypassed,
    setActive, setConflictingTaskId, setCurrentTaskId, setCurrentTaskMode, setExecuting,
    setFinalSummary, setLogs, setProgress, setProgressInfo, t,
  } = options;

  return useCallback(async () => {
    const busy = loading || executing || preScanInFlightRef.current || executionInFlightRef.current;
    if (busy) return;
    const targetLangCodes = selectedLangs.length > 0
      ? selectedLangs
      : getArchivedTargetLanguages(archiveInfo);
    if (!selectedProject || targetLangCodes.length === 0) {
      notificationService.error(t('incremental_translation.no_archived_target_languages'), notificationStyle);
      return;
    }

    executionInFlightRef.current = true;
    setExecuting(true);
    setActive(3);
    setLogs([`[${formatLocalizedDateTime(Date.now(), getResolvedInterfaceLocale(i18n), {
      timeStyle: 'medium',
    })}] ${t('incremental_translation.status_ws_initializing')}`]);
    setFinalSummary(null);
    setProgress(0);
    setProgressInfo({
      percent: 0,
      stage_code: 'initializing',
      stage: t('incremental_translation.progress_stage_initializing'),
    });
    completionSourceRef.current = null;

    try {
      const response = await translationService.startIncrementalUpdate(
        selectedProject.project_id,
        buildIncrementalUpdatePayload({
          ...options,
          dryRun: false,
          projectId: selectedProject.project_id,
          referenceReuseEnabled: options.referenceReuseEnabled && !referenceReuseBypassed,
          targetLangCodes,
        }),
      );
      const taskId = response.data.task_id;
      if (!taskId) throw new Error(t('incremental_translation.task_id_missing'));

      setConflictingTaskId(null);
      setCurrentTaskId(taskId);
      setCurrentTaskMode('execution');
      connectWebSocket(taskId);
      notificationService.info(t('incremental_translation.background_task_notice'), notificationStyle);
    } catch (error) {
      const detail = error?.response?.data?.detail;
      const duplicateTaskId = detail?.code === 'duplicate_task' ? detail.existing_task_id : null;
      if (duplicateTaskId) {
        setConflictingTaskId(duplicateTaskId);
        setCurrentTaskId(duplicateTaskId);
        notificationService.info(t('incremental_translation.conflicting_task_notice'), notificationStyle);
      } else {
        addLog(t('incremental_translation.critical_error', { message: error.message }));
      }
      setExecuting(false);
      executionInFlightRef.current = false;
    }
  }, [
    addLog, archiveInfo, completionSourceRef, connectWebSocket, executing, executionInFlightRef,
    i18n, loading, notificationStyle, options, preScanInFlightRef, referenceReuseBypassed,
    selectedLangs, selectedProject,
    setActive, setConflictingTaskId, setCurrentTaskId, setCurrentTaskMode, setExecuting,
    setFinalSummary, setLogs, setProgress, setProgressInfo, t,
  ]);
}
