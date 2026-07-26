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
    Button
} from '@mantine/core';
import {
    IconAlertCircle,
    IconSettings,
    IconCheck,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import styles from '../../pages/Translation.module.css';
import BusyHeartbeat from '../shared/BusyHeartbeat';
import TelemetrySummary from './TelemetrySummary';

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
    onViewTask,
    onStartProofreading,
}) => {
    const { t } = useTranslation();

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
    const stageTitle = getStageTitle(progressInfo, false);
    const stageDescription = getStageDescription(progressInfo) || (executing ? t('incremental_translation.status_processing') : t('incremental_translation.status_idle'));

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

                {executing && (
                    <>
                        <BusyHeartbeat
                            active
                            compact
                            title={stageTitle}
                            description={stageDescription}
                            color="blue"
                        />
                        <Alert color="blue" mt="md">
                            <Stack gap={6}>
                                <Text size="sm">
                                    {t('incremental_translation.background_task_notice')}
                                </Text>
                                {onViewTask && (
                                    <Group>
                                        <Button size="xs" variant="light" onClick={onViewTask}>
                                            {t('task_center.view_task')}
                                        </Button>
                                    </Group>
                                )}
                            </Stack>
                        </Alert>
                    </>
                )}

                <Group justify="space-between" mt={executing ? 'md' : 0} mb="xl">
                    <Box>
                        <Text size="sm" fw={600}>{stageTitle}</Text>
                        <Text size="xs" c="dimmed">
                            {stageDescription}
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
                        <TelemetrySummary telemetry={finalSummary.telemetry} />
                        <Group>
                            {onViewTask && (
                                <Button size="lg" variant="default" onClick={onViewTask}>
                                    {t('task_center.view_task')}
                                </Button>
                            )}
                            {onStartProofreading && (
                                <Button size="lg" variant="light" color="teal" onClick={onStartProofreading}>
                                    {t('project_management.primary_continue_proofreading')}
                                </Button>
                            )}
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
