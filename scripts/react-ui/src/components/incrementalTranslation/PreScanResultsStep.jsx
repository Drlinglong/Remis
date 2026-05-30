import React, { useCallback, useMemo } from 'react';
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
    ThemeIcon,
    Tooltip,
    Group,
    Stack
} from '@mantine/core';
import {
    IconChartBar,
    IconSettings,
    IconAlertCircle,
    IconPlayerPlay,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import PerformanceControlPanel from '../shared/PerformanceControlPanel';
import styles from '../../pages/Translation.module.css';

export const PreScanResultsStep = ({
    scanResults,
    selectedProvider,
    handleProviderChange,
    selectedModel,
    setSelectedModel,
    models,
    batchSizeLimit,
    setBatchSizeLimit,
    concurrencyLimit,
    setConcurrencyLimit,
    rpmLimit,
    setRpmLimit,
    customSourcePath,
    selectedProject,
    selectedLangs,
    apiProviders,
    archiveInfo,
    startTranslation,
    onBack,
    loading,
    executing,
}) => {
    const { t } = useTranslation();

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
        <Stack mt="xl">
            {scanResults && (
                <Paper id="incremental-prescan-summary" withBorder p="xl" radius="md" className={styles.glassCard}>
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
                        <Button variant="light" onClick={onBack} disabled={loading || executing}>
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
    );
};

export default PreScanResultsStep;
