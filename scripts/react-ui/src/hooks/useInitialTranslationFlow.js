import { useState } from 'react';

import api from '../utils/api';
import translationService from '../services/translationService';
import notificationService from '../services/notificationService';
import {
  buildTranslationDetails,
  buildTranslationPayload,
  getTargetLangCodes,
} from '../utils/initialTranslation';

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
}) {
  const [resumeModalOpen, setResumeModalOpen] = useState(false);
  const [checkpointInfo, setCheckpointInfo] = useState(null);
  const [pendingFormValues, setPendingFormValues] = useState(null);
  const [referencePromptOpen, setReferencePromptOpen] = useState(false);
  const [pendingReferenceValues, setPendingReferenceValues] = useState(null);

  const startTranslation = async (values, { skipReferenceCheck = false } = {}) => {
    if (!selectedProjectId) {
      notificationService.error('Please select a project first.', notificationStyle);
      return;
    }

    if (
      !skipReferenceCheck
      && values.reference_reuse_enabled !== false
      && !values.reference_localization_path
    ) {
      try {
        const response = await translationService.getReferenceLibraryStatus();
        const gameId = selectedProject?.game_id;
        const available = response.data?.libraries?.some(
          (library) => library.game_id === gameId && library.available,
        );
        if (!available) {
          setPendingReferenceValues(values);
          setReferencePromptOpen(true);
          return;
        }
      } catch (error) {
        console.warn('Failed to check reference library status; continuing without prompt.', error);
      }
    }

    setTranslationDetails(buildTranslationDetails(values, selectedProject, config.languages));

    const payload = buildTranslationPayload(values, selectedProjectId, selectedProject);

    setTaskId(null);
    setStatus('pending');
    setActive(2);
    setIsProcessing(true);

    try {
      const response = await api.post('/api/translate/start', payload);
      setTaskId(response.data.task_id);
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
    } catch (error) {
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
    }
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
    if (!values.use_resume) {
      return startTranslation(values);
    }

    const modName = selectedProject?.label;
    if (!modName) {
      return;
    }

    try {
      const response = await api.post('/api/translation/checkpoint-status', {
        mod_name: modName,
        target_lang_codes: getTargetLangCodes(values),
      });

      if (response.data.exists) {
        setCheckpointInfo(response.data);
        setPendingFormValues(values);
        setResumeModalOpen(true);
      } else {
        await startTranslation(values);
      }
    } catch (error) {
      console.error('Failed to check checkpoint:', error);
      await startTranslation(values);
    }
  };

  const handleResume = async () => {
    setResumeModalOpen(false);
    if (pendingFormValues) {
      await startTranslation(pendingFormValues);
    }
  };

  const handleStartOver = async () => {
    setResumeModalOpen(false);
    if (!pendingFormValues) {
      return;
    }

    const modName = selectedProject?.label;
    try {
      await api.delete('/api/translation/checkpoint', {
        data: {
          mod_name: modName,
          target_lang_codes: getTargetLangCodes(pendingFormValues),
        },
      });
      notificationService.success('Checkpoint cleared. Starting fresh.', notificationStyle);
      await startTranslation(pendingFormValues);
    } catch (error) {
      notificationService.error('Failed to clear checkpoint.', notificationStyle);
      console.error(error);
    }
  };

  return {
    checkpointInfo,
    handleResume,
    handleStartClick,
    handleStartOver,
    resumeModalOpen,
    referencePromptOpen,
    continueWithoutReference,
    setReferencePromptOpen,
    setResumeModalOpen,
  };
}
