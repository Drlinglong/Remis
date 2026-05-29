import React, { useCallback, useEffect } from 'react';
import {
    Stack,
    Paper,
    Title,
    Progress,
    Group,
    Box,
    Text,
    Alert,
    SimpleGrid,
    Card,
    Badge,
    Accordion,
    Button
} from '@mantine/core';
import {
    IconAlertCircle,
    IconSettings,
    IconCheck,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import styles from '../../pages/Translation.module.css';

export const ExecutionStep = ({
    progress,
    executing,
    progressInfo,
    logs,
    finalSummary,
    logViewportRef,
    logScrollRef,
    openOutputFolder,
    handleFinish,
    completionSource,
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

    const getValidationIssueCount = useCallback((summary) => {
        if (!summary || !Array.isArray(summary.workshop_issue_exports)) return 0;
        return summary.workshop_issue_exports.reduce((total, item) => total + Number(item?.issue_count || 0), 0);
    }, []);

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

    useEffect(() => {
        if (logViewportRef.current) {
            logViewportRef.current.scrollTo({ top: logViewportRef.current.scrollHeight, behavior: 'smooth' });
        }
    }, [logs, logViewportRef]);

    return (
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
                        <Text size="xs" c="dimmed">
                            {getStageDescription(progressInfo) || (executing ? t('incremental_translation.status_processing') : t('incremental_translation.status_idle'))}
                        </Text>
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
                                        source: completionSource || 'polling',
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
    );
};

export default ExecutionStep;
