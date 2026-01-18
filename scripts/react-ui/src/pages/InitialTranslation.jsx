import React, { useState, useEffect } from 'react';
import api from '../utils/api';
import { useTranslation } from 'react-i18next';
import { useNotification } from '../context/NotificationContext';
import { useTranslationContext } from '../context/TranslationContext';
import notificationService from '../services/notificationService';
import { useForm } from '@mantine/form';
import {
  Stepper,
  Button,
  Group,
  Select,
  MultiSelect,
  Text,
  Card,
  Space,
  Alert,
  Center,
  Container,
  Paper,
  Stack,
  Grid,
  Loader,
  Textarea,
  Switch,
  Collapse,
  Tabs,
  Modal,
  TextInput,
  ScrollArea,
  Title,
  ThemeIcon,
  Badge,
  Box,
  Tooltip,
} from '@mantine/core';
import { IconAlertCircle, IconCheck, IconX, IconSettings, IconRefresh, IconDownload, IconArrowLeft, IconPlayerStop, IconChevronDown, IconChevronUp, IconFolder, IconFolderOpen, IconPlayerPlay, IconLanguage, IconRobot, IconAdjustments, IconSearch } from '@tabler/icons-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTutorial } from '../context/TutorialContext';
import '../App.css';
import layoutStyles from '../components/layout/Layout.module.css';
import { FEATURES } from '../config/features';

import TaskRunner from '../components/TaskRunner';
import { usePersistentState } from '../hooks/usePersistentState';

const InitialTranslation = () => {
  const { t } = useTranslation();
  const { notificationStyle } = useNotification();
  const {
    activeStep: active,
    setActiveStep: setActive,
    taskId,
    setTaskId,
    taskStatus,
    setTaskStatus,
    isProcessing,
    setIsProcessing,
    translationDetails,
    setTranslationDetails,
    selectedProjectId,
    setSelectedProjectId,
    resetTranslation
  } = useTranslationContext();
  const { setPageContext } = useTutorial();

  const [showAdvanced, setShowAdvanced] = useState(true); // Default to true for 2-col layout
  const [config, setConfig] = useState({
    game_profiles: {},
    languages: {},
    api_providers: [],
  });

  // Project State
  const [projects, setProjects] = useState([]);
  const [searchQuery, setSearchQuery] = usePersistentState('trans_search_query', '');
  const [gameFilter, setGameFilter] = usePersistentState('trans_game_filter', 'all');
  const navigate = useNavigate();
  const location = useLocation();

  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState(null);
  const [resultUrl, setResultUrl] = useState(null);
  const [availableGlossaries, setAvailableGlossaries] = useState([]);
  const [availableModels, setAvailableModels] = useState([]);

  // Resume Modal State
  const [resumeModalOpen, setResumeModalOpen] = useState(false);
  const [checkpointInfo, setCheckpointInfo] = useState(null);
  const [pendingFormValues, setPendingFormValues] = useState(null);

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

  useEffect(() => {
    api.get('/api/config')
      .then(response => {
        setConfig(response.data);
      })
      .catch(error => {
        console.error('Failed to load config:', error);
        notificationService.error(t('message_error_load_config'), notificationStyle);
      });

    // Fetch Projects
    api.get('/api/projects')
      .then(response => {
        setProjects(response.data.map(p => ({
          value: p.project_id,
          label: p.name,
          game_id: p.game_id,
          source_language: p.source_language
        })));
      })
      .catch(error => {
        console.error("Failed to load projects", error);
      });

    // Fetch Prompts for Custom Global Prompt
    api.get('/api/prompts')
      .then(response => {
        if (response.data.custom_global_prompt) {
          form.setFieldValue('mod_context', response.data.custom_global_prompt);
        }
      })
      .catch(err => console.error("Failed to fetch prompts", err));
  }, [notificationStyle]);

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
    setPageContext(`translation-step-${active}`);
  }, [active, setPageContext]);

  // Update available models based on provider
  useEffect(() => {
    const providerConfig = config.api_providers.find(p => p.value === form.values.api_provider);

    if (providerConfig) {
      let models = [];

      // Combine standard available models and custom models
      const availableModelsList = providerConfig.available_models || [];
      const customModelsList = providerConfig.custom_models || [];
      const combinedModels = [...new Set([...availableModelsList, ...customModelsList])];

      if (combinedModels.length > 0) {
        models = combinedModels.map(m => {
          const isCustom = customModelsList.includes(m) && !availableModelsList.includes(m);
          return {
            value: m,
            label: isCustom ? `${m} (Custom)` : m
          };
        });
      }

      // Add default model if not already in the list
      if (providerConfig.default_model && !models.some(m => m.value === providerConfig.default_model)) {
        models.unshift({ value: providerConfig.default_model, label: providerConfig.default_model });
      }

      // Priority 0: Ensure the User's "Selected Model" from settings is ALWAYS in the list
      // This allows manual entry in settings (e.g. "gptoss20b") to appear here without being in the "available" list
      if (providerConfig.selected_model && !models.some(m => m.value === providerConfig.selected_model)) {
        models.unshift({ value: providerConfig.selected_model, label: providerConfig.selected_model });
      }

      // Fallbacks for hardcoded providers if config is missing (legacy support)
      if (models.length === 0) {
        if (form.values.api_provider === 'gemini') {
          models = [
            { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash Preview' },
            { value: 'gemini-3-pro-preview', label: 'Gemini 3 Pro Preview' },
          ];
        } else if (form.values.api_provider === 'ollama') {
          models = [
            { value: 'qwen3:4b', label: 'Qwen 3 (4B)' },
            { value: 'qwen2.5:7b', label: 'Qwen 2.5 (7B)' },
            { value: 'llama3', label: 'Llama 3' },
          ];
        }
      }

      setAvailableModels(models);

      // Priority 1: User-selected model from settings (selected_model)
      // Priority 2: Current selection if still valid
      // Priority 3: First available model
      const currentModelValid = models.some(m => m.value === form.values.model_name);

      if (providerConfig.selected_model && models.some(m => m.value === providerConfig.selected_model)) {
        // If we just switched provider, or current model is invalid, use settings model
        if (!currentModelValid || !form.values.model_name) {
          form.setFieldValue('model_name', providerConfig.selected_model);
        }
      } else if (!currentModelValid && models.length > 0) {
        form.setFieldValue('model_name', models[0].value);
      }
    } else {
      setAvailableModels([]);
      form.setFieldValue('model_name', '');
    }
  }, [form.values.api_provider, config.api_providers]);

  // Polling Logic removed from here (now in TranslationContext)

  const handleProjectSelect = (projectId) => {
    const project = projects.find(p => p.value === projectId);
    if (project) {
      setSelectedProjectId(projectId);
      // Auto-set source language from project metadata if available
      if (project.source_language) {
        // Source language might be ISO code (en, zh-CN) while config.languages is keyed by "1", "2"...
        const langConfig = Object.values(config.languages).find(l => l.code === project.source_language);
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

  const handleStartClick = async (values) => {
    // If use_resume is disabled, skip checkpoint check and start fresh
    if (!values.use_resume) {
      startTranslation(values);
      return;
    }

    // 1. Check for existing checkpoint
    const modName = projects.find(p => p.value === selectedProjectId)?.label;
    if (!modName) return;

    try {
      const response = await api.post('/api/translation/checkpoint-status', {
        mod_name: modName,
        target_lang_codes: values.english_disguise ? ['custom'] : values.target_lang_codes
      });

      if (response.data.exists) {
        setCheckpointInfo(response.data);
        setPendingFormValues(values);
        setResumeModalOpen(true);
      } else {
        // No checkpoint, start normally
        startTranslation(values);
      }
    } catch (error) {
      console.error("Failed to check checkpoint:", error);
      // Fallback to normal start if check fails
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
    if (pendingFormValues) {
      const modName = projects.find(p => p.value === selectedProjectId)?.label;
      try {
        await api.delete('/api/translation/checkpoint', {
          data: {
            mod_name: modName,
            target_lang_codes: pendingFormValues.english_disguise ? ['custom'] : pendingFormValues.target_lang_codes
          }
        });
        notificationService.success("Checkpoint cleared. Starting fresh.", notificationStyle);
        startTranslation(pendingFormValues);
      } catch (error) {
        notificationService.error("Failed to clear checkpoint.", notificationStyle);
        console.error(error);
      }
    }
  };

  const startTranslation = (values) => {
    if (!selectedProjectId) {
      notificationService.error("Please select a project first.", notificationStyle);
      return;
    }

    setTranslationDetails({
      modName: projects.find(p => p.value === selectedProjectId)?.label,
      provider: values.api_provider,
      model: values.model_name,
      sourceLang: Object.values(config.languages).find(l => l.code === values.source_lang_code)?.name,
      targetLangs: values.english_disguise
        ? ['Custom (Disguise)']
        : values.target_lang_codes.map(code => Object.values(config.languages).find(l => l.code === code)?.name),
      gameId: projects.find(p => p.value === selectedProjectId)?.game_id
    });

    const payload = {
      project_id: selectedProjectId,
      source_lang_code: values.source_lang_code,
      // target_language: values.target_lang_code, // Removed in favor of target_lang_codes logic below
      api_provider: values.api_provider,
      model: values.model_name,
      mod_context: values.mod_context,
      selected_glossary_ids: values.selected_glossary_ids,
      use_main_glossary: values.use_main_glossary,
      clean_source: values.clean_source,
      use_resume: values.use_resume,
    };

    if (values.english_disguise) {
      payload.custom_lang_config = {
        name: values.custom_name,
        code: 'custom',
        key: values.custom_key,
        folder_prefix: values.custom_prefix
      };
      payload.target_lang_codes = ['custom'];
    } else {
      payload.target_lang_codes = values.target_lang_codes;
    }

    setTaskId(null);
    setStatus('pending');
    setActive(2);
    setIsProcessing(true);

    api.post('/api/translate/start', payload)
      .then(response => {
        setTaskId(response.data.task_id);
        notificationService.success("Translation started!", notificationStyle);
        setStatus('processing');
        setIsProcessing(true);
        setActive(2);
      })
      .catch(error => {
        notificationService.error("Failed to start translation.", notificationStyle);
        console.error('Translate API error:', error);
        setIsProcessing(false);
        setStatus('failed');
      });
  };

  const renderBackButton = () => (
    <Button onClick={handleBack} leftSection={<IconArrowLeft size={14} />} variant="default">
      {t('button_back')}
    </Button>
  );

  return (
    <Container fluid py="xl" h="100vh" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', maxWidth: '100%', width: '100%' }}>
      <ScrollArea h="100%" type="scroll">
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
            <Container fluid px="xl" id="translation-project-list" style={{ maxWidth: '100%', width: '100%' }}> {/* Use fluid container for maximum width */}
              <Stack gap="lg">
                <Title order={2} ta="center" mb="lg" style={{ letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--mantine-color-blue-4)' }}>
                  {t('translation_page.subtitle')}
                </Title>

                {projects.length > 0 ? (
                  <>
                    {/* --- Search & Filter Bar --- */}
                    <Group mb="md" grow>
                      <TextInput
                        placeholder={t('translation_page.search_placeholder')}
                        leftSection={<IconSearch size={16} />}
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.currentTarget.value)}
                        variant="filled"
                        radius="md"
                      />
                      <Select
                        placeholder={t('translation_page.filter_game_placeholder')}
                        data={[
                          { value: 'all', label: t('common.all_games') },
                          ...Object.values(config.game_profiles).map(p => ({ value: p.id, label: p.name.split('(')[0].trim() }))
                        ]}
                        value={gameFilter}
                        onChange={(value) => setGameFilter(value || 'all')}
                        clearable
                        variant="filled"
                        radius="md"
                      />
                    </Group>

                    {/* --- Project List Header --- */}
                    <Card p="sm" radius="md" mb="xs" bg="rgba(0, 0, 0, 0.3)" withBorder style={{ borderColor: 'var(--mantine-color-dark-4)' }}>
                      <Group>
                        <Text fw={700} size="sm" c="dimmed" style={{ width: '150px', textTransform: 'uppercase', letterSpacing: '1px' }}>{t('translation_page.table_header.game')}</Text>
                        <Text fw={700} size="sm" c="dimmed" style={{ flex: 1, textTransform: 'uppercase', letterSpacing: '1px' }}>{t('translation_page.table_header.mod_name')}</Text>
                        <Text fw={700} size="sm" c="dimmed" style={{ width: '80px', textAlign: 'right', textTransform: 'uppercase', letterSpacing: '1px' }}>{t('translation_page.table_header.action')}</Text>
                      </Group>
                    </Card>

                    {/* --- Project List Rows --- */}
                    <ScrollArea h={600} offsetScrollbars type="always">
                      <Stack gap="xs">
                        {projects
                          .filter(project => {
                            const matchesGame = gameFilter === 'all' || !gameFilter || project.game_id === gameFilter;
                            const matchesSearch = project.label.toLowerCase().includes(searchQuery.toLowerCase());
                            return matchesGame && matchesSearch;
                          })
                          .map((project) => {
                            const profile = config.game_profiles[project.game_id] ||
                              Object.values(config.game_profiles).find(p => p.id === project.game_id);
                            const gameName = profile ? profile.name.split('(')[0].trim() : 'Unknown';

                            return (
                              <Card
                                key={project.value}
                                p="md"
                                radius="md"
                                withBorder
                                className={layoutStyles.glassCard}
                                style={{
                                  cursor: 'pointer',
                                  borderColor: selectedProjectId === project.value ? 'var(--mantine-color-blue-6)' : 'transparent',
                                  backgroundColor: selectedProjectId === project.value ? 'rgba(34, 139, 230, 0.1)' : 'rgba(255, 255, 255, 0.03)',
                                  transition: 'all 0.2s ease',
                                  '&:hover': {
                                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                                    transform: 'translateX(5px)'
                                  }
                                }}
                                onClick={() => handleProjectSelect(project.value)}
                              >
                                <Group>
                                  <Badge
                                    color={project.game_id === 'victoria3' ? 'pink' : 'blue'}
                                    variant="filled"
                                    w={150}
                                    radius="sm"
                                  >
                                    {gameName}
                                  </Badge>
                                  <Text fw={500} size="lg" style={{ flex: 1 }}>{project.label}</Text>
                                  <Button
                                    size="sm"
                                    variant={selectedProjectId === project.value ? "filled" : "subtle"}
                                    color="blue"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleProjectSelect(project.value);
                                    }}
                                  >
                                    {selectedProjectId === project.value ? t('translation_page.button.selected') : t('translation_page.button.select')}
                                  </Button>
                                </Group>
                              </Card>
                            );
                          })}
                        {projects.length === 0 && (
                          <Text c="dimmed" ta="center" py="xl">{t('translation_page.no_projects_found')}</Text>
                        )}
                      </Stack>
                    </ScrollArea>
                  </>
                ) : (
                  <Center p="xl">
                    <Stack align="center">
                      <IconFolderOpen size={48} stroke={1.5} color="var(--mantine-color-gray-5)" />
                      <Text c="dimmed">{t('translation_page.no_projects_action')}</Text>
                      <Button variant="subtle" onClick={() => navigate('/')}>{t('translation_page.go_to_project_management')}</Button>
                    </Stack>
                  </Center>
                )}
              </Stack>
            </Container>
          )}
          {
            active === 1 && (
              <form onSubmit={form.onSubmit(handleStartClick)}>
                <Grid gutter="xl">
                  {/* Left Column: Core Configuration */}
                  <Grid.Col span={{ base: 12, md: 5 }}>
                    <Card id="translation-config-card" withBorder padding="xl" radius="md" className={layoutStyles.glassCard} h="100%">
                      <Stack gap="md">
                        <Group>
                          <ThemeIcon size="lg" radius="md" variant="light" color="blue">
                            <IconSettings size={20} />
                          </ThemeIcon>
                          <Text size="lg" fw={500}>{t('initial_translation_step_core_settings')}</Text>
                        </Group>

                        {/* Project Name (Read Only) */}
                        {selectedProjectId && (
                          <TextInput
                            label={t('form_label_project_name')}
                            value={projects.find(p => p.value === selectedProjectId)?.label || 'Unknown'}
                            disabled
                            variant="filled"
                          />
                        )}

                        {/* Game & Source Language Row */}
                        {selectedProjectId && (
                          <Grid>
                            <Grid.Col span={6}>
                              <Tooltip label={t('initial_translation_step_readonly_hint')} withArrow>
                                <div>
                                  <TextInput
                                    label={t('form_label_game')}
                                    value={(() => {
                                      const project = projects.find(p => p.value === selectedProjectId);
                                      if (!project) return 'Unknown';
                                      const profile = config.game_profiles[project.game_id] ||
                                        Object.values(config.game_profiles).find(p => p.id === project.game_id);
                                      return profile ? profile.name : 'Unknown';
                                    })()}
                                    disabled
                                    variant="filled"
                                  />
                                </div>
                              </Tooltip>
                            </Grid.Col>
                            <Grid.Col span={6}>
                              <Tooltip label={t('initial_translation_step_readonly_hint')} withArrow>
                                <div>
                                  <TextInput
                                    label={t('form_label_source_language')}
                                    value={(() => {
                                      const project = projects.find(p => p.value === selectedProjectId);
                                      if (!project) return 'Unknown';
                                      const langConfig = Object.values(config.languages).find(l => l.code === project.source_language);
                                      return langConfig ? langConfig.name : 'Unknown';
                                    })()}
                                    disabled
                                    variant="filled"
                                  />
                                </div>
                              </Tooltip>
                            </Grid.Col>
                          </Grid>
                        )}

                        {!form.values.english_disguise && (
                          <MultiSelect
                            label={t('form_label_target_languages')}
                            placeholder={t('form_placeholder_target_languages')}
                            leftSection={<IconLanguage size={16} />}
                            data={Object.values(config.languages).map(l => ({ value: l.code, label: l.name }))}
                            {...form.getInputProps('target_lang_codes')}
                            searchable
                            hidePickedOptions
                          />
                        )}

                        <Select
                          label={
                            <Group gap={5}>
                              {t('form_label_api_provider')}
                              {!['ollama', 'lm_studio', 'vllm', 'koboldcpp', 'oobabooga', 'gemini_cli', 'hunyuan'].includes(form.values.api_provider) && (
                                <Tooltip
                                  label={t('tutorial.api_key_warning_tooltip')}
                                  multiline
                                  w={300}
                                  withArrow
                                  position="top-start"
                                >
                                  <Group gap={4} style={{ cursor: 'help' }}>
                                    <IconAlertCircle size={14} color="orange" />
                                    <Text size="xs" c="orange" td="underline" style={{ fontSize: '0.75rem' }}>
                                      {t('tutorial.api_key_warning_label')}
                                    </Text>
                                  </Group>
                                </Tooltip>
                              )}
                            </Group>
                          }
                          leftSection={<IconRobot size={16} />}
                          data={config.api_providers.filter(p => p.value !== 'hunyuan' || FEATURES.ENABLE_HUNYUAN_PROVIDER)}
                          {...form.getInputProps('api_provider')}
                        />

                        {/* Local LLM Warning */}
                        {['ollama', 'lm_studio', 'vllm', 'koboldcpp', 'oobabooga'].includes(form.values.api_provider) && (
                          <Alert variant="light" color="yellow" title={t('tutorial.local_llm_warning')} icon={<IconAlertCircle size={16} />} mt="xs">
                          </Alert>
                        )}

                        {availableModels.length > 0 && (
                          <Group align="flex-end" gap={5} style={{ width: '100%' }}>
                            <Select
                              label={
                                <Group gap={5}>
                                  {t('initial_translation_step_model')}
                                  <Tooltip
                                    label={t('tutorial.smart_model_warning_tooltip')}
                                    multiline
                                    w={300}
                                    withArrow
                                    position="top-start"
                                  >
                                    <Group gap={4} style={{ cursor: 'help' }}>
                                      <IconAlertCircle size={14} color="orange" />
                                      <Text size="xs" c="orange" td="underline" style={{ fontSize: '0.75rem' }}>
                                        {t('tutorial.smart_model_warning_label')}
                                      </Text>
                                    </Group>
                                  </Tooltip>
                                </Group>
                              }
                              data={availableModels}
                              {...form.getInputProps('model_name')}
                              style={{ flex: 1 }}
                            />
                            <Tooltip label={t('model_settings_hint', 'You can add more models in Settings > API Settings')} withArrow>
                              <ThemeIcon variant="light" color="gray" size="lg" mb={2}>
                                <IconSettings size={18} />
                              </ThemeIcon>
                            </Tooltip>
                          </Group>
                        )}
                      </Stack>
                    </Card>
                  </Grid.Col>

                  {/* Right Column: Advanced Configuration */}
                  <Grid.Col span={{ base: 12, md: 7 }}>
                    <Card withBorder padding="xl" radius="md" className={layoutStyles.glassCard} h="100%">
                      <Stack gap="md">
                        <Group>
                          <ThemeIcon size="lg" radius="md" variant="light" color="orange">
                            <IconAdjustments size={20} />
                          </ThemeIcon>
                          <Text size="lg" fw={500}>{t('advanced_options', 'Advanced Options')}</Text>
                        </Group>

                        <Textarea
                          label={t('form_label_additional_prompt')}
                          placeholder={t('form_placeholder_additional_prompt')}
                          autosize
                          minRows={4}
                          {...form.getInputProps('mod_context')}
                        />

                        <Group grow align="flex-start">
                          <Stack gap="xs">
                            <Switch
                              label={t('form_label_use_main_glossary')}
                              description={t('form_desc_use_main_glossary')}
                              {...form.getInputProps('use_main_glossary', { type: 'checkbox' })}
                            />
                            <Tooltip
                              label={t('tooltip_clean_source', 'WARNING: This will DELETE all files in the uploaded mod folder except for localization files (.yml), Customizable Localization (.txt) and metadata (.mod, .json, .png) to save disk space. Use with caution!')}
                              multiline
                              w={300}
                              withArrow
                              color="red"
                            >
                              <div>
                                <Switch
                                  label={t('form_label_clean_source')}
                                  description={t('warning_clean_source')}
                                  color="red"
                                  checked={form.values.clean_source}
                                  onChange={(event) => form.setFieldValue('clean_source', event.currentTarget.checked)}
                                  style={{ cursor: 'help' }}
                                />
                              </div>
                            </Tooltip>
                            <Switch
                              label={t('form_label_use_resume')}
                              description={t('form_desc_use_resume')}
                              {...form.getInputProps('use_resume', { type: 'checkbox' })}
                            />
                          </Stack>

                          <MultiSelect
                            label={t('form_label_extra_glossaries')}
                            placeholder={t('form_placeholder_extra_glossaries')}
                            data={availableGlossaries}
                            {...form.getInputProps('selected_glossary_ids')}
                            clearable
                          />
                        </Group>

                        <Card withBorder p="md" radius="md" bg="var(--mantine-color-body)">
                          <Stack gap="xs">
                            <Switch
                              label={t('form_label_disguise_mode')}
                              description={t('form_desc_disguise_mode')}
                              {...form.getInputProps('english_disguise', {
                                type: 'checkbox',
                                onChange: (event) => {
                                  form.setFieldValue('english_disguise', event.currentTarget.checked);
                                  if (event.currentTarget.checked) {
                                    form.setFieldValue('target_lang_codes', []); // Clear target languages if disguise is on
                                  } else {
                                    // Clear custom fields if disguise is off
                                    form.setFieldValue('custom_name', '');
                                    form.setFieldValue('custom_key', '');
                                    form.setFieldValue('custom_prefix', '');
                                    form.setFieldValue('disguise_target_key', '');
                                  }
                                }
                              })}
                            />

                            {form.values.english_disguise && (
                              <>
                                <Text size="sm" fw={500} mt="xs">{t('form_title_custom_config')}</Text>
                                <TextInput
                                  label={t('form_label_custom_name')}
                                  placeholder={t('form_placeholder_custom_name')}
                                  description={t('form_desc_custom_name')}
                                  {...form.getInputProps('custom_name')}
                                />
                                <Group grow>
                                  <Select
                                    label={t('form_label_disguise_target')}
                                    placeholder={t('form_placeholder_disguise_target')}
                                    data={Object.values(config.languages).map(l => ({ value: l.key, label: `${l.name} (${l.key})` }))}
                                    {...form.getInputProps('disguise_target_key')}
                                    onChange={(value) => {
                                      form.setFieldValue('disguise_target_key', value);
                                      form.setFieldValue('custom_key', value);
                                    }}
                                  />
                                  <TextInput
                                    label={t('form_label_folder_prefix')}
                                    placeholder={t('form_placeholder_folder_prefix')}
                                    {...form.getInputProps('custom_prefix')}
                                  />
                                </Group>
                              </>
                            )}
                          </Stack>
                        </Card>
                      </Stack>
                    </Card>
                  </Grid.Col>
                </Grid>

                <Group justify="flex-end" mt="xl">
                  {renderBackButton()}
                  <Button id="translation-start-btn" type="submit" size="lg">{t('button_start_translation')}</Button>
                </Group>
              </form>
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
      </ScrollArea >

      < Modal
        opened={resumeModalOpen}
        onClose={() => setResumeModalOpen(false)}
        title={< Group ><IconAlertCircle color="orange" /> <Text fw={700}>{t('translation_page.resume_modal.title')}</Text></Group >}
        centered
      >
        <Stack>
          <Text>
            {t('translation_page.resume_modal.content')}
          </Text>
          {checkpointInfo && (
            <Alert color="blue" variant="light">
              <Text size="sm"><b>{t('translation_page.resume_modal.completed_files')}</b> {checkpointInfo.completed_count}</Text>
              {checkpointInfo.total_files_estimate > 0 && (
                <Text size="sm"><b>{t('translation_page.resume_modal.estimated_progress')}</b> {Math.round((checkpointInfo.completed_count / checkpointInfo.total_files_estimate) * 100)}%</Text>
              )}
              {checkpointInfo.metadata?.model_name && (
                <Text size="sm"><b>{t('translation_page.resume_modal.previous_model')}</b> {checkpointInfo.metadata.model_name}</Text>
              )}
            </Alert>
          )}
          <Text size="sm" c="dimmed">
            {t('translation_page.resume_modal.question')}
          </Text>
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={handleStartOver} leftSection={<IconRefresh size={16} />}>
              {t('translation_page.resume_modal.start_over')}
            </Button>
            <Button onClick={handleResume} leftSection={<IconPlayerPlay size={16} />}>
              {t('translation_page.resume_modal.resume')}
            </Button>
          </Group>
        </Stack>
      </Modal >
    </Container >
  );
};

export default InitialTranslation;
