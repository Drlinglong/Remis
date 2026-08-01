import React, { useCallback } from 'react';
import {
    Paper,
    SimpleGrid,
    Select,
    Title,
    Box,
    Text,
    Alert,
    Divider,
    Card,
    Button,
    Accordion,
    Badge,
    Group,
    Stack
} from '@mantine/core';
import {
    IconSettings,
    IconAlertCircle,
    IconPlayerPlay,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import PerformanceControlPanel from '../shared/PerformanceControlPanel';
import TelemetrySummary from './TelemetrySummary';
import { buildPreScanLanguageSummary } from './preScanSummary';
import styles from '../../pages/Translation.module.css';

export const PreScanResultsStep = ({
    scanResults,
    selectedProvider,
    handleProviderChange,
    selectedModel,
    setSelectedModel,
    models = [],
    batchSizeLimit,
    setBatchSizeLimit,
    concurrencyLimit,
    setConcurrencyLimit,
    rpmLimit,
    setRpmLimit,
    customSourcePath,
    selectedProject,
    selectedLangs = [],
    apiProviders = [],
    archiveInfo,
    startTranslation,
    onBack,
    loading,
    executing,
    currentTaskId,
    conflictingTaskId,
    onViewTask,
}) => {
    const { t } = useTranslation();
    const languageSummary = buildPreScanLanguageSummary({ scanResults, selectedLangs, archiveInfo });

    const formatRange = useCallback((range) => (
        range.uniform ? String(range.min) : `${range.min} - ${range.max}`
    ), []);

    const formatLanguageScope = useCallback(() => {
        const languages = languageSummary.languages.length > 0 ? languageSummary.languages : selectedLangs;
        if (languageSummary.languageCount <= 1) {
            return t('incremental_translation.language_scope_single', {
                language: languages[0] || '--',
                defaultValue: '{{language}}',
            });
        }

        const preview = languages.slice(0, 3).join(', ');
        return t('incremental_translation.language_scope_multi', {
            preview,
            count: languageSummary.languageCount,
            defaultValue: '{{preview}} and {{count}} languages',
        });
    }, [languageSummary.languageCount, languageSummary.languages, selectedLangs, t]);

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

    return (
        <Stack data-remis-surface="surface" mt="xl">
            {scanResults && (
                <Paper data-remis-surface="surface" id="incremental-prescan-summary" withBorder p="xl" radius="md" className={styles.glassCard}>
                    <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md" mb="lg">
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
                    </SimpleGrid>

                    <Card withBorder p="md" radius="md" mb="lg">
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

                    <Alert icon={<IconAlertCircle size={16} />} color="blue" radius="md" mb="lg">
                        <Text size="sm">
                            {t('incremental_translation.language_scope_summary', {
                                languages: formatLanguageScope(),
                                defaultValue: 'Running incremental update for {{languages}}. Per-language metrics describe one target language; aggregate metrics describe the whole run.',
                            })}
                        </Text>
                        <Text size="sm" mt={6}>
                            {t('incremental_translation.reusable_scope_note')}
                        </Text>
                    </Alert>

                    <Divider mb="lg" />

                    <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md" mb="xl">
                        <Card withBorder p="md" radius="md">
                            <Text size="xs" c="dimmed" mb={4}>{t('incremental_translation.per_language_total')}</Text>
                            <Title order={3}>{formatRange(languageSummary.perLanguageTotal)}</Title>
                        </Card>
                        <Card withBorder p="md" radius="md" style={{ borderLeft: '4px solid var(--mantine-color-green-6)' }}>
                            <Text size="xs" c="dimmed" mb={4}>{t('incremental_translation.per_language_reused')}</Text>
                            <Title order={3} c="green">{formatRange(languageSummary.perLanguageReusable)}</Title>
                        </Card>
                        <Card withBorder p="md" radius="md" style={{ borderLeft: '4px solid var(--mantine-color-orange-6)' }}>
                            <Text size="xs" c="dimmed" mb={4}>{t('incremental_translation.per_language_new')}</Text>
                            <Title order={3} c="orange">{formatRange(languageSummary.perLanguageDirty)}</Title>
                        </Card>
                    </SimpleGrid>

                    <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md" mb="xl">
                        <Card withBorder p="md" radius="md">
                            <Text size="xs" c="dimmed" mb={4}>{t('incremental_translation.aggregate_total')}</Text>
                            <Title order={3}>{languageSummary.aggregateTotal}</Title>
                        </Card>
                        <Card withBorder p="md" radius="md" style={{ borderLeft: '4px solid var(--mantine-color-green-6)' }}>
                            <Text size="xs" c="dimmed" mb={4}>{t('incremental_translation.aggregate_reused')}</Text>
                            <Title order={3} c="green">{languageSummary.aggregateReusable}</Title>
                        </Card>
                        <Card withBorder p="md" radius="md" style={{ borderLeft: '4px solid var(--mantine-color-orange-6)' }}>
                            <Text size="xs" c="dimmed" mb={4}>{t('incremental_translation.aggregate_new')}</Text>
                            <Title order={3} c="orange">{languageSummary.aggregateDirty}</Title>
                        </Card>
                    </SimpleGrid>

                    <Alert icon={<IconAlertCircle size={16} />} color="blue">
                        {t('incremental_translation.start_translation_confirm')}
                    </Alert>

                    {(conflictingTaskId || (executing && currentTaskId)) && (
                        <Alert
                            color="blue"
                            title={t('incremental_translation.conflicting_task_title')}
                            mt="md"
                        >
                            <Group justify="space-between" align="center" wrap="wrap">
                                <Text size="sm">
                                    {t('incremental_translation.conflicting_task_notice')}
                                </Text>
                                {onViewTask && (
                                    <Button size="xs" variant="light" onClick={onViewTask}>
                                        {t('task_center.view_task')}
                                    </Button>
                                )}
                            </Group>
                        </Alert>
                    )}

                    <Group justify="flex-end" mt="md">
                        <Button variant="light" onClick={onBack} disabled={loading || executing}>
                            {t('common.back')}
                        </Button>
                        <Button
                            id="incremental-start-run-btn"
                            size="lg"
                            leftSection={<IconPlayerPlay size={20} />}
                            onClick={startTranslation}
                            disabled={loading || executing || Boolean(conflictingTaskId)}
                        >
                            {t('incremental_translation.step_4_title')}
                        </Button>
                    </Group>

                    <TelemetrySummary telemetry={scanResults.telemetry} />

                    {renderFileDetails(scanResults.file_summaries)}
                </Paper>
            )}
        </Stack>
    );
};

export default PreScanResultsStep;
