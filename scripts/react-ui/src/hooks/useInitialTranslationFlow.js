import { useState } from 'react';

import api from '../utils/api';
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
}) {
  const [resumeModalOpen, setResumeModalOpen] = useState(false);
  const [checkpointInfo, setCheckpointInfo] = useState(null);
  const [pendingFormValues, setPendingFormValues] = useState(null);

  const startTranslation = (values) => {
    if (!selectedProjectId) {
      notificationService.error('Please select a project first.', notificationStyle);
      return;
    }

    setTranslationDetails(buildTranslationDetails(values, selectedProject, config.languages));

    const payload = buildTranslationPayload(values, selectedProjectId);

    setTaskId(null);
    setStatus('pending');
    setActive(2);
    setIsProcessing(true);

    api.post('/api/translate/start', payload)
      .then((response) => {
        setTaskId(response.data.task_id);
        notificationService.success('Translation started!', notificationStyle);
        setStatus('processing');
        setIsProcessing(true);
        setActive(2);
      })
      .catch((error) => {
        notificationService.error('Failed to start translation.', notificationStyle);
        console.error('Translate API error:', error);
        setIsProcessing(false);
        setStatus('failed');
      });
  };

  const handleStartClick = async (values) => {
    if (!values.use_resume) {
      startTranslation(values);
      return;
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
        startTranslation(values);
      }
    } catch (error) {
      console.error('Failed to check checkpoint:', error);
      startTranslation(values);
    }
  };

  const handleResume = () => {
    setResumeModalOpen(false);
    if (pendingFormValues) {
      startTranslation(pendingFormValues);
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
      startTranslation(pendingFormValues);
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
    setResumeModalOpen,
  };
}
