import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNotification } from '../context/NotificationContextCore';
import { useTranslationContext } from '../context/TranslationContextCore';
import { useForm } from '@mantine/form';
import {
  Stepper,
  Text,
  Card,
  Container,
  Stack,
  Loader,
  Box,
  Button,
  Group,
} from '@mantine/core';
import { IconArrowLeft, IconPlayerPlay } from '@tabler/icons-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTutorial } from '../context/TutorialContextCore';
import '../App.css';
import layoutStyles from '../components/layout/Layout.module.css';
import controlsStyles from '../components/initialTranslation/InitialTranslationControls.module.css';

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

const formatModelSummary = (modelName = '') => {
  const knownModels = {
    'gemini-3-flash-preview': 'Gemini 3 Flash',
    'gemini-3-pro-preview': 'Gemini 3 Pro',
  };
  return knownModels[modelName] || modelName || '—';
};

const TranslationActionBar = ({
  checkpointHintInfo,
  config,
  form,
  onBack,
  providerStatusLoading = true,
  providerStatuses = [],
  selectedProjectId,
  t,
}) => {
  const targetCount = form.values.english_disguise
    ? 1
    : form.values.target_lang_codes.length;
  const selectedProvider = (config.api_providers || []).find(
    (provider) => provider.value === form.values.api_provider,
  );
  const selectedProviderStatus = providerStatuses.find(
    (provider) => provider.id === form.values.api_provider,
  );
  const missingApiKey = Boolean(
    selectedProviderStatus
    && !selectedProviderStatus.is_keyless
    && !selectedProviderStatus.has_key,
  );
  const hasModel = Boolean(form.values.model_name);
  const ready = Boolean(
    selectedProjectId
    && targetCount > 0
    && form.values.api_provider
    && hasModel
    && !missingApiKey,
  );

  let actionLabel = t('button_start_translation');
  if (form.submitting || providerStatusLoading) {
    actionLabel = t('initial_translation_start_checking');
  } else if (targetCount === 0) {
    actionLabel = t('initial_translation_start_choose_target');
  } else if (missingApiKey) {
    actionLabel = t('initial_translation_start_missing_api_key');
  } else if (!hasModel) {
    actionLabel = t('initial_translation_start_choose_model');
  } else if (form.values.use_resume && checkpointHintInfo?.exists) {
    actionLabel = t('initial_translation_continue');
  }

  return (
    <Box className={controlsStyles.actionBar} data-remis-surface="elevated">
      <Box className={controlsStyles.actionBarInner}>
        <Box className={controlsStyles.summaryLine}>
          <Text fw={700} c="var(--text-main)">
            {t('initial_translation_ready_title')}
          </Text>
          <Group gap={6} mt={2}>
            <Text size="sm" c={targetCount > 0 ? 'dimmed' : 'orange'} className={controlsStyles.summaryItem}>
              {t('initial_translation_summary_target_count', { count: targetCount })}
            </Text>
            <Text size="sm" c="dimmed">·</Text>
            <Text size="sm" c="dimmed" className={controlsStyles.summaryItem}>
              {formatModelSummary(form.values.model_name || selectedProvider?.selected_model)}
            </Text>
            <Text size="sm" c="dimmed">·</Text>
            <Text size="sm" c="dimmed" className={controlsStyles.summaryItem}>
              {form.values.use_main_glossary
                ? t('initial_translation_summary_main_glossary_on')
                : t('initial_translation_summary_main_glossary_off')}
            </Text>
            <Text size="sm" c="dimmed">·</Text>
            <Text size="sm" c="dimmed" className={controlsStyles.summaryItem}>
              {form.values.embedded_workshop_enabled
                ? t('initial_translation_summary_workshop_on')
                : t('initial_translation_summary_workshop_off')}
            </Text>
          </Group>
        </Box>

        <Group gap="sm" className={controlsStyles.actionButtons}>
          <Button
            onClick={onBack}
            leftSection={<IconArrowLeft size={16} />}
            variant="default"
          >
            {t('button_back')}
          </Button>
          <Button
            id="translation-start-btn"
            type="submit"
            form="initial-translation-config-form"
            size="md"
            leftSection={<IconPlayerPlay size={17} />}
            disabled={!ready || providerStatusLoading}
            loading={form.submitting}
          >
            {actionLabel}
          </Button>
        </Group>
      </Box>
    </Box>
  );
};

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

  const [, setStatus] = useState(null);
  const [checkpointHintInfo, setCheckpointHintInfo] = useState(null);
  const checkpointHintRequestRef = useRef(0);

  const form = useForm({
    initialValues: {
      source_lang_code: 'en',
      target_lang_codes: [],
      api_provider: 'gemini',
      model_name: 'gemini-pro',
      mod_context: '',
      selected_glossary_ids: [],
      use_main_glossary: true,
      clean_source: false,
      use_resume: false,
      translation_batch_size_limit: '',
      translation_concurrency_limit: '',
      translation_rpm_limit: '40',
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

  const {
    availableGlossaries,
    availableModels,
    config,
    projects,
    providerStatusLoading,
    providerStatuses,
  } = useInitialTranslationPageData({
    form,
    notificationStyle,
    selectedProjectId,
    t,
  });

  const selectedProject = findProjectById(projects, selectedProjectId);
  const filteredProjects = filterProjects(projects, gameFilter, searchQuery);
  const checkpointTargetSignature = form.values.english_disguise
    ? 'custom'
    : form.values.target_lang_codes.join('|');

  const handleProjectSelect = useCallback((projectId) => {
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
  }, [config.languages, form, projects, setActive, setSelectedProjectId]);

  useEffect(() => {
    if (!selectedProject?.source_language) {
      return;
    }

    const langConfig = findLanguageByCode(config.languages, selectedProject.source_language);
    if (!langConfig) {
      return;
    }

    if (form.values.source_lang_code !== langConfig.code) {
      form.setFieldValue('source_lang_code', langConfig.code);
    }

    if (!form.values.english_disguise && form.values.target_lang_codes.includes(langConfig.code)) {
      form.setFieldValue(
        'target_lang_codes',
        form.values.target_lang_codes.filter((code) => code !== langConfig.code),
      );
    }
  }, [
    config.languages,
    form,
    form.values.english_disguise,
    form.values.source_lang_code,
    form.values.target_lang_codes,
    selectedProject?.source_language,
  ]);

  // Handle projectId from URL
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const projectIdFromUrl = params.get('projectId');
    if (projectIdFromUrl && projects.length > 0) {
      if (projectIdFromUrl !== selectedProjectId || active === 0) {
        handleProjectSelect(projectIdFromUrl);
      }
    }
  }, [active, handleProjectSelect, location.search, projects.length, selectedProjectId]);

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
    form.values,
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

  const handleBack = () => {
    if (active > 0) {
      setActive(active - 1);
    }
  };

  return (
    <Container fluid pt="xl" px={0} h="100vh" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', maxWidth: '100%', width: '100%' }}>
      <Box px="md" style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
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

      {active === 1 && (
        <TranslationActionBar
          checkpointHintInfo={checkpointHintInfo}
          config={config}
          form={form}
          onBack={handleBack}
          providerStatusLoading={providerStatusLoading}
          providerStatuses={providerStatuses}
          selectedProjectId={selectedProjectId}
          t={t}
        />
      )}
    </Container >
  );
};

export default InitialTranslation;
