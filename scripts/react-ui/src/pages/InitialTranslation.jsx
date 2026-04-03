import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useNotification } from '../context/NotificationContext';
import { useTranslationContext } from '../context/TranslationContext';
import { useForm } from '@mantine/form';
import {
  Stepper,
  Text,
  Card,
  Container,
  Stack,
  Loader,
  Box,
} from '@mantine/core';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTutorial } from '../context/TutorialContext';
import '../App.css';
import layoutStyles from '../components/layout/Layout.module.css';

import ConfigStep from '../components/initialTranslation/ConfigStep';
import ProjectSelectionStep from '../components/initialTranslation/ProjectSelectionStep';
import ResumeCheckpointModal from '../components/initialTranslation/ResumeCheckpointModal';
import TaskRunner from '../components/TaskRunner';
import { useInitialTranslationFlow } from '../hooks/useInitialTranslationFlow';
import { useInitialTranslationPageData } from '../hooks/useInitialTranslationPageData';
import { usePersistentState } from '../hooks/usePersistentState';
import {
  getTargetLangCodes,
  buildModelOptions,
  filterProjects,
  findLanguageByCode,
  findProjectById,
} from '../utils/initialTranslation';
import api from '../utils/api';

const InitialTranslation = () => {
  const { t } = useTranslation();
  const { notificationStyle } = useNotification();
  const {
    activeStep: active,
    setActiveStep: setActive,
    setTaskId,
    taskStatus,
    setIsProcessing,
    translationDetails,
    setTranslationDetails,
    selectedProjectId,
    setSelectedProjectId,
    resetTranslation
  } = useTranslationContext();
  const { setPageContext } = useTutorial();

  // Project State
  const [searchQuery, setSearchQuery] = usePersistentState('trans_search_query', '');
  const [gameFilter, setGameFilter] = usePersistentState('trans_game_filter', 'all');
  const navigate = useNavigate();
  const location = useLocation();

  const [status, setStatus] = useState(null);
  const [availableGlossaries, setAvailableGlossaries] = useState([]);
  const [checkpointHintInfo, setCheckpointHintInfo] = useState(null);
  const checkpointHintRequestRef = useRef(0);

  const form = useForm({
    initialValues: {
      source_lang_code: 'en',
      target_lang_codes: ['zh-CN'], // Default to array
      api_provider: 'gemini',
      model_name: 'gemini-pro',
      mod_context: '',
      selected_glossary_ids: [],
      use_main_glossary: true,
      clean_source: false,
      use_resume: true,
      embedded_workshop_enabled: true,
      embedded_workshop_follow_primary_settings: true,
      embedded_workshop_api_provider: '',
      embedded_workshop_api_model: '',
      embedded_workshop_batch_size_limit: '10',
      embedded_workshop_concurrency_limit: '1',
      embedded_workshop_rpm_limit: '40',
      // Custom Language Fields
      custom_name: '',
      custom_key: 'l_english',
      custom_prefix: 'Custom-',
      english_disguise: false,
      disguise_target_key: 'l_english',
    },
    validate: {
      api_provider: (value) => (value ? null : t('form_validation_required')),
      custom_name: (value, values) => (values.english_disguise && !value ? 'Required' : null),
      custom_key: (value, values) => (values.english_disguise && !value ? 'Required' : null),
      custom_prefix: (value, values) => (values.english_disguise && !value ? 'Required' : null),
      target_lang_codes: (value, values) => (!values.english_disguise && value.length === 0 ? 'Select at least one language' : null),
    },
  });

  const { availableModels, config, projects } = useInitialTranslationPageData({
    form,
    notificationStyle,
    t,
  });

  const selectedProject = findProjectById(projects, selectedProjectId);
  const filteredProjects = filterProjects(projects, gameFilter, searchQuery);
  const checkpointTargetSignature = form.values.english_disguise
    ? 'custom'
    : form.values.target_lang_codes.join('|');

  // Handle projectId from URL
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const projectIdFromUrl = params.get('projectId');
    if (projectIdFromUrl && projects.length > 0) {
      if (projectIdFromUrl !== selectedProjectId || active === 0) {
        handleProjectSelect(projectIdFromUrl);
      }
    }
  }, [location.search, active, projects, selectedProjectId]);

  useEffect(() => {
    const nextPageContext = `translation-step-${active}`;
    setPageContext((prev) => (prev === nextPageContext ? prev : nextPageContext));
  }, [active, setPageContext]);

  useEffect(() => {
    if (active !== 1 || !selectedProject?.label) {
      setCheckpointHintInfo(null);
      return;
    }

    const targetLangCodes = getTargetLangCodes(form.values);
    if (!targetLangCodes.length) {
      setCheckpointHintInfo(null);
      return;
    }

    const requestId = checkpointHintRequestRef.current + 1;
    checkpointHintRequestRef.current = requestId;

    api.post('/api/translation/checkpoint-status', {
      mod_name: selectedProject.label,
      target_lang_codes: targetLangCodes,
    })
      .then((response) => {
        if (checkpointHintRequestRef.current !== requestId) {
          return;
        }
        setCheckpointHintInfo(response.data?.exists ? response.data : null);
      })
      .catch((error) => {
        if (checkpointHintRequestRef.current !== requestId) {
          return;
        }
        console.error('Failed to check checkpoint hint:', error);
        setCheckpointHintInfo(null);
      });
  }, [
    active,
    checkpointTargetSignature,
    selectedProject?.label,
  ]);

  useEffect(() => {
    if (form.values.embedded_workshop_follow_primary_settings) {
      return;
    }

    const providerValue = form.values.embedded_workshop_api_provider;
    if (!providerValue) {
      return;
    }

    const models = buildModelOptions(providerValue, config.api_providers);
    const hasCurrentModel = models.some((item) => item.value === form.values.embedded_workshop_api_model);
    if (!hasCurrentModel && models.length > 0) {
      form.setFieldValue('embedded_workshop_api_model', models[0].value);
    }
  }, [
    config.api_providers,
    form,
    form.values.embedded_workshop_api_model,
    form.values.embedded_workshop_api_provider,
    form.values.embedded_workshop_follow_primary_settings,
  ]);

  // Polling Logic removed from here (now in TranslationContext)

  const {
    checkpointInfo,
    handleResume,
    handleStartClick,
    handleStartOver,
    resumeModalOpen,
    setResumeModalOpen,
  } = useInitialTranslationFlow({
    config,
    notificationStyle,
    selectedProject,
    selectedProjectId,
    setActive,
    setIsProcessing,
    setStatus,
    setTaskId,
    setTranslationDetails,
  });

  const handleProjectSelect = (projectId) => {
    const project = findProjectById(projects, projectId);
    if (project) {
      setSelectedProjectId(projectId);
      // Auto-set source language from project metadata if available
      if (project.source_language) {
        const langConfig = findLanguageByCode(config.languages, project.source_language);
        if (langConfig) {
          form.setFieldValue('source_lang_code', langConfig.code);
        }
      }
      setActive(1); // Auto-advance to configuration
    }
  };

  const handleBack = () => {
    if (active > 0) {
      setActive(active - 1);
    }
  };

  return (
    <Container fluid py="xl" h="100vh" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', maxWidth: '100%', width: '100%' }}>
      <Box style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
        <Stack gap="xl" pb="xl" w="100%">
          <Box w="100%">
            <Stepper active={active} onStepClick={setActive} allowNextStepsSelect={false}>
              <Stepper.Step label={t('translation_page.title')} description={t('translation_page.subtitle')}>
              </Stepper.Step>
              <Stepper.Step label={t('initial_translation_step_configure')} description={t('initial_translation_step_configure_desc', 'Settings')}>
              </Stepper.Step>
              <Stepper.Step label={t('initial_translation_step_translate')} description={t('initial_translation_step_translate_desc', 'Processing')}>
              </Stepper.Step>
              <Stepper.Step label={t('initial_translation_step_finish')} description={t('initial_translation_step_download_desc')}>
              </Stepper.Step>
            </Stepper>
          </Box>

          {active === 0 && (
            <ProjectSelectionStep
              config={config}
              filteredProjects={filteredProjects}
              gameFilter={gameFilter}
              navigate={navigate}
              onProjectSelect={handleProjectSelect}
              projects={projects}
              searchQuery={searchQuery}
              selectedProjectId={selectedProjectId}
              setGameFilter={setGameFilter}
              setSearchQuery={setSearchQuery}
              t={t}
            />
          )}
          {
            active === 1 && (
              <ConfigStep
                availableGlossaries={availableGlossaries}
                availableModels={availableModels}
                checkpointHintInfo={checkpointHintInfo}
                config={config}
                embeddedWorkshopModels={buildModelOptions(
                  form.values.embedded_workshop_follow_primary_settings
                    ? form.values.api_provider
                    : form.values.embedded_workshop_api_provider,
                  config.api_providers,
                )}
                form={form}
                onBack={handleBack}
                onSubmit={handleStartClick}
                selectedProject={selectedProject}
                selectedProjectId={selectedProjectId}
                t={t}
              />
            )
          }

          {
            (active === 2 || active === 3) && (
              <Card withBorder padding="xl" radius="md" className={layoutStyles.glassCard}>
                {taskStatus ? (
                  <div id="task-runner-container">
                    <TaskRunner
                      task={taskStatus}
                      onComplete={() => navigate(`/project/${selectedProjectId}/proofread`)}
                      onRestart={() => {
                        resetTranslation();
                        setStatus(null);
                      }}
                      onDashboard={() => navigate('/project-management')}
                      translationDetails={translationDetails}
                    />
                  </div>
                ) : (
                  <Stack align="center" p="xl">
                    <Loader size="xl" type="dots" />
                    <Text size="lg" mt="md">Initializing...</Text>
                  </Stack>
                )}
              </Card>
            )
          }
        </Stack >
      </Box>

      <ResumeCheckpointModal
        checkpointInfo={checkpointInfo}
        onClose={() => setResumeModalOpen(false)}
        onResume={handleResume}
        onStartOver={handleStartOver}
        opened={resumeModalOpen}
        t={t}
      />
    </Container >
  );
};

export default InitialTranslation;
