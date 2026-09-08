import { useState } from 'react';

import api from '../utils/api';
import translationService from '../services/translationService';
import notificationService from '../services/notificationService';
import { FEATURES } from '../config/features';
import {
  TRANSLATION_RECOVERY_ACTIONS,
  isRecoveryActionAllowed,
  useTranslationRecovery,
} from './useTranslationRecovery';
import {
  buildTranslationDetails,
  buildTranslationPayload,
} from '../utils/initialTranslation';
import { useStaleTranslationContextRetry } from './useStaleTranslationContextRetry';

export function useInitialTranslationFlow({
  config,
  notificationStyle,
  selectedProject,
  selectedProjectId,
  setActive,
  setIsProcessing,
  setTaskId,
  setTranslationDetails,
  setStatus,
  t = (_key, fallback) => fallback,
  resumeEnabled = FEATURES.ENABLE_CHECKPOINT_RESUME,
}) {
  const [resumeModalOpen, setResumeModalOpen] = useState(false);
  const [pendingFormValues, setPendingFormValues] = useState(null);
  const [referencePromptOpen, setReferencePromptOpen] = useState(false);
  const [pendingReferenceValues, setPendingReferenceValues] = useState(null);
  const recoveryController = useTranslationRecovery(selectedProjectId, {
    apiClient: api,
    autoLoad: resumeEnabled,
  });

  const applyRecoveryTask = (response) => {
    const task = response?.task || response;
    const taskId = task?.task_id;
    if (!taskId) {
      throw new Error('The recovery action did not return a task ID.');
    }
    setTaskId(taskId);
    setStatus(task.status || 'processing');
    setIsProcessing(true);
    setActive(2);
  };
  const staleContext = useStaleTranslationContextRetry();

  const startTranslation = async (values, { skipReferenceCheck = false } = {}) => {
    const effectiveValues = resumeEnabled ? values : { ...values, use_resume: false };
    if (!selectedProjectId) {
      notificationService.error('Please select a project first.', notificationStyle);
      return;
    }

    if (
      !skipReferenceCheck
      && effectiveValues.reference_reuse_enabled !== false
      && !effectiveValues.reference_localization_path
    ) {
      try {
        const response = await translationService.getReferenceLibraryStatus();
        const gameId = selectedProject?.game_id;
        const available = response.data?.libraries?.some(
          (library) => library.game_id === gameId && library.available,
        );
        if (!available) {
          setPendingReferenceValues(effectiveValues);
          setReferencePromptOpen(true);
          return;
        }
      } catch (error) {
        console.warn('Failed to check reference library status; continuing without prompt.', error);
      }
    }

    setTranslationDetails(buildTranslationDetails(effectiveValues, selectedProject, config.languages));

    const payload = buildTranslationPayload(effectiveValues, selectedProjectId, selectedProject);

    setTaskId(null);
    setStatus('pending');
    setActive(2);
    setIsProcessing(true);

    const onSuccess = async (response) => {
      applyRecoveryTask(response.data);
      if (response.data.warning?.code === 'project_context_degraded') {
        notificationService.info(
          t('initial_translation_context_degraded', 'Project archive was skipped; translation will continue with glossaries.'),
          notificationStyle,
        );
      } else {
        notificationService.success(t('initial_translation_started', 'Translation started!'), notificationStyle);
      }
      setStatus('processing');
      setIsProcessing(true);
      setActive(2);
    };
    const onError = (error) => {
      const detail = error?.response?.data?.detail;
      const errorCode = typeof detail === 'object' ? detail?.code : null;
      const message = errorCode === 'duplicate_task'
        ? t('initial_translation_duplicate_task', 'This project already has a translation task in progress.')
        : t('initial_translation_start_failed', 'Failed to start translation.');
      notificationService.error(message, notificationStyle);
      console.error('Translate API error:', error);
      setTaskId(null);
      setIsProcessing(false);
      setStatus('failed');
      setActive(1);
    };
    await staleContext.submit({
      payload,
      request: (nextPayload) => api.post('/api/translate/start', nextPayload),
      onSuccess,
      onError,
      onCancel: () => {
        setTaskId(null);
        setIsProcessing(false);
        setStatus(null);
        setActive(1);
      },
    });
  };

  const continueWithoutReference = async () => {
    if (!pendingReferenceValues) return;
    const values = {
      ...pendingReferenceValues,
      reference_reuse_enabled: false,
      reference_localization_path: '',
    };
    setReferencePromptOpen(false);
    setPendingReferenceValues(null);
    await startTranslation(values, { skipReferenceCheck: true });
  };

  const handleStartClick = async (values) => {
    if (!resumeEnabled) {
      return startTranslation({ ...values, use_resume: false });
    }

    if (!selectedProjectId) {
      return;
    }

    try {
      const recovery = await recoveryController.refresh();
      if (recovery?.checkpoint?.available
        && isRecoveryActionAllowed(recovery, TRANSLATION_RECOVERY_ACTIONS.RESUME)) {
        setPendingFormValues(values);
        setResumeModalOpen(true);
      } else {
        await startTranslation({ ...values, use_resume: false });
      }
    } catch (error) {
      console.error('Failed to load translation recovery:', error);
      await startTranslation({ ...values, use_resume: false });
    }
  };

  const handleResume = async () => {
    setResumeModalOpen(false);
    try {
      const response = await recoveryController.resume();
      applyRecoveryTask(response);
    } catch {
      notificationService.error('Failed to resume translation.', notificationStyle);
      setTaskId(null);
      setIsProcessing(false);
      setStatus('failed');
      setActive(1);
    }
  };

  const handleStartOver = async () => {
    setResumeModalOpen(false);
    if (!pendingFormValues) {
      return;
    }

    try {
      const response = await recoveryController.startOver();
      applyRecoveryTask(response);
    } catch (error) {
      notificationService.error('Failed to start over.', notificationStyle);
      console.error(error);
    }
  };

  const handleClearCheckpoint = async () => {
    try {
      await recoveryController.clearCheckpoint();
      notificationService.success(
        t('translation_checkpoint_cleared', 'Saved checkpoint cleared.'),
        notificationStyle,
      );
    } catch (error) {
      notificationService.error(
        t('translation_checkpoint_clear_failed', 'Failed to clear the saved checkpoint.'),
        notificationStyle,
      );
      console.error(error);
      throw error;
    }
  };

  return {
    checkpointInfo: recoveryController.recovery,
    checkpointActionPending: recoveryController.pendingAction,
    handleClearCheckpoint,
    handleResume,
    handleStartClick,
    handleStartOver,
    resumeModalOpen,
    referencePromptOpen,
    continueWithoutReference,
    setReferencePromptOpen,
    setResumeModalOpen,
    staleContext,
  };
}
