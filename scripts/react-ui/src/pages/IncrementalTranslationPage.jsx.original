import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
    Container,
    Stepper,
    Button,
    Group,
    Paper,
    Text,
    Title,
    Stack,
    Card,
    SimpleGrid,
    Badge,
    Alert,
    Select,
    TextInput,
    Progress,
    Divider,
    MultiSelect,
    Accordion,
    Box,
    Switch,
    Collapse,
    Modal,
    Tooltip,
    ThemeIcon,
} from '@mantine/core';
import { IconRocket, IconCheck, IconAlertCircle, IconSearch, IconFolderOpen, IconPlayerPlay, IconChartBar, IconSettings } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import api from '../utils/api';
import { open } from '@tauri-apps/plugin-dialog';
import { useNotification } from '../context/NotificationContext';
import { getTutorialKey, useTutorial } from '../context/TutorialContext';
import notificationService from '../services/notificationService';
import styles from './Translation.module.css';

const INCREMENTAL_STATE_STORAGE_KEY = 'incremental_translation_state_v1';
const LOCAL_PROVIDERS = ['ollama', 'lm_studio', 'vllm', 'koboldcpp', 'oobabooga', 'text-generation-webui'];

const normalizeArrayPayload = (payload, keys = []) => {
    if (Array.isArray(payload)) return payload;
    if (!payload || typeof payload !== 'object') return [];

    for (const key of keys) {
        if (Array.isArray(payload[key])) return payload[key];
    }

    return [];
};

const IncrementalTranslationPage = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const location = useLocation();
    const { notificationStyle } = useNotification();
    const { setPageContext, startTour } = useTutorial();
    const [active, setActive] = useState(0);
    const [loading, setLoading] = useState(false);
    const [showTutorialPrompt, setShowTutorialPrompt] = useState(false);

    // Data State
    const [projects, setProjects] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [gameFilter, setGameFilter] = useState('all');
    const [selectedProject, setSelectedProject] = useState(null);
    const [apiProviders, setApiProviders] = useState([]);
    const [selectedProvider, setSelectedProvider] = useState('gemini');
    const [selectedModel, setSelectedModel] = useState('');
    const [models, setModels] = useState([]);
    const [customSourcePath, setCustomSourcePath] = useState('');
    const [selectedLangs, setSelectedLangs] = useState([]);
    const [batchSizeLimit, setBatchSizeLimit] = useState('');
    const [concurrencyLimit, setConcurrencyLimit] = useState('10');
    const [rpmLimit, setRpmLimit] = useState('40');

    // Validation / Scan Results
    const [archiveInfo, setArchiveInfo] = useState(null);
    const [scanResults, setScanResults] = useState(null);
    const [error, setError] = useState(null);
    const [errorKey, setErrorKey] = useState(null);

    // Execution State
    const [executing, setExecuting] = useState(false);
    const [progress, setProgress] = useState(0);
    const [progressInfo, setProgressInfo] = useState({});
    const [logs, setLogs] = useState([]);
    const [finalSummary, setFinalSummary] = useState(null);
    const [currentTaskId, setCurrentTaskId] = useState(null);
    const [currentTaskMode, setCurrentTaskMode] = useState(null);
    const logScrollRef = useRef(null);
    const [checkpointFound, setCheckpointFound] = useState(false);
    const [checkpointInfo, setCheckpointInfo] = useState(null);
    const [useResume, setUseResume] = useState(false);
    const [showResumeDetails, setShowResumeDetails] = useState(false);
    const [embeddedWorkshopEnabled, setEmbeddedWorkshopEnabled] = useState(true);
    const [embeddedWorkshopFollowPrimary, setEmbeddedWorkshopFollowPrimary] = useState(true);
    const [embeddedWorkshopProvider, setEmbeddedWorkshopProvider] = useState('');
    const [embeddedWorkshopModel, setEmbeddedWorkshopModel] = useState('');
    const [embeddedWorkshopBatchSize, setEmbeddedWorkshopBatchSize] = useState('10');
    const [embeddedWorkshopConcurrency, setEmbeddedWorkshopConcurrency] = useState('1');
    const [embeddedWorkshopRpm, setEmbeddedWorkshopRpm] = useState('40');
    const [showWorkshopSettings, setShowWorkshopSettings] = useState(false);
    const wsRef = useRef(null);
    const pollTimerRef = useRef(null);
    const logViewportRef = useRef(null);
    const completionSourceRef = useRef(null);
    const preScanInFlightRef = useRef(false);
    const executionInFlightRef = useRef(false);
    const persistedStateRef = useRef(null);
    const restorationAppliedRef = useRef(false);
    const statusResyncRef = useRef(false);
    const routePrefillAppliedRef = useRef(false);
    const [projectsLoaded, setProjectsLoaded] = useState(false);
    const [configLoaded, setConfigLoaded] = useState(false);
    const batchSizeOptions = [
        { value: '', label: t('translation_page.translation_limit_auto', { defaultValue: 'Auto (Recommended)' }) },
        ...['5', '10', '20', '40', '60'].map((value) => ({ value, label: value })),
    ];
    const concurrencyOptions = ['1', '2', '5', '10', '20', '50'].map((value) => ({ value, label: value }));
    const rpmOptions = ['5', '10', '20', '30', '50', '100'].map((value) => ({ value, label: value }));
    const workshopBatchOptions = ['3', '5', '10', '15', '20'].map((value) => ({ value, label: value }));
    const workshopConcurrencyOptions = ['1', '2', '3', '5'].map((value) => ({ value, label: value }));
    const workshopRpmOptions = ['5', '10', '20', '40', '60', '100'].map((value) => ({ value, label: value }));
    const filteredProjects = useMemo(() => {
        const normalizedQuery = searchQuery.trim().toLowerCase();
        return projects.filter((project) => {
            const matchesGame = gameFilter === 'all' || project.game_id === gameFilter;
            const haystack = [
                project.name,
                project.game_id,
                project.source_language,
                project.source_path,
            ]
                .filter(Boolean)
                .join(' ')
                .toLowerCase();
            const matchesQuery = !normalizedQuery || haystack.includes(normalizedQuery);
            return matchesGame && matchesQuery;
        });
    }, [gameFilter, projects, searchQuery]);
    const gameFilterOptions = useMemo(() => {
        const games = Array.from(new Set(projects.map((project) => project.game_id).filter(Boolean)));
        return [
            { value: 'all', label: t('common.all_games', { defaultValue: 'All Games' }) },
            ...games.map((game) => ({ value: game, label: game.toUpperCase() })),
        ];
    }, [projects, t]);

    const formatDuration = useCallback((ms) => {
        if (typeof ms !== 'number' || Number.isNaN(ms)) return '--';
        if (ms < 1000) return `${Math.round(ms)} ms`;
        return `${(ms / 1000).toFixed(ms >= 10000 ? 0 : 1)} s`;
    }, []);

    const formatDateTime = useCallback((value) => {
        if (!value) return '--';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleString();
    }, []);

    const renderInfoLabel = useCallback((label, tooltip) => (
        <Group gap={4} wrap="nowrap">
            <Text size="sm" fw={500}>{label}</Text>
            {tooltip && (
                <Tooltip label={tooltip} multiline w={320} withArrow>
                    <ThemeIcon variant="subtle" color="gray" size="sm" style={{ cursor: 'help' }}>
                        <IconAlertCircle size={14} />
                    </ThemeIcon>
                </Tooltip>
            )}
        </Group>
    ), []);

    const getStageTitle = useCallback((progressState, isPreScan = false) => {
        const stageCode = progressState?.stage_code || '';
        const translationKey = stageCode
            ? `incremental_translation.progress_stage_${stageCode}`
            : (isPreScan ? 'incremental_translation.pre_scan_in_progress' : 'incremental_translation.execution_in_progress');
        return t(translationKey, {
            defaultValue: isPreScan
                ? t('incremental_translation.pre_scan_in_progress')
                : t('incremental_translation.execution_in_progress')
        });
    }, [t]);

    const getStageDescription = useCallback((progressState) => {
        if (!progressState) return '';
        if (progressState.current_file && progressState.total_files) {
            return t('incremental_translation.progress_file_counter', {
                current: progressState.current_file_index || 1,
                total: progressState.total_files,
                file: progressState.current_file,
            });
        }
        if (progressState.batch_idx && progressState.total_batches) {
            return t('incremental_translation.progress_batch_counter', {
                current: progressState.batch_idx,
                total: progressState.total_batches,
            });
        }
        if (typeof progressState.files_detected === 'number') {
            return t('incremental_translation.progress_files_detected', {
                count: progressState.files_detected,
            });
        }
        return progressState.message || '';
    }, [t]);

    const formatWarningMessage = useCallback((warning) => {
        if (!warning) return '';

        const batchNum = warning.batch_num ?? '?';
        const attempt = warning.attempt ?? '?';
        const provider = warning.provider || 'unknown';
        const rawMessage = String(warning.message || '');
        const errorText = rawMessage.trim();
        const normalizedDetails = warning.details ? String(warning.details).replace(/\s+/g, ' ').trim() : '';
        const warningDetails = normalizedDetails
            ? ` ${t('incremental_translation.warning_details_suffix', { details: normalizedDetails })}`
            : '';

        if (warning.type === 'fallback_to_source') {
            return t('incremental_translation.warning_fallback_to_source', {
                batch_num: batchNum,
                provider,
            });
        }

        if (warning.type === 'context_exceeded') {
            return t('incremental_translation.warning_context_exceeded', {
                batch_num: batchNum,
                attempt,
                provider,
            });
        }

        if (warning.type === 'api_error') {
            if (errorText.includes('API_KEY_INVALID') || errorText.includes('API Key not found')) {
                return t('incremental_translation.warning_api_key_invalid', {
                    batch_num: batchNum,
                    attempt,
                    provider,
                });
            }

            return t('incremental_translation.warning_api_error', {
                batch_num: batchNum,
                attempt,
                provider,
                error: rawMessage,
            });
        }

        if (errorText.includes('API_KEY_INVALID') || errorText.includes('API Key not found')) {
            return t('incremental_translation.warning_api_key_invalid', {
                batch_num: batchNum,
                attempt,
                provider,
            });
        }

        if (errorText.includes('Response parsing failed')) {
            return t('incremental_translation.warning_response_parsing_failed', {
                batch_num: batchNum,
                attempt,
                provider,
            });
        }

        if (errorText.includes('429') || errorText.toLowerCase().includes('rate limit') || errorText.toLowerCase().includes('too many requests')) {
            return t('incremental_translation.warning_rate_limited', {
                batch_num: batchNum,
                attempt,
                provider,
            });
        }

        if (errorText.includes('Batch failed after retries and fell back to source text')) {
            return t('incremental_translation.warning_fallback_to_source', {
                batch_num: batchNum,
                provider,
            });
        }

        if (errorText === 'Invalid key format') {
            return `${t('incremental_translation.warning_invalid_key_format')}${warningDetails}`;
        }

        if (warning.level && rawMessage) {
            const validationMessage = rawMessage.startsWith('validation_')
                ? t('incremental_translation.warning_validation_generic')
                : rawMessage;
            return `${t('incremental_translation.warning_validation_prefix', {
                level: String(warning.level).toUpperCase(),
            })}${validationMessage}${warningDetails}`;
        }

        if (rawMessage) {
            return t('incremental_translation.warning_generic_with_error', {
                error: rawMessage,
            });
        }

        return rawMessage;
    }, [t]);

    const resolveProviderModels = useCallback((providerValue) => {
        const providerData = apiProviders.find((provider) => provider.value === providerValue);
        if (!providerData) return [];
        const availableModels = providerData.available_models || [];
        const customModels = providerData.custom_models || [];
        const merged = [...new Set([...availableModels, ...customModels])];
        if (providerData.selected_model && !merged.includes(providerData.selected_model)) {
            merged.unshift(providerData.selected_model);
        }
        if (providerData.default_model && !merged.includes(providerData.default_model)) {
            merged.unshift(providerData.default_model);
        }
        return merged;
    }, [apiProviders]);

    const applyProviderSelection = useCallback((providerValue, preferredModel = '', preferredConcurrency = null) => {
        const nextProvider = providerValue || 'gemini';
        const availableModels = resolveProviderModels(nextProvider);
        const nextModel = preferredModel && availableModels.includes(preferredModel)
            ? preferredModel
            : (availableModels[0] || '');

        setSelectedProvider(nextProvider);
        setModels(availableModels);
        setSelectedModel(nextModel);

        if (preferredConcurrency !== null && preferredConcurrency !== undefined) {
            setConcurrencyLimit(String(preferredConcurrency));
        } else {
            setConcurrencyLimit(LOCAL_PROVIDERS.includes(nextProvider) ? '1' : '10');
        }
    }, [resolveProviderModels]);

    useEffect(() => {
        if (embeddedWorkshopFollowPrimary) {
            return;
        }

        const modelsForProvider = resolveProviderModels(embeddedWorkshopProvider);
        if (!embeddedWorkshopProvider && apiProviders.length > 0) {
            const providerValue = apiProviders[0]?.value || '';
            setEmbeddedWorkshopProvider(providerValue);
            setEmbeddedWorkshopModel(resolveProviderModels(providerValue)[0] || '');
            return;
        }

        if (modelsForProvider.length > 0 && !modelsForProvider.includes(embeddedWorkshopModel)) {
            setEmbeddedWorkshopModel(modelsForProvider[0]);
        }
    }, [
        apiProviders,
        embeddedWorkshopFollowPrimary,
        embeddedWorkshopModel,
        embeddedWorkshopProvider,
        resolveProviderModels,
    ]);

    const resetPersistedState = useCallback(() => {
        sessionStorage.removeItem(INCREMENTAL_STATE_STORAGE_KEY);
        setCurrentTaskId(null);
        setCurrentTaskMode(null);
        preScanInFlightRef.current = false;
        executionInFlightRef.current = false;
        completionSourceRef.current = null;
        statusResyncRef.current = false;
    }, []);

    const renderTelemetry = useCallback((telemetry) => {
        if (!telemetry) return null;

        const languageTelemetry = Array.isArray(telemetry.languages) ? telemetry.languages : [];
        const topLevelItems = [
            { label: t('incremental_translation.telemetry_snapshot'), value: formatDuration(telemetry.snapshot_ms) },
            { label: t('incremental_translation.telemetry_total'), value: formatDuration(telemetry.total_ms) },
        ];

        return (
            <Stack gap="xs" mt="md">
                <Text size="sm" fw={600}>{t('incremental_translation.telemetry_title')}</Text>
                <SimpleGrid cols={{ base: 1, sm: 2 }}>
                    {topLevelItems.map((item) => (
                        <Card key={item.label} withBorder p="sm" radius="md">
                            <Text size="xs" c="dimmed">{item.label}</Text>
                            <Text size="sm" fw={600}>{item.value}</Text>
                        </Card>
                    ))}
                </SimpleGrid>
                {languageTelemetry.length > 0 && (
                    <Accordion variant="separated" radius="md" chevronPosition="right">
                        {languageTelemetry.map((item) => (
                            <Accordion.Item key={item.target_lang} value={item.target_lang}>
                                <Accordion.Control>
                                    <Group justify="space-between" wrap="nowrap">
                                        <Text size="sm" fw={600}>{item.target_lang}</Text>
                                        <Badge color="blue" variant="light">{formatDuration(item.total_ms)}</Badge>
                                    </Group>
                                </Accordion.Control>
                                <Accordion.Panel>
                                    {item.archive_baseline && (
                                        <Card withBorder p="sm" radius="md" mb="md">
                                            <Text size="xs" c="dimmed">{t('incremental_translation.archive_baseline_title')}</Text>
                                            <SimpleGrid cols={{ base: 1, sm: 2 }} mt="xs">
                                                <Box>
                                                    <Text size="xs" c="dimmed">{t('incremental_translation.archive_version_label')}</Text>
                                                    <Text size="sm" fw={600}>v{item.archive_baseline.version_id ?? '--'}</Text>
                                                </Box>
                                                <Box>
                                                    <Text size="xs" c="dimmed">{t('incremental_translation.archive_entries_label')}</Text>
                                                    <Text size="sm" fw={600}>{item.archive_baseline.translated_count ?? '--'}</Text>
                                                </Box>
                                                <Box>
                                                    <Text size="xs" c="dimmed">{t('incremental_translation.archive_uploaded_label')}</Text>
                                                    <Text size="sm">{formatDateTime(item.archive_baseline.last_translation_at)}</Text>
                                                </Box>
                                                <Box>
                                                    <Text size="xs" c="dimmed">{t('incremental_translation.archive_snapshot_label')}</Text>
                                                    <Text size="sm">{formatDateTime(item.archive_baseline.created_at)}</Text>
                                                </Box>
                                            </SimpleGrid>
                                        </Card>
                                    )}
                                    <SimpleGrid cols={{ base: 1, sm: 2 }}>
                                        {[
                                            ['incremental_translation.telemetry_archive_fetch', item.archive_fetch_ms],
                                            ['incremental_translation.telemetry_prepare', item.prepare_ms],
                                            ['incremental_translation.telemetry_translation', item.translation_ms],
                                            ['incremental_translation.telemetry_build', item.build_ms],
                                            ['incremental_translation.telemetry_archive_write', item.archive_write_ms],
                                        ]
                                            .filter(([, value]) => typeof value === 'number')
                                            .map(([labelKey, value]) => (
                                                <Card key={labelKey} withBorder p="sm" radius="md">
                                                    <Text size="xs" c="dimmed">{t(labelKey)}</Text>
                                                    <Text size="sm" fw={600}>{formatDuration(value)}</Text>
                                                </Card>
                                            ))}
                                    </SimpleGrid>
                                </Accordion.Panel>
                            </Accordion.Item>
                        ))}
                    </Accordion>
                )}
            </Stack>
        );
    }, [formatDateTime, formatDuration, t]);

    const getValidationIssueCount = useCallback((summary) => {
        if (!summary || !Array.isArray(summary.workshop_issue_exports)) return 0;
        return summary.workshop_issue_exports.reduce((total, item) => total + Number(item?.issue_count || 0), 0);
    }, []);

    const getArchivedTargetLanguages = useCallback((info) => {
        if (!info) return [];
        if (Array.isArray(info.archived_languages)) {
            return info.archived_languages.filter(Boolean);
        }
        if (Array.isArray(info.target_languages)) {
            return info.target_languages.filter(Boolean);
        }
        return info.target_language ? [info.target_language] : [];
    }, []);

    const renderFileDetails = useCallback((fileSummaries) => {
        const dirtyFiles = (fileSummaries || []).filter((item) => (item.new + item.changed) > 0);
        if (dirtyFiles.length === 0) return null;

        return (
            <Accordion variant="separated" radius="md" mt="md">
                <Accordion.Item value="file-details">
                    <Accordion.Control>
                        <Group justify="space-between" wrap="nowrap">
                            <Text fw={600}>{t('incremental_translation.file_details_title')}</Text>
                            <Badge color="orange" variant="light">{dirtyFiles.length}</Badge>
                        </Group>
                    </Accordion.Control>
                    <Accordion.Panel>
                        <Stack gap="sm">
                            {dirtyFiles.map((file) => (
                                <Card key={`${file.target_lang || 'default'}:${file.file_path}`} withBorder p="sm" radius="md">
                                    <Group justify="space-between" mb="xs" wrap="nowrap">
                                        <Box style={{ minWidth: 0 }}>
                                            <Text size="sm" fw={600} truncate>{file.file_path}</Text>
                                            <Text size="xs" c="dimmed">{file.target_lang || selectedLangs[0] || archiveInfo?.target_language || '--'}</Text>
                                        </Box>
                                        <Group gap={6}>
                                            <Badge color="green" variant="light">{t('incremental_translation.reused_short')}: {file.unchanged}</Badge>
                                            <Badge color="orange" variant="light">{t('incremental_translation.new_short')}: {file.new}</Badge>
                                            <Badge color="red" variant="light">{t('incremental_translation.changed_short')}: {file.changed}</Badge>
                                        </Group>
                                    </Group>
                                    <Stack gap={6}>
                                        {(file.dirty_entries || []).map((entry, index) => (
                                            <Group key={`${file.file_path}:${entry.key}:${index}`} justify="space-between" align="flex-start" wrap="nowrap">
                                                <Box style={{ minWidth: 0 }}>
                                                    <Text size="xs" fw={600}>{entry.key}</Text>
                                                    <Text size="xs" c="dimmed" lineClamp={2}>{entry.source_text}</Text>
                                                </Box>
                                                <Badge
                                                    color={entry.status === 'new' ? 'orange' : 'red'}
                                                    variant="filled"
                                                    style={{ flexShrink: 0, whiteSpace: 'nowrap' }}
                                                >
                                                    {t(`incremental_translation.entry_status_${entry.status}`)}
                                                </Badge>
                                            </Group>
                                        ))}
                                    </Stack>
                                </Card>
                            ))}
                        </Stack>
                    </Accordion.Panel>
                </Accordion.Item>
            </Accordion>
        );
    }, [archiveInfo?.target_language, selectedLangs, t]);

    useEffect(() => {
        if (restorationAppliedRef.current || !projectsLoaded || !configLoaded) return;

        const persistedState = persistedStateRef.current;
        if (!persistedState) {
            restorationAppliedRef.current = true;
            return;
        }

        const matchedProject = persistedState.selectedProject?.project_id
            ? projects.find((project) => project.project_id === persistedState.selectedProject.project_id) || persistedState.selectedProject
            : null;

        if (matchedProject) setSelectedProject(matchedProject);
        if (typeof persistedState.active === 'number') setActive(persistedState.active);
        if (typeof persistedState.loading === 'boolean') setLoading(persistedState.loading);
        if (persistedState.customSourcePath) setCustomSourcePath(persistedState.customSourcePath);
        if (Array.isArray(persistedState.selectedLangs)) setSelectedLangs(persistedState.selectedLangs);
        if (persistedState.archiveInfo) setArchiveInfo(persistedState.archiveInfo);
        if (persistedState.scanResults) setScanResults(persistedState.scanResults);
        if (persistedState.errorKey) setErrorKey(persistedState.errorKey);
        if (typeof persistedState.executing === 'boolean') setExecuting(persistedState.executing);
        if (typeof persistedState.progress === 'number') setProgress(persistedState.progress);
        if (persistedState.progressInfo) setProgressInfo(persistedState.progressInfo);
        if (Array.isArray(persistedState.logs)) setLogs(persistedState.logs);
        if (persistedState.finalSummary) setFinalSummary(persistedState.finalSummary);
        if (typeof persistedState.checkpointFound === 'boolean') setCheckpointFound(persistedState.checkpointFound);
        if (persistedState.checkpointInfo) setCheckpointInfo(persistedState.checkpointInfo);
        if (typeof persistedState.useResume === 'boolean') setUseResume(persistedState.useResume);
        if (typeof persistedState.showResumeDetails === 'boolean') setShowResumeDetails(persistedState.showResumeDetails);
        if (typeof persistedState.embeddedWorkshopEnabled === 'boolean') setEmbeddedWorkshopEnabled(persistedState.embeddedWorkshopEnabled);
        if (typeof persistedState.embeddedWorkshopFollowPrimary === 'boolean') setEmbeddedWorkshopFollowPrimary(persistedState.embeddedWorkshopFollowPrimary);
        if (persistedState.embeddedWorkshopProvider) setEmbeddedWorkshopProvider(persistedState.embeddedWorkshopProvider);
        if (persistedState.embeddedWorkshopModel) setEmbeddedWorkshopModel(persistedState.embeddedWorkshopModel);
        if (persistedState.embeddedWorkshopBatchSize) setEmbeddedWorkshopBatchSize(String(persistedState.embeddedWorkshopBatchSize));
        if (persistedState.embeddedWorkshopConcurrency) setEmbeddedWorkshopConcurrency(String(persistedState.embeddedWorkshopConcurrency));
        if (persistedState.embeddedWorkshopRpm) setEmbeddedWorkshopRpm(String(persistedState.embeddedWorkshopRpm));
        if (typeof persistedState.showWorkshopSettings === 'boolean') setShowWorkshopSettings(persistedState.showWorkshopSettings);
        if (persistedState.currentTaskId) setCurrentTaskId(persistedState.currentTaskId);
        if (persistedState.currentTaskMode) setCurrentTaskMode(persistedState.currentTaskMode);
        if (persistedState.completionSource) completionSourceRef.current = persistedState.completionSource;

        applyProviderSelection(
            persistedState.selectedProvider || 'gemini',
            persistedState.selectedModel || '',
            persistedState.concurrencyLimit ?? null,
        );
        if (persistedState.batchSizeLimit !== undefined && persistedState.batchSizeLimit !== null) {
            setBatchSizeLimit(String(persistedState.batchSizeLimit));
        }
        if (persistedState.rpmLimit) setRpmLimit(String(persistedState.rpmLimit));

        restorationAppliedRef.current = true;
    }, [applyProviderSelection, configLoaded, projects, projectsLoaded]);

    useEffect(() => {
        if (!projectsLoaded || !configLoaded || routePrefillAppliedRef.current) return;
        if (persistedStateRef.current?.selectedProject?.project_id) {
            routePrefillAppliedRef.current = true;
            return;
        }

        const routedProjectId = location.state?.projectId;
        if (!routedProjectId) {
            routePrefillAppliedRef.current = true;
            return;
        }

        const matchedProject = projects.find((project) => project.project_id === routedProjectId);
        routePrefillAppliedRef.current = true;
        if (matchedProject) {
            handleSelectProject(matchedProject);
        }
    }, [configLoaded, location.state, projects, projectsLoaded]);

    useEffect(() => {
        if (!archiveInfo || !selectedProject || active !== 1) return;

        const archivedLangs = getArchivedTargetLanguages(archiveInfo);
        if (archivedLangs.length === 0) {
            setErrorKey('incremental_translation.no_archived_target_languages');
            setError(null);
            return;
        }

        if (errorKey === 'incremental_translation.no_archived_target_languages') {
            setErrorKey(null);
        }
    }, [active, archiveInfo, errorKey, getArchivedTargetLanguages, selectedProject]);

    useEffect(() => {
        if (!restorationAppliedRef.current) return;

        const stateToPersist = {
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
            completionSource: completionSourceRef.current,
        };

        try {
            sessionStorage.setItem(INCREMENTAL_STATE_STORAGE_KEY, JSON.stringify(stateToPersist));
        } catch (err) {
            console.warn('Failed to persist incremental translation state:', err);
        }
    }, [
        active,
        archiveInfo,
        checkpointFound,
        checkpointInfo,
        batchSizeLimit,
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
        error,
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
    ]);

    // Fetch basics
    useEffect(() => {
        try {
            const rawState = sessionStorage.getItem(INCREMENTAL_STATE_STORAGE_KEY);
            persistedStateRef.current = rawState ? JSON.parse(rawState) : null;
        } catch (err) {
            console.warn('Failed to read incremental translation persisted state:', err);
            persistedStateRef.current = null;
        }
        fetchProjects();
        fetchApiConfig();
    }, []);

    const fetchProjects = async () => {
        try {
            const response = await api.get('/api/projects?status=active');
            const projectList = normalizeArrayPayload(response.data, ['projects', 'items', 'data', 'results']);
            setProjects(projectList);
        } catch {
            notificationService.error(t('notification.error_generic'), notificationStyle);
        } finally {
            setProjectsLoaded(true);
        }
    };

    const fetchApiConfig = async () => {
        try {
            const response = await api.get('/api/config');
            const data = response.data;
            const providers = normalizeArrayPayload(data?.api_providers, ['items', 'data', 'results']);

            setApiProviders(providers);

            const defaultProvider = data.default_provider || 'gemini';
            setSelectedProvider(defaultProvider);

            // Find models for default provider
            const providerData = providers.find(p => p.value === defaultProvider);
            if (providerData) {
                const availableModels = providerData.available_models || providerData.custom_models || [];
                setModels(availableModels);
                setSelectedModel(data.default_model || availableModels[0] || '');
            }
            setBatchSizeLimit('');
            setRpmLimit(String(data.rpm_limit || 40));
        } catch (err) {
            console.error('Failed to fetch API config', err);
        } finally {
            setConfigLoaded(true);
        }
    };

    const handleProviderChange = (val) => {
        applyProviderSelection(val);
    };

    const handleSelectProject = async (project) => {
        setSelectedProject(project);
        setCustomSourcePath(project.source_path);
        setError(null);
        setArchiveInfo(null);
        setScanResults(null);
        setFinalSummary(null);
        setLogs([]);
        setError(null);
        setErrorKey(null);
        setProgress(0);
        setProgressInfo({});
        setExecuting(false);
        setCheckpointFound(false);
        setCurrentTaskId(null);
        setCurrentTaskMode(null);
        completionSourceRef.current = null;
        statusResyncRef.current = false;
        setActive(1);

        // Immediate archive check
        try {
            setLoading(true);
            const res = await api.get(`/api/project/${project.project_id}/check-archive`);
            if (res.data.exists) {
                setArchiveInfo(res.data);
                const availableLangs = getArchivedTargetLanguages(res.data);
                setSelectedLangs(availableLangs);
                // Also check for checkpoint (resume status)
                checkCheckpoint(project, project.source_path, availableLangs);
                if (availableLangs.length === 0) {
                    setErrorKey('incremental_translation.no_archived_target_languages');
                    setError(null);
                }
            } else {
                setErrorKey('incremental_translation.archive_missing');
                setError(null);
            }
        } catch {
            setErrorKey('incremental_translation.archive_missing');
            setError(null);
        } finally {
            setLoading(false);
        }
    };

    const checkCheckpoint = async (project, sourcePath, targetLangs) => {
        try {
            const normalizedTargetLangs = Array.isArray(targetLangs) ? targetLangs.filter(Boolean) : [];
            if (normalizedTargetLangs.length === 0) {
                setCheckpointFound(false);
                setCheckpointInfo(null);
                return;
            }
            // Determine mod_name for checkpoint lookup
            const modName = sourcePath.split(/[\\/]/).pop();
            const res = await api.post('/api/translation/checkpoint-status', {
                project_id: project.project_id,
                mod_name: modName,
                target_lang_codes: normalizedTargetLangs,
            });
            if (res.data.exists && res.data.completed_count > 0) {
                setCheckpointFound(true);
                setCheckpointInfo(res.data);
                notificationService.info(t('incremental_translation.checkpoint_detected', { count: res.data.completed_count }), notificationStyle);
            } else {
                setCheckpointFound(false);
                setCheckpointInfo(null);
            }
        } catch (err) {
            console.error('Failed to check checkpoint status', err);
            setCheckpointInfo(null);
        }
    };

    const handleSelectFolder = async () => {
        try {
            const selected = await open({
                directory: true,
                multiple: false,
                title: t('incremental_translation.select_new_folder')
            });
            if (selected && typeof selected === 'string') {
                setCustomSourcePath(selected);
                // Re-check checkpoint for the new folder if project is selected
                if (selectedProject) {
                    checkCheckpoint(selectedProject, selected, selectedLangs);
                }
            }
        } catch (err) {
            console.error('Failed to open folder dialog:', err);
            notificationService.error(t('notification.error_generic'), notificationStyle);
        }
    };

    const runPreScan = async () => {
        if (!selectedProject || !customSourcePath || loading || executing || preScanInFlightRef.current || executionInFlightRef.current) return;
        const targetLangCodes = selectedLangs.length > 0 ? selectedLangs : getArchivedTargetLanguages(archiveInfo);
        if (targetLangCodes.length === 0) {
            notificationService.error(t('incremental_translation.no_archived_target_languages'), notificationStyle);
            return;
        }

        preScanInFlightRef.current = true;
        try {
            setLoading(true);
            setProgress(0);
            setProgressInfo({ percent: 0, stage_code: 'initializing', stage: t('incremental_translation.progress_stage_initializing') });
            setLogs([t('incremental_translation.pre_scan_bootstrap_log')]);
            const res = await api.post(`/api/project/${selectedProject.project_id}/incremental-update`, {
                project_id: selectedProject.project_id,
                target_lang_codes: targetLangCodes,
                dry_run: true,
                api_provider: selectedProvider,
                model: selectedModel,
                batch_size_limit: batchSizeLimit ? Number(batchSizeLimit) : null,
                concurrency_limit: Number(concurrencyLimit),
                rpm_limit: Number(rpmLimit),
                custom_source_path: customSourcePath,
                use_resume: useResume,
                embedded_workshop: {
                    enabled: embeddedWorkshopEnabled,
                    follow_primary_settings: embeddedWorkshopFollowPrimary,
                    api_provider: embeddedWorkshopFollowPrimary ? null : embeddedWorkshopProvider,
                    api_model: embeddedWorkshopFollowPrimary ? null : embeddedWorkshopModel,
                    batch_size_limit: Number(embeddedWorkshopBatchSize),
                    concurrency_limit: Number(embeddedWorkshopConcurrency),
                    rpm_limit: Number(embeddedWorkshopRpm),
                }
            });

            const taskId = res.data.task_id;
            if (taskId) {
                setCurrentTaskId(taskId);
                setCurrentTaskMode('pre_scan');
                // Connect to WebSocket and wait for the summary
                connectWebSocket(taskId, true); // true indicates pre-scan mode
            } else {
                // Fallback for immediate response (though backend is currently async)
                if (res.data.status === 'warning') {
                    notificationService.info(res.data.message || t('incremental_translation.no_files_warning'), notificationStyle);
                }
                setScanResults({
                    ...(res.data.summary || {}),
                    file_summaries: res.data.file_summaries || [],
                    telemetry: res.data.telemetry || null,
                });
                setActive(2);
                setLoading(false);
            }
        } catch (err) {
            console.error('Pre-scan error:', err);
            notificationService.error(t('notification.error_generic'), notificationStyle);
            setLoading(false);
            preScanInFlightRef.current = false;
        }
    };

    const startTranslation = async () => {
        if (loading || executing || preScanInFlightRef.current || executionInFlightRef.current) return;
        const targetLangCodes = selectedLangs.length > 0 ? selectedLangs : getArchivedTargetLanguages(archiveInfo);
        if (!selectedProject || targetLangCodes.length === 0) {
            notificationService.error(t('incremental_translation.no_archived_target_languages'), notificationStyle);
            return;
        }
        executionInFlightRef.current = true;
        setExecuting(true);
        setActive(3);
        setLogs([`[${new Date().toLocaleTimeString()}] ${t('incremental_translation.status_ws_initializing')}`]);
        setFinalSummary(null);
        setProgress(0);
        setProgressInfo({ percent: 0, stage_code: 'initializing', stage: t('incremental_translation.progress_stage_initializing') });
        completionSourceRef.current = null;

        try {
            // 1. Kick off the translation request
            const res = await api.post(`/api/project/${selectedProject.project_id}/incremental-update`, {
                project_id: selectedProject.project_id,
                target_lang_codes: targetLangCodes,
                dry_run: false,
                api_provider: selectedProvider,
                model: selectedModel,
                batch_size_limit: batchSizeLimit ? Number(batchSizeLimit) : null,
                concurrency_limit: Number(concurrencyLimit),
                rpm_limit: Number(rpmLimit),
                custom_source_path: customSourcePath,
                use_resume: useResume,
                embedded_workshop: {
                    enabled: embeddedWorkshopEnabled,
                    follow_primary_settings: embeddedWorkshopFollowPrimary,
                    api_provider: embeddedWorkshopFollowPrimary ? null : embeddedWorkshopProvider,
                    api_model: embeddedWorkshopFollowPrimary ? null : embeddedWorkshopModel,
                    batch_size_limit: Number(embeddedWorkshopBatchSize),
                    concurrency_limit: Number(embeddedWorkshopConcurrency),
                    rpm_limit: Number(embeddedWorkshopRpm),
                }
            });

            const taskId = res.data.task_id;
            if (!taskId) {
                throw new Error(t('incremental_translation.task_id_missing'));
            }

            setCurrentTaskId(taskId);
            setCurrentTaskMode('execution');
            // 2. Connect to WebSocket for real-time updates
            connectWebSocket(taskId);

        } catch (err) {
            addLog(t('incremental_translation.critical_error', { message: err.message }));
            setExecuting(false);
            executionInFlightRef.current = false;
        }
    };

    const openOutputFolder = async () => {
        const folderPath = finalSummary?.output_dir;
        if (!folderPath) return;

        try {
            await api.post('/api/system/open_folder', { path: folderPath });
        } catch (err) {
            console.error('Failed to open incremental output folder:', err);
            notificationService.error(t('notification.error_generic'), notificationStyle);
        }
    };

    const clearTaskPolling = () => {
        if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
        }
    };

    const handleTaskUpdate = (data, isPreScan = false, source = 'unknown') => {
        if (!data) return;

        if (data.progress) {
            setProgress(data.progress.percent || 0);
            setProgressInfo(data.progress);
        }

        if (data.log) {
            setLogs(data.log);
        }

        if (data.status === 'completed') {
            completionSourceRef.current = source;
            console.info(`Incremental task completed via ${source}.`);
            clearTaskPolling();
            if (isPreScan) {
                preScanInFlightRef.current = false;
                setCurrentTaskId(null);
                setCurrentTaskMode(null);
                setScanResults({
                    ...(data.summary || {}),
                    file_summaries: data.file_summaries || [],
                    telemetry: data.telemetry || null,
                });
                setActive(2);
                setLoading(false);
            } else {
                executionInFlightRef.current = false;
                setFinalSummary(data);
                addLog(t('incremental_translation.translation_completed_success'));
                setProgress(100);
                setProgressInfo(data.progress || {});
                setExecuting(false);
            }
            if (wsRef.current) {
                wsRef.current.close();
            }
        } else if (data.status === 'failed') {
            completionSourceRef.current = source;
            console.warn(`Incremental task failed via ${source}.`);
            clearTaskPolling();
            addLog(t('incremental_translation.task_failed_check_logs'));
            if (isPreScan) {
                preScanInFlightRef.current = false;
                setCurrentTaskId(null);
                setCurrentTaskMode(null);
                setLoading(false);
            } else {
                executionInFlightRef.current = false;
                setExecuting(false);
            }
            if (wsRef.current) {
                wsRef.current.close();
            }
        }
    };

    const startTaskPolling = (taskId, isPreScan = false) => {
        clearTaskPolling();
        console.info(`Starting polling fallback for incremental task ${taskId}.`);
        pollTimerRef.current = setInterval(async () => {
            try {
            const res = await api.get(`/api/status/${taskId}`);
                handleTaskUpdate(res.data, isPreScan, 'polling');
            } catch (err) {
                console.error('Polling task status failed:', err);
            }
        }, 1000);
    };

    const connectWebSocket = (taskId, isPreScan = false) => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const wsUrl = `${protocol}//${host}/api/ws/status/${taskId}`;

        console.log(`Connecting to WS (${isPreScan ? 'Pre-scan' : 'Execution'}): ${wsUrl}`);
        if (wsRef.current) wsRef.current.close();
        startTaskPolling(taskId, isPreScan);
        
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            console.info(`Incremental task WebSocket connected: ${taskId}`);
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleTaskUpdate(data, isPreScan, 'websocket');
        };

        ws.onerror = (err) => {
            console.error('WebSocket Error:', err);
            addLog(t('incremental_translation.status_ws_error'));
        };

        ws.onclose = () => {
            console.log('WebSocket connection closed.');
        };
    };

    // Clean up WS on unmount
    useEffect(() => {
        return () => {
            clearTaskPolling();
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, []);

    useEffect(() => {
        if (!restorationAppliedRef.current || statusResyncRef.current || !currentTaskId || !currentTaskMode) return;
        if (!loading && !executing) return;

        statusResyncRef.current = true;

        const isPreScan = currentTaskMode === 'pre_scan';
            api.get(`/api/status/${currentTaskId}`)
            .then((res) => {
                const taskStatus = res.data?.status;
                if (taskStatus === 'completed' || taskStatus === 'failed') {
                    handleTaskUpdate(res.data, isPreScan, 'polling');
                    return;
                }
                connectWebSocket(currentTaskId, isPreScan);
            })
            .catch((resumeErr) => {
                console.error('Failed to resume incremental task state:', resumeErr);
                connectWebSocket(currentTaskId, isPreScan);
            });
    }, [currentTaskId, currentTaskMode, executing, loading]);

    const addLog = (msg) => {
        setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
    };

    const handleFinish = () => {
        resetPersistedState();
        navigate('/project-management');
    };

    useEffect(() => {
        if (logViewportRef.current) {
            logViewportRef.current.scrollTo({ top: logViewportRef.current.scrollHeight, behavior: 'smooth' });
        }
    }, [logs]);

    const prevStep = () => setActive((current) => (current > 0 ? current - 1 : current));

    useEffect(() => {
        setPageContext((prev) => {
            const nextContext = `incremental-translation-step-${active}`;
            return prev === nextContext ? prev : nextContext;
        });
    }, [active, setPageContext]);

    useEffect(() => {
        const tutorialKey = getTutorialKey('incremental-translation_prompt_seen');
        if (!localStorage.getItem(tutorialKey)) {
            setShowTutorialPrompt(true);
        }
    }, []);

    return (
        <Container size="xl" py="xl" className={styles.incrementalPage}>
            <Title order={2} mb="xl" className={styles.pageTitle}>
                <IconRocket size={32} style={{ marginRight: 12, verticalAlign: 'middle' }} />
                {t('incremental_translation.title')}
            </Title>

            <Stepper active={active} onStepClick={setActive} allowNextStepsSelect={false} breakpoint="sm">
                {/* --- Step 1: Select Project --- */}
                <Stepper.Step
                    label={t('incremental_translation.step_1_title')}
                    description={t('incremental_translation.step_1_desc')}
                    icon={<IconSearch size={18} />}
                >
                    <Stack mt="xl" className={styles.executionStep}>
                        <Paper id="incremental-project-selector" withBorder p="md" radius="md" className={styles.glassCard}>
                            <Group grow align="flex-end">
                                <TextInput
                                    label={t('common.search', { defaultValue: 'Search' })}
                                    placeholder={t('incremental_translation.project_search_placeholder')}
                                    value={searchQuery}
                                    onChange={(event) => setSearchQuery(event.currentTarget.value)}
                                    leftSection={<IconSearch size={16} />}
                                />
                                <Select
                                    label={t('common.filter_game')}
                                    data={gameFilterOptions}
                                    value={gameFilter}
                                    onChange={(value) => setGameFilter(value || 'all')}
                                />
                            </Group>
                        </Paper>
                        <SimpleGrid id="incremental-project-grid" cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
                            {filteredProjects.map((p) => (
                                <Card
                                    key={p.project_id}
                                    padding="lg"
                                    radius="md"
                                    withBorder
                                    onClick={() => handleSelectProject(p)}
                                    style={{ cursor: 'pointer', transition: 'transform 0.2s' }}
                                    className={selectedProject?.project_id === p.project_id ? styles.selectedCard : styles.glassCard}
                                >
                                    <Stack gap="xs">
                                        <Box>
                                            <Title order={5}>{p.name}</Title>
                                            <Text size="xs" c="dimmed">{t('incremental_translation.project_folder')}: {p.source_path?.split(/[\\/]/).pop()}</Text>
                                        </Box>
                                        <Group gap="xs">
                                            <Badge color="blue" variant="light">{t('incremental_translation.project_game')}: {p.game_id}</Badge>
                                            <Badge color="teal" variant="light">{t('incremental_translation.project_source_language')}: {p.source_language}</Badge>
                                        </Group>
                                        <Text size="xs" c="dimmed" lineClamp={2}>{p.source_path}</Text>
                                    </Stack>
                                </Card>
                            ))}
                        </SimpleGrid>
                        {filteredProjects.length === 0 && (
                            <Paper withBorder p="xl" radius="md" className={styles.glassCard}>
                                <Text ta="center" c="dimmed">
                                    {t('common.nothing_found')}
                                </Text>
                            </Paper>
                        )}
                    </Stack>
                </Stepper.Step>

                {/* --- Step 2: Validation & Setup --- */}
                <Stepper.Step
                    label={t('incremental_translation.step_2_title')}
                    description={t('incremental_translation.step_2_desc')}
                    icon={<IconSettings size={18} />}
                >
                    <Stack mt="xl" gap="md" style={{ position: 'relative' }}>
                        {loading && (
                            <Paper withBorder p="md" radius="md">
                                <Stack gap="xs">
                                    <Group justify="space-between">
                                        <Text size="sm" fw={600}>{getStageTitle(progressInfo, true)}</Text>
                                        <Badge color="blue" variant="light">{progress}%</Badge>
                                    </Group>
                                    <Progress value={progress} animated />
                                    <Text size="sm">{getStageDescription(progressInfo)}</Text>
                                    <Text size="xs" c="dimmed">{logs[logs.length - 1]}</Text>
                                </Stack>
                            </Paper>
                        )}

                        {(errorKey || error) && (
                            <Alert icon={<IconAlertCircle size={16} />} title={t('incremental_translation.error_title')} color="red" radius="md">
                                {errorKey ? t(errorKey) : error}
                                <Box mt="sm">
                                    <Text size="sm">{t('incremental_translation.archive_missing_action')}</Text>
                                </Box>
                                <Button variant="outline" color="red" size="xs" mt="md" onClick={() => setActive(0)}>
                                    {t('common.back')}
                                </Button>
                            </Alert>
                        )}

                        {archiveInfo && (
                            <Paper id="incremental-setup-card" withBorder p="lg" radius="md" className={styles.glassCard}>
                                <Stack>
                                    <Alert icon={<IconCheck size={16} />} color="blue" radius="md">
                                        <Text size="sm" fw={600}>{t('incremental_translation.workflow_supported_title')}</Text>
                                        <Text size="sm">{t('incremental_translation.workflow_supported_desc')}</Text>
                                    </Alert>
                                    <Card id="incremental-project-details-card" withBorder p="md" radius="md">
                                        <Text size="sm" fw={600} mb="sm">{t('incremental_translation.project_details_title')}</Text>
                                        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                                            <Box>
                                                <Text size="xs" c="dimmed">{t('incremental_translation.project_name')}</Text>
                                                <Text size="sm">{archiveInfo.project_name || selectedProject?.name}</Text>
                                            </Box>
                                            <Box>
                                                <Text size="xs" c="dimmed">{t('incremental_translation.project_game')}</Text>
                                                <Text size="sm">{selectedProject?.game_id}</Text>
                                            </Box>
                                            <Box>
                                                <Text size="xs" c="dimmed">{t('incremental_translation.project_source_language')}</Text>
                                                <Text size="sm">{selectedProject?.source_language}</Text>
                                            </Box>
                                            <Box>
                                                <Text size="xs" c="dimmed">{t('incremental_translation.project_folder')}</Text>
                                                <Text size="sm">{selectedProject?.source_path?.split(/[\\/]/).pop()}</Text>
                                            </Box>
                                            <Box>
                                                <Text size="xs" c="dimmed">{t('incremental_translation.archived_target_languages')}</Text>
                                                <Text size="sm">
                                                    {getArchivedTargetLanguages(archiveInfo).length > 0
                                                        ? getArchivedTargetLanguages(archiveInfo).join(', ')
                                                        : t('incremental_translation.none_archived')}
                                                </Text>
                                            </Box>
                                            <Box>
                                                <Text size="xs" c="dimmed">{t('incremental_translation.selected_target_languages')}</Text>
                                                <Text size="sm">
                                                    {selectedLangs.length > 0
                                                        ? selectedLangs.join(', ')
                                                        : t('incremental_translation.none_selected')}
                                                </Text>
                                            </Box>
                                        </SimpleGrid>
                                    </Card>

                                    {Array.isArray(archiveInfo.baseline_versions) && archiveInfo.baseline_versions.length > 0 && (
                                        <Card withBorder p="md" radius="md">
                                            <Text size="sm" fw={600} mb="sm">{t('incremental_translation.archive_baseline_title')}</Text>
                                            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
                                                {archiveInfo.baseline_versions.map((baseline) => (
                                                    <Card key={baseline.language} withBorder p="sm" radius="md">
                                                        <Group justify="space-between" mb="xs">
                                                            <Text size="sm" fw={600}>{baseline.language}</Text>
                                                            <Badge color="indigo" variant="light">v{baseline.version_id ?? '--'}</Badge>
                                                        </Group>
                                                        <Stack gap={6}>
                                                            <Box>
                                                                <Text size="xs" c="dimmed">{t('incremental_translation.archive_uploaded_label')}</Text>
                                                                <Text size="sm">{formatDateTime(baseline.last_translation_at)}</Text>
                                                            </Box>
                                                            <Box>
                                                                <Text size="xs" c="dimmed">{t('incremental_translation.archive_snapshot_label')}</Text>
                                                                <Text size="sm">{formatDateTime(baseline.created_at)}</Text>
                                                            </Box>
                                                            <Box>
                                                                <Text size="xs" c="dimmed">{t('incremental_translation.archive_entries_label')}</Text>
                                                                <Text size="sm">{baseline.translated_count ?? '--'}</Text>
                                                            </Box>
                                                        </Stack>
                                                    </Card>
                                                ))}
                                            </SimpleGrid>
                                        </Card>
                                    )}

                                    <Group justify="space-between">
                                        <Title order={4}>
                                            {t('incremental_translation.step_2_title')} - {archiveInfo.project_name || selectedProject?.name}
                                        </Title>
                                        <Group gap="xs">
                                            {checkpointFound && (
                                                <Badge color="orange" variant="filled">
                                                    {t('incremental_translation.checkpoint_found_label')}
                                                </Badge>
                                            )}
                                            <Badge color="green" leftSection={<IconCheck size={12} />}>
                                                {t('incremental_translation.archive_found', {
                                                    version: String(archiveInfo.version_id ?? '').slice(0, 8),
                                                    date: new Date(archiveInfo.created_at).toLocaleDateString()
                                                })}
                                            </Badge>
                                        </Group>
                                    </Group>

                                    <Divider />

                                    {checkpointFound && (
                                        <Alert icon={<IconSettings size={16} />} title={t('incremental_translation.checkpoint_found_title')} color="orange" radius="md">
                                            <Stack gap="sm">
                                                <Group justify="space-between">
                                                    <Text size="sm">{t('incremental_translation.checkpoint_found_desc')}</Text>
                                                    <Button
                                                        size="xs"
                                                        variant={useResume ? "filled" : "outline"}
                                                        color="orange"
                                                        onClick={() => setUseResume(!useResume)}
                                                    >
                                                        {useResume ? t('incremental_translation.resume_enabled') : t('incremental_translation.resume_disabled')}
                                                    </Button>
                                                </Group>
                                                <Group justify="space-between">
                                                    <Text size="xs" c="dimmed">
                                                        {t('incremental_translation.resume_detail_subtitle', { defaultValue: '展开后可查看上次断点续传完成到什么时间、什么批次。' })}
                                                    </Text>
                                                    <Button
                                                        variant="subtle"
                                                        size="xs"
                                                        onClick={() => setShowResumeDetails((value) => !value)}
                                                    >
                                                        {showResumeDetails
                                                            ? t('common.collapse', { defaultValue: '收起' })
                                                            : t('common.expand', { defaultValue: '展开' })}
                                                    </Button>
                                                </Group>
                                                <Collapse in={showResumeDetails}>
                                                    <Stack gap="xs">
                                                        {(checkpointInfo?.targets || []).map((target) => (
                                                            <Card key={target.target_lang_code} withBorder p="sm" radius="md">
                                                                <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
                                                                    <Box>
                                                                        <Text size="xs" c="dimmed">{t('translation_config.target_languages')}</Text>
                                                                        <Text size="sm" fw={600}>{target.target_lang_code}</Text>
                                                                    </Box>
                                                                    <Box>
                                                                        <Text size="xs" c="dimmed">{t('translation_page.resume_detail_completed', { defaultValue: '已完成文件' })}</Text>
                                                                        <Text size="sm">{target.completed_count ?? 0}</Text>
                                                                    </Box>
                                                                    <Box>
                                                                        <Text size="xs" c="dimmed">{t('translation_page.resume_detail_batch', { defaultValue: '上次批次' })}</Text>
                                                                        <Text size="sm">{`${target.metadata?.current_batch ?? 0} / ${target.metadata?.total_batches ?? 0}`}</Text>
                                                                    </Box>
                                                                    <Box>
                                                                        <Text size="xs" c="dimmed">{t('translation_page.resume_detail_time', { defaultValue: '上次保存' })}</Text>
                                                                        <Text size="sm">{target.last_saved_at || target.metadata?.last_saved_at || '--'}</Text>
                                                                    </Box>
                                                                    <Box style={{ gridColumn: '1 / -1' }}>
                                                                        <Text size="xs" c="dimmed">{t('translation_page.resume_detail_file', { defaultValue: '最后完成文件' })}</Text>
                                                                        <Text size="sm">{target.last_completed_file || target.metadata?.last_completed_file || '--'}</Text>
                                                                    </Box>
                                                                </SimpleGrid>
                                                            </Card>
                                                        ))}
                                                    </Stack>
                                                </Collapse>
                                            </Stack>
                                        </Alert>
                                    )}

                                    <Card id="incremental-embedded-workshop" withBorder p="md" radius="md">
                                        <Stack gap="sm">
                                            <Switch
                                                label={t('translation_page.embedded_workshop_enabled', { defaultValue: '在增量翻译里嵌入智能工坊格式校对' })}
                                                description={t('translation_page.embedded_workshop_enabled_desc', { defaultValue: '默认开启。翻译完成后自动进行格式校对与修复，再刷新问题清单。' })}
                                                checked={embeddedWorkshopEnabled}
                                                onChange={(event) => setEmbeddedWorkshopEnabled(event.currentTarget.checked)}
                                            />
                                            <Group justify="space-between">
                                                <div>
                                                    <Text size="sm" fw={600}>
                                                        {t('translation_page.embedded_workshop_settings', { defaultValue: '智能工坊设置' })}
                                                    </Text>
                                                    <Text size="xs" c="dimmed">
                                                        {t('translation_page.embedded_workshop_settings_desc', { defaultValue: '默认收起。展开后可给校对单独指定模型与速率。' })}
                                                    </Text>
                                                </div>
                                                <Button
                                                    variant="subtle"
                                                    size="xs"
                                                    onClick={() => setShowWorkshopSettings((value) => !value)}
                                                >
                                                    {showWorkshopSettings
                                                        ? t('common.collapse', { defaultValue: '收起' })
                                                        : t('common.expand', { defaultValue: '展开' })}
                                                </Button>
                                            </Group>
                                            <Collapse in={showWorkshopSettings}>
                                                <Stack gap="sm">
                                                    <Switch
                                                        label={t('translation_page.embedded_workshop_follow', { defaultValue: '默认跟随当前翻译 API 与模型' })}
                                                        description={t('translation_page.embedded_workshop_follow_desc', { defaultValue: '关闭后可以改成独立校对模型，例如大模型翻译、小模型校对。' })}
                                                        checked={embeddedWorkshopFollowPrimary}
                                                        onChange={(event) => setEmbeddedWorkshopFollowPrimary(event.currentTarget.checked)}
                                                    />
                                                    {!embeddedWorkshopFollowPrimary && (
                                                        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                                                            <Select
                                                                label={t('translation_page.embedded_workshop_provider', { defaultValue: '校对 API' })}
                                                                data={apiProviders.map((provider) => ({ value: provider.value, label: provider.label }))}
                                                                value={embeddedWorkshopProvider}
                                                                onChange={(value) => {
                                                                    setEmbeddedWorkshopProvider(value || '');
                                                                    setEmbeddedWorkshopModel(resolveProviderModels(value || '')[0] || '');
                                                                }}
                                                            />
                                                            <Select
                                                                label={t('translation_page.embedded_workshop_model', { defaultValue: '校对模型' })}
                                                                data={resolveProviderModels(embeddedWorkshopProvider).map((model) => ({ value: model, label: model }))}
                                                                value={embeddedWorkshopModel}
                                                                onChange={setEmbeddedWorkshopModel}
                                                                searchable
                                                            />
                                                        </SimpleGrid>
                                                    )}
                                                    <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
                                                        <Select
                                                            label={renderInfoLabel(t('translation_page.embedded_workshop_batch_size'), t('translation_page.embedded_workshop_batch_size_tooltip'))}
                                                            data={workshopBatchOptions}
                                                            value={embeddedWorkshopBatchSize}
                                                            onChange={setEmbeddedWorkshopBatchSize}
                                                        />
                                                        <Select
                                                            label={renderInfoLabel(t('translation_page.embedded_workshop_concurrency'), t('translation_page.embedded_workshop_concurrency_tooltip'))}
                                                            data={workshopConcurrencyOptions}
                                                            value={embeddedWorkshopConcurrency}
                                                            onChange={setEmbeddedWorkshopConcurrency}
                                                        />
                                                        <Select
                                                            label={renderInfoLabel(t('translation_page.embedded_workshop_rpm'), t('translation_page.embedded_workshop_rpm_tooltip'))}
                                                            data={workshopRpmOptions}
                                                            value={embeddedWorkshopRpm}
                                                            onChange={setEmbeddedWorkshopRpm}
                                                        />
                                                    </SimpleGrid>
                                                </Stack>
                                            </Collapse>
                                        </Stack>
                                    </Card>

                                    <Box id="incremental-target-languages">
                                        <MultiSelect
                                            label={t('translation_config.target_languages')}
                                            description={t('incremental_translation.target_lang_desc')}
                                            data={getArchivedTargetLanguages(archiveInfo).map(lang => ({ value: lang, label: lang }))}
                                            value={selectedLangs}
                                            onChange={setSelectedLangs}
                                            required
                                            clearable
                                        />
                                    </Box>
                                    {getArchivedTargetLanguages(archiveInfo).length === 0 && (
                                        <Alert icon={<IconAlertCircle size={16} />} color="orange" radius="md">
                                            {t('incremental_translation.no_archived_target_languages')}
                                        </Alert>
                                    )}

                                    <Box id="incremental-folder-picker">
                                        <Text size="sm" fw={500} mb={4}>{t('incremental_translation.select_new_folder')}</Text>
                                        <Group gap="xs">
                                            <TextInput
                                                style={{ flex: 1 }}
                                                value={customSourcePath}
                                                readOnly
                                            />
                                            <Button variant="light" leftSection={<IconFolderOpen size={16} />} onClick={handleSelectFolder}>
                                                {t('common.browse')}
                                            </Button>
                                        </Group>
                                        <Text size="xs" c="dimmed" mt={4}>
                                            {t('incremental_translation.current_folder_info', { path: selectedProject?.source_path })}
                                        </Text>
                                    </Box>

                                    <Group justify="flex-end" mt="md">
                                        <Button variant="light" onClick={prevStep}>{t('common.back')}</Button>
                                        <Button id="incremental-run-prescan-btn" onClick={runPreScan}>{t('incremental_translation.step_3_title')}</Button>
                                    </Group>
                                </Stack>
                            </Paper>
                        )}
                    </Stack>
                </Stepper.Step>

                {/* --- Step 3: Pre-scan Results --- */}
                <Stepper.Step
                    label={t('incremental_translation.step_3_title')}
                    description={t('incremental_translation.step_3_desc')}
                    icon={<IconChartBar size={18} />}
                >
                    <Stack mt="xl">
                        {scanResults && (
                            <Paper id="incremental-prescan-summary" withBorder p="xl" radius="md" className={styles.glassCard}>
                                <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} mb="lg">
                                    <Select
                                        label={t('translation_config.provider')}
                                        data={apiProviders.map(p => ({ value: p.value, label: p.label }))}
                                        value={selectedProvider}
                                        onChange={handleProviderChange}
                                    />
                                    <Select
                                        label={t('translation_config.model')}
                                        data={models.map(m => ({ value: m, label: m }))}
                                        value={selectedModel}
                                        onChange={setSelectedModel}
                                        searchable
                                    />
                                    <Select
                                        label={renderInfoLabel(
                                            t('translation_page.translation_batch_size'),
                                            t('translation_page.translation_batch_size_tooltip'),
                                        )}
                                        data={batchSizeOptions}
                                        value={batchSizeLimit}
                                        onChange={setBatchSizeLimit}
                                    />
                                    <Select
                                        label={renderInfoLabel(
                                            t('incremental_translation.concurrency_limit'),
                                            t('translation_page.translation_concurrency_tooltip'),
                                        )}
                                        data={concurrencyOptions}
                                        value={concurrencyLimit}
                                        onChange={setConcurrencyLimit}
                                    />
                                    <Select
                                        label={renderInfoLabel(
                                            t('incremental_translation.rpm_limit'),
                                            t('translation_page.translation_rpm_tooltip'),
                                        )}
                                        data={rpmOptions}
                                        value={rpmLimit}
                                        onChange={setRpmLimit}
                                    />
                                </SimpleGrid>

                                <Title order={4} mb="md">{t('incremental_translation.pre_scan_summary')}</Title>
                                <SimpleGrid cols={2} mb="lg">
                                    <Box>
                                        <Text size="xs" c="dimmed">{t('incremental_translation.scan_directory')}</Text>
                                        <Text size="sm" truncate>{customSourcePath}</Text>
                                    </Box>
                                    <Box>
                                        <Text size="xs" c="dimmed">{t('incremental_translation.source_language')}</Text>
                                        <Text size="sm">{selectedProject?.source_language}</Text>
                                    </Box>
                                </SimpleGrid>

                                <Alert icon={<IconSettings size={16} />} color="gray" radius="md" mb="lg">
                                    <Text size="sm" fw={600}>{t('incremental_translation.workflow_supported_title')}</Text>
                                    <Text size="sm">{t('incremental_translation.workflow_supported_desc')}</Text>
                                </Alert>

                                <Divider mb="lg" />

                                <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md" mb="xl">
                                    <Card withBorder p="md" radius="md">
                                        <Text size="xs" c="dimmed" mb={4}>{t('summary_total')}</Text>
                                        <Title order={3}>{scanResults.total}</Title>
                                    </Card>
                                    <Card withBorder p="md" radius="md" style={{ borderLeft: '4px solid var(--mantine-color-green-6)' }}>
                                        <Text size="xs" c="dimmed" mb={4}>{t('incremental_translation.reused_count', { count: '' })}</Text>
                                        <Title order={3} c="green">{scanResults.unchanged}</Title>
                                    </Card>
                                    <Card withBorder p="md" radius="md" style={{ borderLeft: '4px solid var(--mantine-color-orange-6)' }}>
                                        <Text size="xs" c="dimmed" mb={4}>{t('incremental_translation.new_count', { count: '' })}</Text>
                                        <Title order={3} c="orange">{scanResults.new + scanResults.changed}</Title>
                                    </Card>
                                </SimpleGrid>

                                <Alert icon={<IconAlertCircle size={16} />} color="blue">
                                    {t('incremental_translation.start_translation_confirm')}
                                </Alert>

                                <Group justify="flex-end" mt="md">
                                    <Button variant="light" onClick={prevStep} disabled={loading || executing}>
                                        {t('common.back')}
                                    </Button>
                                    <Button
                                        id="incremental-start-run-btn"
                                        size="lg"
                                        leftSection={<IconPlayerPlay size={20} />}
                                        onClick={startTranslation}
                                        disabled={loading || executing}
                                    >
                                        {t('incremental_translation.step_4_title')}
                                    </Button>
                                </Group>

                                {renderTelemetry(scanResults.telemetry)}

                                {renderFileDetails(scanResults.file_summaries)}
                            </Paper>
                        )}
                    </Stack>
                </Stepper.Step>

                {/* --- Step 4: Execution --- */}
                <Stepper.Completed>
                    <Stack mt="xl">
                        <Paper id="incremental-execution-panel" withBorder p="xl" radius="md" className={styles.glassCard}>
                            <Title order={4} mb="md">{t('incremental_translation.execution_log')}</Title>

                            <Progress
                                value={progress}
                                label={progress > 0 ? `${progress}%` : ''}
                                size="xl"
                                radius="xl"
                                animated={executing}
                                mb="sm"
                            />

                            <Group justify="space-between" mb="xl">
                                <Box>
                                    <Text size="sm" fw={600}>{getStageTitle(progressInfo, false)}</Text>
                                    <Text size="xs" c="dimmed">{getStageDescription(progressInfo) || (executing ? t('incremental_translation.status_processing') : t('incremental_translation.status_idle'))}</Text>
                                </Box>
                                <Text size="xs" fw={700} c="blue">
                                    {progress}%
                                </Text>
                            </Group>

                            <Box
                                ref={logViewportRef}
                                className={styles.logScrollBox}
                            >
                                <div ref={logScrollRef}>
                                    {logs.map((log, i) => {
                                        const isError = log.includes('ERROR') || log.includes('failed');
                                        return (
                                            <Text key={i} size="xs" style={{ fontFamily: 'monospace', color: isError ? '#ff6b6b' : 'inherit' }} mb={2}>
                                                {log}
                                            </Text>
                                        );
                                    })}
                                </div>
                            </Box>

                            {finalSummary && (
                                <Stack id="incremental-final-summary" mt="xl">
                                    <Title order={4} c="green">{t('incremental_translation.completion_title')}</Title>
                                    {finalSummary.warning_count > 0 && (
                                        <Alert color="orange" title={t('incremental_translation.runtime_warning_summary_title')}>
                                            <Text size="sm">
                                                {t('incremental_translation.runtime_warning_summary_desc', { count: finalSummary.warning_count })}
                                            </Text>
                                            {(finalSummary.warnings || []).slice(0, 3).map((warning, index) => (
                                                <Text key={`${warning.type || 'warning'}-${index}`} size="xs" c="dimmed" mt={4}>
                                                    - {warning.line_number ? `L${warning.line_number} | ` : ''}{formatWarningMessage(warning)}
                                                </Text>
                                            ))}
                                        </Alert>
                                    )}
                                    {getValidationIssueCount(finalSummary) > 0 && (
                                        <Alert color="yellow" title={t('incremental_translation.validation_issue_summary_title')}>
                                            <Text size="sm">
                                                {t('incremental_translation.validation_issue_summary_desc', { count: getValidationIssueCount(finalSummary) })}
                                            </Text>
                                            {(finalSummary.workshop_issue_exports || []).map((exportInfo) => (
                                                exportInfo?.issues_path ? (
                                                    <Text key={exportInfo.issues_path} size="xs" c="dimmed" mt={4}>
                                                        - {t('incremental_translation.validation_issue_export_item', {
                                                            lang: exportInfo.target_lang || 'default',
                                                            count: exportInfo.issue_count || 0,
                                                            path: exportInfo.issues_path,
                                                        })}
                                                    </Text>
                                                ) : null
                                            ))}
                                        </Alert>
                                    )}
                                    <Alert color="green">
                                        <Stack gap={4}>
                                            <Text size="sm">{t('incremental_translation.output_dir_hint')}</Text>
                                            {finalSummary.output_dir && (
                                                <Text size="xs" c="dimmed">{finalSummary.output_dir}</Text>
                                            )}
                                            {finalSummary.output_dir && (
                                                <Text size="xs" c="dimmed">
                                                    {t('incremental_translation.log_file_hint', { path: `${finalSummary.output_dir}\\incremental_update.log` })}
                                                </Text>
                                            )}
                                            <Text size="xs" c="dimmed">
                                                {t('incremental_translation.transport_status', {
                                                    source: completionSourceRef.current || 'polling',
                                                })}
                                            </Text>
                                        </Stack>
                                    </Alert>
                                    {renderTelemetry(finalSummary.telemetry)}
                                    <Group>
                                        <Button size="lg" variant="light" onClick={openOutputFolder}>
                                            {t('button_open_folder')}
                                        </Button>
                                        <Button size="lg" onClick={handleFinish}>
                                            {t('common.finish')}
                                        </Button>
                                    </Group>
                                </Stack>
                            )}
                        </Paper>
                    </Stack>
                </Stepper.Completed>
            </Stepper>

            <Modal
                opened={showTutorialPrompt}
                onClose={() => {
                    setShowTutorialPrompt(false);
                    localStorage.setItem(getTutorialKey('incremental-translation_prompt_seen'), 'true');
                }}
                title={t('tutorial.auto_start_prompt.title')}
                centered
                radius="md"
            >
                <Stack>
                    <Text size="sm">{t('tutorial.auto_start_prompt.message')}</Text>
                    <Group justify="flex-end" mt="md">
                        <Button
                            variant="subtle"
                            color="gray"
                            onClick={() => {
                                setShowTutorialPrompt(false);
                                localStorage.setItem(getTutorialKey('incremental-translation_prompt_seen'), 'true');
                            }}
                        >
                            {t('tutorial.auto_start_prompt.cancel')}
                        </Button>
                        <Button
                            color="blue"
                            onClick={() => {
                                setShowTutorialPrompt(false);
                                localStorage.setItem(getTutorialKey('incremental-translation_prompt_seen'), 'true');
                                startTour();
                            }}
                        >
                            {t('tutorial.auto_start_prompt.confirm')}
                        </Button>
                    </Group>
                </Stack>
            </Modal>
        </Container>
    );
};

export default IncrementalTranslationPage;
