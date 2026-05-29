import React, { useCallback } from 'react';
import {
    Stack,
    Paper,
    Card,
    SimpleGrid,
    Box,
    Text,
    Badge,
    Group,
    Title,
    Divider,
    Alert,
    Collapse,
    Button,
    TextInput,
    MultiSelect,
    Select,
    Switch,
    Accordion,
    Tooltip,
    ThemeIcon,
} from '@mantine/core';
import {
    IconCheck,
    IconAlertCircle,
    IconSettings,
    IconFolderOpen,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import PerformanceControlPanel from '../shared/PerformanceControlPanel';
import styles from '../../pages/Translation.module.css';

export const ConfigStep = ({
    loading,
    error,
    errorKey,
    archiveInfo,
    selectedProject,
    checkpointFound,
    checkpointInfo,
    useResume,
    setUseResume,
    showResumeDetails,
    setShowResumeDetails,
    selectedProvider,
    handleProviderChange,
    selectedModel,
    setSelectedModel,
    models,
    customSourcePath,
    onSelectFolder,
    selectedLangs,
    setSelectedLangs,
    batchSizeLimit,
    setBatchSizeLimit,
    concurrencyLimit,
    setConcurrencyLimit,
    rpmLimit,
    setRpmLimit,
    
    // Embedded Workshop
    embeddedWorkshopEnabled,
    setEmbeddedWorkshopEnabled,
    embeddedWorkshopFollowPrimary,
    setEmbeddedWorkshopFollowPrimary,
    embeddedWorkshopProvider,
    setEmbeddedWorkshopProvider,
    embeddedWorkshopModel,
    setEmbeddedWorkshopModel,
    embeddedWorkshopBatchSize,
    setEmbeddedWorkshopBatchSize,
    embeddedWorkshopConcurrency,
    setEmbeddedWorkshopConcurrency,
    embeddedWorkshopRpm,
    setEmbeddedWorkshopRpm,
    showWorkshopSettings,
    setShowWorkshopSettings,
    apiProviders,

    // Actions
    runPreScan,
    onBack,
}) => {
    const { t } = useTranslation();

    const formatDateTime = useCallback((value) => {
        if (!value) return '--';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleString();
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

    const targetLangOptions = getArchivedTargetLanguages(archiveInfo).map((lang) => ({
        value: lang,
        label: lang.toUpperCase(),
    }));

    return (
        <Stack mt="xl" gap="md" style={{ position: 'relative' }}>
            {(errorKey || error) && (
                <Alert icon={<IconAlertCircle size={16} />} title={t('incremental_translation.error_title')} color="red" radius="md">
                    {errorKey ? t(errorKey) : error}
                    <Box mt="sm">
                        <Text size="sm">{t('incremental_translation.archive_missing_action')}</Text>
                    </Box>
                    <Button variant="outline" color="red" size="xs" mt="md" onClick={onBack}>
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
                                            onClick={() => setShowResumeDetails(!showResumeDetails)}
                                        >
                                            {showResumeDetails ? t('common.collapse', { defaultValue: '收起' }) : t('common.expand', { defaultValue: '展开' })}
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

                        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                            <TextInput
                                label={t('translation_config.source_path')}
                                value={customSourcePath}
                                onChange={(e) => {}}
                                readOnly
                                rightSection={
                                    <Tooltip label={t('translation_config.select_path_tooltip')}>
                                        <ThemeIcon variant="subtle" color="blue" style={{ cursor: 'pointer' }} onClick={onSelectFolder}>
                                            <IconFolderOpen size={16} />
                                        </ThemeIcon>
                                    </Tooltip>
                                }
                            />
                            <MultiSelect
                                label={t('translation_config.target_languages')}
                                data={targetLangOptions}
                                value={selectedLangs}
                                onChange={setSelectedLangs}
                            />
                        </SimpleGrid>

                        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                            <Select
                                label={t('translation_config.api_provider')}
                                data={apiProviders}
                                value={selectedProvider}
                                onChange={handleProviderChange}
                            />
                            <Select
                                label={t('translation_config.api_model')}
                                data={models}
                                value={selectedModel}
                                onChange={setSelectedModel}
                                disabled={models.length === 0}
                            />
                        </SimpleGrid>

                        {/* Renders PerformanceControlPanel for primary translation settings */}
                        <Card withBorder p="md" radius="md">
                            <Text size="sm" fw={600} mb="xs">{t('translation_page.performance_settings', { defaultValue: '性能限制' })}</Text>
                            <PerformanceControlPanel
                                batchSize={batchSizeLimit}
                                onChangeBatchSize={setBatchSizeLimit}
                                concurrency={concurrencyLimit}
                                onChangeConcurrency={setConcurrencyLimit}
                                rpm={rpmLimit}
                                onChangeRpm={setRpmLimit}
                            />
                        </Card>

                        {/* --- Embedded Workshop Settings (Accordion) --- */}
                        <Accordion variant="separated" radius="md">
                            <Accordion.Item value="embedded-workshop">
                                <Accordion.Control>
                                    <Group justify="space-between" wrap="nowrap">
                                        <Box>
                                            <Text fw={600}>{t('translation_page.embedded_workshop_title', { defaultValue: '智能工坊 (校对插件)' })}</Text>
                                            <Text size="xs" c="dimmed">
                                                {t('translation_page.embedded_workshop_subtitle', { defaultValue: '在生成翻译后，顺便进行文本智能润饰与格式校对。' })}
                                            </Text>
                                        </Box>
                                        <Switch
                                            checked={embeddedWorkshopEnabled}
                                            onChange={(e) => setEmbeddedWorkshopEnabled(e.currentTarget.checked)}
                                            onClick={(e) => e.stopPropagation()}
                                            style={{ marginRight: 12 }}
                                        />
                                    </Group>
                                </Accordion.Control>
                                <Accordion.Panel>
                                    {embeddedWorkshopEnabled && (
                                        <Stack gap="md" mt="xs">
                                            <Switch
                                                label={t('translation_page.embedded_workshop_follow_primary', { defaultValue: '直接套用主翻译 API 设置' })}
                                                checked={embeddedWorkshopFollowPrimary}
                                                onChange={(e) => setEmbeddedWorkshopFollowPrimary(e.currentTarget.checked)}
                                            />

                                            {!embeddedWorkshopFollowPrimary && (
                                                <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                                                    <Select
                                                        label={t('translation_page.embedded_workshop_provider', { defaultValue: '校对 Provider' })}
                                                        data={apiProviders}
                                                        value={embeddedWorkshopProvider}
                                                        onChange={setEmbeddedWorkshopProvider}
                                                    />
                                                    <Select
                                                        label={t('translation_page.embedded_workshop_model', { defaultValue: '校对 Model' })}
                                                        data={resolveProviderModels(embeddedWorkshopProvider)}
                                                        value={embeddedWorkshopModel}
                                                        onChange={setEmbeddedWorkshopModel}
                                                    />
                                                </SimpleGrid>
                                            )}

                                            {/* Renders PerformanceControlPanel for embedded workshop settings */}
                                            <PerformanceControlPanel
                                                batchSize={embeddedWorkshopBatchSize}
                                                onChangeBatchSize={setEmbeddedWorkshopBatchSize}
                                                concurrency={embeddedWorkshopConcurrency}
                                                onChangeConcurrency={setEmbeddedWorkshopConcurrency}
                                                rpm={embeddedWorkshopRpm}
                                                onChangeRpm={setEmbeddedWorkshopRpm}
                                                batchSizeOpts={['3', '5', '10', '15', '20'].map(value => ({ value, label: value }))}
                                                concurrencyOpts={['1', '2', '3', '5'].map(value => ({ value, label: value }))}
                                                rpmOpts={['5', '10', '20', '40', '60', '100'].map(value => ({ value, label: value }))}
                                            />
                                        </Stack>
                                    )}
                                </Accordion.Panel>
                            </Accordion.Item>
                        </Accordion>

                        <Group justify="space-between" mt="lg">
                            <Button variant="outline" onClick={onBack}>
                                {t('common.back')}
                            </Button>
                            <Button
                                id="incremental-scan-btn"
                                loading={loading}
                                disabled={selectedLangs.length === 0}
                                onClick={runPreScan}
                            >
                                {t('incremental_translation.run_pre_scan')}
                            </Button>
                        </Group>
                    </Stack>
                </Paper>
            )}
        </Stack>
    );
};

export default ConfigStep;
