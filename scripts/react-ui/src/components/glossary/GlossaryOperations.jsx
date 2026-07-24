import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import {
    ActionIcon,
    Alert,
    Badge,
    Button,
    Checkbox,
    Divider,
    Group,
    Loader,
    Modal,
    Paper,
    ScrollArea,
    Select,
    Stack,
    Text,
    TextInput,
    Tooltip,
} from '@mantine/core';
import {
    IconAlertTriangle,
    IconHelpCircle,
    IconHistory,
    IconSparkles,
} from '@tabler/icons-react';

import PerformanceControlPanel from '../shared/PerformanceControlPanel';
import {
    buildProviderSelection,
    resolveProviderModels,
} from '../../hooks/incrementalTranslationProviders';
import { taskDetailRoute } from '../../utils/taskRoutes';

const taskHealthReport = (task) => {
    const metadata = task?.result?.metadata || {};
    return metadata.preview || metadata;
};

const GlossaryOperations = ({
    selectedIds,
    glossaries,
    targetLanguages = [],
    apiProviders = [],
    operation,
    isMutating,
    onPreviewMerge,
    onStartMerge,
    onStartHealthCheck,
    onLoadHealthHistory,
    toolbarMode = 'full',
    defaultIncludeAiAdvice = false,
}) => {
    const { t, i18n } = useTranslation();
    const navigate = useNavigate();
    const [mergeOpened, setMergeOpened] = useState(false);
    const [mergeTargetMode, setMergeTargetMode] = useState('new');
    const [mergeTargetName, setMergeTargetName] = useState('');
    const [mergeTargetId, setMergeTargetId] = useState(null);
    const [conflictStrategy, setConflictStrategy] = useState('skip_conflicts');
    const [mergePreview, setMergePreview] = useState(null);
    const [healthOpened, setHealthOpened] = useState(false);
    const [targetLang, setTargetLang] = useState(null);
    const [includeAiAdvice, setIncludeAiAdvice] = useState(false);
    const [confirmModelUsage, setConfirmModelUsage] = useState(false);
    const [provider, setProvider] = useState(null);
    const [model, setModel] = useState(null);
    const [concurrencyLimit, setConcurrencyLimit] = useState('1');
    const [healthTaskId, setHealthTaskId] = useState(null);
    const [healthPreview, setHealthPreview] = useState(null);
    const [historyOpened, setHistoryOpened] = useState(false);
    const [historyLoading, setHistoryLoading] = useState(false);
    const [historyError, setHistoryError] = useState('');
    const [healthHistory, setHealthHistory] = useState([]);

    const selectedGlossaries = useMemo(() => {
        const selected = new Set(selectedIds);
        return glossaries.filter((glossary) => selected.has(glossary.glossary_id));
    }, [glossaries, selectedIds]);

    const selectedGames = new Set(selectedGlossaries.map((item) => item.game_id));
    const existingTargets = glossaries
        .filter((item) => selectedGames.size === 1 && selectedGames.has(item.game_id))
        .map((item) => ({ value: String(item.glossary_id), label: item.name }));

    const modelOptions = resolveProviderModels(apiProviders, provider)
        .map((item) => ({ value: item, label: item }));

    const currentHealthTask = operation?.kind === 'health' && operation.taskId === healthTaskId
        ? operation
        : null;
    const currentTaskMetadata = currentHealthTask?.task?.result?.metadata;
    const healthReport = (
        currentTaskMetadata?.preview
        || (currentTaskMetadata?.glossary_ids ? currentTaskMetadata : null)
        || healthPreview
    );
    const healthAiPlan = (
        healthReport?.ai_review_plan
        || currentTaskMetadata?.ai_review_plan
        || currentHealthTask?.aiReviewPlan
    );

    const openMerge = () => {
        const defaultName = selectedGlossaries.length > 0
            ? `${selectedGlossaries[0].name} — Merged`
            : 'Merged glossary';
        setMergeTargetName(defaultName.slice(0, 200));
        setMergeTargetMode('new');
        setMergeTargetId(null);
        setConflictStrategy('skip_conflicts');
        setMergePreview(null);
        setMergeOpened(true);
    };

    const mergeOptions = () => ({
        target_mode: mergeTargetMode,
        target_glossary_id: mergeTargetMode === 'existing' && mergeTargetId
            ? Number(mergeTargetId)
            : null,
        target_name: mergeTargetMode === 'new' ? mergeTargetName.trim() : null,
        conflict_strategy: conflictStrategy,
    });

    const previewMerge = async () => {
        const preview = await onPreviewMerge(selectedIds, mergeOptions());
        if (preview) setMergePreview(preview);
    };

    const startMerge = async () => {
        const started = await onStartMerge(selectedIds, mergeOptions());
        if (started) {
            setMergeOpened(false);
            setMergePreview(null);
        }
    };

    const openHealth = () => {
        const localProvider = apiProviders.find((item) => (
            ['ollama', 'lm_studio', 'vllm', 'koboldcpp', 'oobabooga', 'text-generation-webui']
                .includes(item.value)
        ));
        const selection = buildProviderSelection({
            providers: apiProviders,
            providerValue: provider || localProvider?.value || apiProviders[0]?.value,
            preferredModel: model || '',
            preferredConcurrency: provider ? concurrencyLimit : null,
        });
        setTargetLang(targetLang || targetLanguages[0]?.code || null);
        setProvider(selection.selectedProvider || null);
        setModel(selection.selectedModel || null);
        setConcurrencyLimit(
            String(Math.min(6, Math.max(1, Number(selection.concurrencyLimit) || 1)))
        );
        setIncludeAiAdvice(defaultIncludeAiAdvice);
        setConfirmModelUsage(false);
        setHealthTaskId(null);
        setHealthPreview(null);
        setHealthOpened(true);
    };

    const startHealth = async () => {
        const started = await onStartHealthCheck(selectedIds, {
            target_lang: targetLang || null,
            include_ai_advice: includeAiAdvice,
            confirm_model_usage: includeAiAdvice && confirmModelUsage,
            api_provider: includeAiAdvice ? provider : null,
            model_name: includeAiAdvice ? model : null,
            concurrency_limit: includeAiAdvice ? Number(concurrencyLimit) : 1,
        });
        if (started) {
            setHealthTaskId(started.task_id);
            setHealthPreview(started.deterministic_preview ? {
                ...started.deterministic_preview,
                ai_review_plan: started.ai_review_plan,
            } : null);
        }
    };

    const openHealthHistory = async () => {
        if (selectedGlossaries.length !== 1 || !onLoadHealthHistory) return;
        setHistoryOpened(true);
        setHistoryLoading(true);
        setHistoryError('');
        try {
            setHealthHistory(
                await onLoadHealthHistory(selectedGlossaries[0].glossary_id)
            );
        } catch (error) {
            setHealthHistory([]);
            setHistoryError(
                error.response?.data?.detail
                || t('glossary_health_history_load_failed', 'Could not load health-check history.')
            );
        } finally {
            setHistoryLoading(false);
        }
    };

    const openTask = (taskId) => {
        setHealthOpened(false);
        setHistoryOpened(false);
        navigate(taskDetailRoute(taskId));
    };

    return (
        <>
            <Group gap="xs" wrap="wrap">
                {toolbarMode === 'full' && (
                    <Button
                        size="xs"
                        variant="light"
                        disabled={selectedIds.length < 2}
                        onClick={openMerge}
                    >
                        {t('glossary_merge_action', 'Merge selected')}
                    </Button>
                )}
                <Button
                    size={toolbarMode === 'health-only' ? 'sm' : 'xs'}
                    variant="light"
                    color="teal"
                    leftSection={toolbarMode === 'health-only'
                        ? <IconSparkles size={16} aria-hidden="true" />
                        : null}
                    disabled={selectedIds.length < 1}
                    onClick={openHealth}
                >
                    {toolbarMode === 'health-only'
                        ? t('glossary_ai_inspection_action', 'AI inspection')
                        : t('glossary_health_action', 'Check health')}
                </Button>
                {toolbarMode === 'full' && (
                    <Button
                        size="xs"
                        variant="subtle"
                        leftSection={<IconHistory size={15} aria-hidden="true" />}
                        disabled={selectedGlossaries.length !== 1}
                        onClick={openHealthHistory}
                    >
                        {t('glossary_health_history_action', 'Check history')}
                    </Button>
                )}
            </Group>

            <Modal
                opened={mergeOpened}
                onClose={() => !isMutating && setMergeOpened(false)}
                title={t('glossary_merge_title', 'Merge glossaries')}
                size="xl"
                centered
            >
                <Stack>
                    <Text size="sm" c="dimmed">
                        {t('glossary_merge_selected_summary', {
                            count: selectedIds.length,
                            defaultValue: 'Build a read-only preview for {{count}} selected glossaries before writing anything.',
                        })}
                    </Text>
                    <Select
                        label={t('glossary_merge_target_mode', 'Merge destination')}
                        value={mergeTargetMode}
                        allowDeselect={false}
                        data={[
                            { value: 'new', label: t('glossary_merge_new_target', 'Create a new glossary') },
                            { value: 'existing', label: t('glossary_merge_existing_target', 'Merge into an existing glossary') },
                        ]}
                        onChange={(value) => {
                            setMergeTargetMode(value || 'new');
                            setConflictStrategy(value === 'existing' ? 'keep_target' : 'skip_conflicts');
                            setMergePreview(null);
                        }}
                    />
                    {mergeTargetMode === 'new' ? (
                        <TextInput
                            label={t('glossary_merge_name', 'Merged glossary name')}
                            value={mergeTargetName}
                            maxLength={200}
                            required
                            onChange={(event) => {
                                setMergeTargetName(event.currentTarget.value);
                                setMergePreview(null);
                            }}
                        />
                    ) : (
                        <Select
                            label={t('glossary_merge_target', 'Target glossary')}
                            value={mergeTargetId}
                            data={existingTargets}
                            searchable
                            required
                            onChange={(value) => {
                                setMergeTargetId(value);
                                setMergePreview(null);
                            }}
                        />
                    )}
                    <Select
                        label={t('glossary_merge_conflict_strategy', 'Conflict strategy')}
                        value={conflictStrategy}
                        allowDeselect={false}
                        data={[
                            ...(mergeTargetMode === 'existing' ? [{
                                value: 'keep_target',
                                label: t('glossary_merge_keep_target', 'Keep target entries'),
                            }] : []),
                            { value: 'skip_conflicts', label: t('glossary_merge_skip_conflicts', 'Skip conflicting terms') },
                            { value: 'keep_first', label: t('glossary_merge_keep_first', 'Keep first selected glossary') },
                            { value: 'keep_last', label: t('glossary_merge_keep_last', 'Keep last selected glossary') },
                        ]}
                        onChange={(value) => {
                            setConflictStrategy(value || 'skip_conflicts');
                            setMergePreview(null);
                        }}
                    />

                    {mergePreview && (
                        <Paper withBorder p="md">
                            <Group gap="xs" mb="xs" wrap="wrap">
                                <Badge>{mergePreview.unique_term_count} {t('glossary_merge_unique', 'unique')}</Badge>
                                <Badge color="gray">{mergePreview.duplicate_term_count} {t('glossary_merge_duplicates', 'duplicates')}</Badge>
                                <Badge color={mergePreview.conflict_count ? 'orange' : 'teal'}>
                                    {mergePreview.conflict_count} {t('glossary_merge_conflicts', 'conflicts')}
                                </Badge>
                                <Badge color="blue">{mergePreview.planned_term_count} {t('glossary_merge_planned', 'planned terms')}</Badge>
                            </Group>
                            {mergePreview.conflicts.slice(0, 5).map((conflict) => (
                                <Text key={conflict.normalized_source} size="xs" c="dimmed">
                                    {conflict.source}: {conflict.options.map((item) => item.glossary_name).join(' / ')}
                                </Text>
                            ))}
                        </Paper>
                    )}

                    <Group justify="flex-end">
                        <Button variant="default" onClick={() => setMergeOpened(false)} disabled={isMutating}>
                            {t('cancel', 'Cancel')}
                        </Button>
                        <Button
                            variant={mergePreview ? 'default' : 'filled'}
                            onClick={previewMerge}
                            loading={isMutating}
                            disabled={
                                (mergeTargetMode === 'new' && !mergeTargetName.trim())
                                || (mergeTargetMode === 'existing' && !mergeTargetId)
                            }
                        >
                            {t('glossary_merge_preview', 'Preview merge')}
                        </Button>
                        {mergePreview && (
                            <Button onClick={startMerge} loading={isMutating}>
                                {t('glossary_merge_start', 'Start merge task')}
                            </Button>
                        )}
                    </Group>
                </Stack>
            </Modal>

            <Modal
                opened={healthOpened}
                onClose={() => !isMutating && setHealthOpened(false)}
                title={t('glossary_health_title', 'Glossary health check')}
                size="xl"
                centered
                scrollAreaComponent={ScrollArea.Autosize}
            >
                <Stack>
                    <Stack gap={4}>
                        <Group gap={4}>
                            <Text fw={700}>
                                {t('glossary_health_how_title', 'How the check works')}
                            </Text>
                            <Tooltip
                                multiline
                                w={460}
                                withArrow
                                label={(
                                    <Stack gap="xs">
                                        <Text size="sm">
                                            {t(
                                                'glossary_health_how_scope',
                                                '1. Remis reads every entry in the selected glossaries. Choosing a language limits translation checks to that language.'
                                            )}
                                        </Text>
                                        <Text size="sm">
                                            {t(
                                                'glossary_health_how_rules',
                                                '2. Deterministic rules find empty source text, missing translations, edge whitespace, placeholder mismatches, equivalent duplicates, and conflicting entries for the same source term.'
                                            )}
                                        </Text>
                                        <Text size="sm">
                                            {t(
                                                'glossary_health_how_score',
                                                '3. The score starts at 100. Each error removes 8 points, warning 3, and informational duplicate 1, capped at ten findings per rule.'
                                            )}
                                        </Text>
                                        <Text size="sm">
                                            {t(
                                                'glossary_health_how_ai',
                                                '4. Optional AI review receives only the deterministic evidence and returns bounded suggestions. It cannot edit or silently repair the glossary.'
                                            )}
                                        </Text>
                                    </Stack>
                                )}
                            >
                                <ActionIcon
                                    variant="subtle"
                                    color="gray"
                                    size="sm"
                                    aria-label={t('glossary_health_how_title', 'How the check works')}
                                >
                                    <IconHelpCircle size={15} aria-hidden="true" />
                                </ActionIcon>
                            </Tooltip>
                        </Group>
                        <Text size="sm" c="dimmed">
                            {t(
                                'glossary_health_script_summary',
                                'Uses mechanical script checks for incomplete, duplicate, and other basic entry problems. No API fees.'
                            )}
                        </Text>
                    </Stack>
                    <Select
                        label={t('glossary_health_target_lang', 'Translation language to verify')}
                        value={targetLang}
                        data={targetLanguages.map((language) => ({
                            value: language.code,
                            label: language.name_local || language.code,
                        }))}
                        clearable
                        onChange={setTargetLang}
                    />
                    <Checkbox
                        checked={includeAiAdvice}
                        onChange={(event) => {
                            setIncludeAiAdvice(event.currentTarget.checked);
                            setConfirmModelUsage(false);
                        }}
                        label={t('glossary_health_include_ai', 'Add advisory AI review after deterministic checks')}
                        description={t(
                            'glossary_health_include_ai_desc',
                            'Calls an LLM to suggest improvements for entries with detected problems and may incur provider fees.'
                        )}
                    />
                    {includeAiAdvice && (
                        <>
                            <Group grow align="flex-start">
                                <Select
                                    label={t('glossary_health_provider', 'Provider')}
                                    value={provider}
                                    data={apiProviders}
                                    onChange={(value) => {
                                        const selection = buildProviderSelection({
                                            providers: apiProviders,
                                            providerValue: value,
                                        });
                                        setProvider(selection.selectedProvider || null);
                                        setModel(selection.selectedModel || null);
                                        setConcurrencyLimit(
                                            String(Math.min(
                                                6,
                                                Math.max(1, Number(selection.concurrencyLimit) || 1)
                                            ))
                                        );
                                    }}
                                    required
                                />
                                <Select
                                    label={t('glossary_health_model', 'Model')}
                                    value={model}
                                    data={modelOptions}
                                    searchable
                                    onChange={setModel}
                                    required
                                />
                            </Group>
                            <PerformanceControlPanel
                                concurrency={concurrencyLimit}
                                onChangeConcurrency={setConcurrencyLimit}
                                showBatchSize={false}
                                showConcurrency
                                showRpm={false}
                                concurrencyOpts={['1', '2', '3', '4', '6'].map((value) => ({
                                    value,
                                    label: value,
                                }))}
                            />
                            <Checkbox
                                checked={confirmModelUsage}
                                onChange={(event) => setConfirmModelUsage(event.currentTarget.checked)}
                                label={t(
                                    'glossary_health_confirm_model',
                                    'I approve this model request. It may use a paid provider and will return suggestions only.'
                                )}
                            />
                        </>
                    )}

                    {healthReport && Number.isFinite(Number(healthReport.score)) && (
                        <>
                            <Divider />
                            <Group gap="xs">
                                <Badge size="lg" color={healthReport.score >= 80 ? 'teal' : healthReport.score >= 60 ? 'orange' : 'red'}>
                                    {t('glossary_health_score', 'Score')} {healthReport.score}/100
                                </Badge>
                                <Badge variant="light">
                                    {healthReport.issue_count} {t('glossary_health_issues', 'issues')}
                                </Badge>
                                {currentHealthTask && (
                                    <Badge variant="outline">
                                        {t(`task_center.status.${currentHealthTask.status}`, {
                                            defaultValue: currentHealthTask.status,
                                        })}
                                    </Badge>
                                )}
                            </Group>
                            {healthAiPlan && (
                                <Text size="sm" c="dimmed">
                                    {t('glossary_health_ai_plan', {
                                        count: healthAiPlan.case_count,
                                        batches: healthAiPlan.batch_count,
                                        defaultValue: `${healthAiPlan.case_count} repair cases in ${healthAiPlan.batch_count} model batches.`,
                                    })}
                                </Text>
                            )}
                            <Stack gap="xs">
                                {(healthReport.issues || []).map((issue) => (
                                    <Paper key={issue.code} withBorder p="sm">
                                        <Group justify="space-between" wrap="nowrap">
                                            <Text size="sm" fw={700}>
                                                {t(`glossary_health_issue_${issue.code}`, {
                                                    defaultValue: issue.message || issue.code,
                                                })}
                                            </Text>
                                            <Badge color={issue.severity === 'error' ? 'red' : issue.severity === 'warning' ? 'orange' : 'blue'}>
                                                {issue.count}
                                            </Badge>
                                        </Group>
                                    </Paper>
                                ))}
                            </Stack>
                            {(healthReport.ai_advice || []).length > 0 && (
                                <Stack gap="xs">
                                    <Text fw={700}>{t('glossary_health_ai_advice', 'AI advice')}</Text>
                                    {healthReport.ai_advice.map((advice) => (
                                        <Paper key={advice.case_id || advice.issue_code} withBorder p="sm">
                                            {advice.entry_id && (
                                                <Text size="xs" c="dimmed">{advice.entry_id}</Text>
                                            )}
                                            {advice.suggested_translation && (
                                                <Text size="sm" fw={700}>{advice.suggested_translation}</Text>
                                            )}
                                            <Text size="sm" fw={700}>{advice.recommendation}</Text>
                                            <Text size="xs" c="dimmed">{advice.rationale}</Text>
                                        </Paper>
                                    ))}
                                </Stack>
                            )}
                        </>
                    )}

                    <Group justify="space-between">
                        <Text size="xs" c="dimmed">
                            {healthTaskId ? `Task ${healthTaskId}` : t('glossary_health_no_task', 'No task started yet.')}
                        </Text>
                        <Group>
                            <Button variant="default" onClick={() => setHealthOpened(false)} disabled={isMutating}>
                                {t('button_close', 'Close')}
                            </Button>
                            {healthTaskId ? (
                                <Button color="teal" onClick={() => openTask(healthTaskId)}>
                                    {t('glossary_health_view_task', 'View task details')}
                                </Button>
                            ) : (
                                <Button
                                    color="teal"
                                    onClick={startHealth}
                                    loading={isMutating}
                                    disabled={includeAiAdvice && (
                                        !targetLang
                                        || !provider
                                        || !model
                                        || !confirmModelUsage
                                    )}
                                >
                                    {t('glossary_health_start', 'Start health task')}
                                </Button>
                            )}
                        </Group>
                    </Group>
                </Stack>
            </Modal>

            <Modal
                opened={historyOpened}
                onClose={() => setHistoryOpened(false)}
                title={t('glossary_health_history_title', {
                    name: selectedGlossaries[0]?.name || '',
                    defaultValue: 'Health-check history — {{name}}',
                })}
                size="lg"
                centered
                scrollAreaComponent={ScrollArea.Autosize}
            >
                {historyLoading ? (
                    <Group justify="center" py="xl">
                        <Loader />
                    </Group>
                ) : historyError ? (
                    <Alert color="red" icon={<IconAlertTriangle size={16} />}>
                        {historyError}
                    </Alert>
                ) : healthHistory.length === 0 ? (
                    <Stack align="flex-start" gap="sm">
                        <Text c="dimmed">
                            {t('glossary_health_history_empty', 'No health checks have been run for this glossary.')}
                        </Text>
                        <Text size="sm" c="dimmed">
                            {t(
                                'glossary_health_history_empty_hint',
                                'The basic check uses local rules and has no API cost. AI advice is optional.'
                            )}
                        </Text>
                        <Button
                            color="teal"
                            onClick={() => {
                                setHistoryOpened(false);
                                openHealth();
                            }}
                        >
                            {t(
                                'glossary_health_history_start_first',
                                'Start first health check'
                            )}
                        </Button>
                    </Stack>
                ) : (
                    <Stack gap="sm">
                        {healthHistory.map((task) => {
                            const report = taskHealthReport(task);
                            const hasScore = Number.isFinite(Number(report.score));
                            const aiRequested = (
                                task.result?.types?.includes('advisory_review')
                                || task.result?.metadata?.ai_advice_requested
                                || report.ai_review_status === 'completed'
                                || report.ai_review_status === 'failed'
                            );
                            return (
                                <Paper key={task.task_id} withBorder p="md">
                                    <Group justify="space-between" align="flex-start" wrap="nowrap">
                                        <Stack gap={5}>
                                            <Group gap="xs">
                                                <Text fw={700}>
                                                    {t('glossary_health_task_title', {
                                                        count: report.glossary_count || 1,
                                                        defaultValue: 'Glossary health check',
                                                    })}
                                                </Text>
                                                <Badge variant="light">
                                                    {t(`task_center.status.${task.status}`, {
                                                        defaultValue: task.status,
                                                    })}
                                                </Badge>
                                                {aiRequested && (
                                                    <Badge color="violet" variant="outline">
                                                        {t('glossary_health_ai_advice', 'AI advice')}
                                                    </Badge>
                                                )}
                                            </Group>
                                            <Text size="xs" c="dimmed">
                                                {task.created_at
                                                    ? new Intl.DateTimeFormat(i18n.language, {
                                                        dateStyle: 'medium',
                                                        timeStyle: 'short',
                                                    }).format(new Date(task.created_at))
                                                    : task.task_id}
                                            </Text>
                                            {hasScore && (
                                                <Group gap="xs">
                                                    <Badge color={report.score >= 80 ? 'teal' : report.score >= 60 ? 'orange' : 'red'}>
                                                        {t('glossary_health_score', 'Score')} {report.score}/100
                                                    </Badge>
                                                    <Badge variant="light">
                                                        {report.issue_count || 0} {t('glossary_health_issues', 'issues')}
                                                    </Badge>
                                                </Group>
                                            )}
                                        </Stack>
                                        <Button
                                            size="xs"
                                            variant="light"
                                            onClick={() => openTask(task.task_id)}
                                        >
                                            {t('glossary_health_view_task', 'View task details')}
                                        </Button>
                                    </Group>
                                </Paper>
                            );
                        })}
                    </Stack>
                )}
            </Modal>
        </>
    );
};

export default GlossaryOperations;
