import React from 'react';
import { useTranslation } from 'react-i18next';
import {
    Alert,
    Badge,
    Box,
    Button,
    Checkbox,
    Container,
    Grid,
    Group,
    Paper,
    Progress,
    Radio,
    Select,
    Stack,
    Text,
    TextInput,
    Title,
} from '@mantine/core';
import {
    IconArchive,
    IconFileText,
    IconInfoCircle,
    IconRadar2,
} from '@tabler/icons-react';

import {
    ANALYSIS_CONCURRENCY_OPTIONS,
    ANALYSIS_SCOPES,
    getStatusTone,
} from './modArchiveModel';
import { TARGET_LANGUAGE_OPTIONS } from './useModArchiveAnalysis';
import styles from './ModArchive.module.css';

const translateStatus = (t, category, code) => {
    const key = `mod_archive.status.${category}.${code}`;
    const translated = t(key);
    return translated === key ? code : translated;
};

const getSetupCopy = (allowArchiveAnalysis) => allowArchiveAnalysis
    ? {
        ariaLabel: 'mod_archive.title',
        title: 'mod_archive.analysis.title',
        subtitle: 'mod_archive.analysis.subtitle',
        setupTitle: 'mod_archive.analysis.setup_title',
        setupDescription: 'mod_archive.analysis.setup_desc',
    }
    : {
        ariaLabel: 'neologism_review.title',
        title: 'neologism_review.mining.setup_title',
        subtitle: 'neologism_review.mining.setup_desc',
        setupTitle: 'neologism_review.mining.setup_title',
        setupDescription: 'neologism_review.mining.setup_desc',
    };

const ModArchiveAnalysisSetup = ({ allowArchiveAnalysis = true, controller }) => {
    const { t } = useTranslation();
    const {
        projects,
        files,
        selectedFiles,
        setSelectedFiles,
        providers,
        apiProvider,
        setApiProvider,
        modelName,
        setModelName,
        targetLang,
        setTargetLang,
        descriptionLanguage,
        setDescriptionLanguage,
        analysisScope,
        setAnalysisScope,
        upstreamVersion,
        setUpstreamVersion,
        concurrencyLimit,
        setConcurrencyLimit,
        scanning,
        status,
        loadError,
        workflowError,
        currentProject,
        availableTargetLanguages,
        startAnalysis,
        onSelectedProjectChange,
    } = controller;

    const isActive = ['starting', 'running', 'queued'].includes(status?.status);
    const progressCurrent = status?.totalBatches || status?.currentBatch
        ? status.currentBatch
        : status?.processedFiles;
    const progressTotal = status?.totalBatches || status?.currentBatch
        ? status.totalBatches
        : status?.totalFiles;
    const progressValue = Number.isFinite(status?.overallPercent)
        ? Math.min(100, Math.max(0, status.overallPercent))
        : 0;
    const provider = providers.find((item) => item.value === apiProvider);
    const copy = getSetupCopy(allowArchiveAnalysis);

    return (
        <Container
            className={styles.page}
            size="xl"
            py="xl"
            data-testid="mod-archive-analysis"
            data-remis-surface="canvas"
        >
            <Group className={styles.header} wrap="nowrap">
                <Badge
                    className={styles.headerIcon}
                    size="xl"
                    radius="sm"
                    aria-label={t(copy.ariaLabel)}
                >
                    {allowArchiveAnalysis ? <IconArchive size={22} /> : <IconRadar2 size={22} />}
                </Badge>
                <Stack gap={2} style={{ minWidth: 0 }}>
                    <Title order={2}>
                        {t(copy.title)}
                    </Title>
                    <Text className={styles.subtitle} size="sm">
                        {t(copy.subtitle)}
                    </Text>
                </Stack>
            </Group>

            {(loadError || workflowError) && (
                <Alert
                    className={styles.surface}
                    icon={<IconInfoCircle size={18} />}
                    mb="md"
                    data-testid="mod-archive-analysis-error"
                    data-remis-surface="surface"
                >
                    {workflowError || loadError}
                </Alert>
            )}

            <div className={styles.layout}>
                <Paper className={styles.surface} p="lg" withBorder data-remis-surface="surface">
                    <Stack gap="md">
                        <div>
                            <Title order={3}>
                                {t(copy.setupTitle)}
                            </Title>
                            <Text className={styles.muted} size="sm" mt={4}>
                                {t(copy.setupDescription)}
                            </Text>
                        </div>

                        <Select
                            label={t('neologism_review.mining.select_project')}
                            placeholder={t('neologism_review.mining.select_project_placeholder')}
                            data={projects}
                            value={controller.selectedProject}
                            onChange={onSelectedProjectChange}
                            searchable
                        />

                        {allowArchiveAnalysis && <Radio.Group
                            label={t('mod_archive.analysis.scope_label')}
                            value={analysisScope}
                            onChange={setAnalysisScope}
                            name="mod-archive-analysis-scope"
                            data-testid="mod-archive-scope"
                        >
                            <Stack className={styles.scopeGroup} mt="xs">
                                <Box
                                    component="label"
                                    className={styles.scopeOption}
                                    data-selected={analysisScope === ANALYSIS_SCOPES.TERMS_ONLY}
                                    data-testid="mod-archive-scope-terms-only"
                                >
                                    <Radio
                                        value={ANALYSIS_SCOPES.TERMS_ONLY}
                                        label={t('mod_archive.analysis.scope_terms_only')}
                                    />
                                    <Text className={styles.scopeDescription} size="sm">
                                        {t('mod_archive.analysis.scope_terms_only_desc')}
                                    </Text>
                                </Box>
                                <Box
                                    component="label"
                                    className={styles.scopeOption}
                                    data-selected={analysisScope === ANALYSIS_SCOPES.NARRATIVE_CONTEXT}
                                    data-testid="mod-archive-scope-narrative-context"
                                >
                                    <Radio
                                        value={ANALYSIS_SCOPES.NARRATIVE_CONTEXT}
                                        label={t('mod_archive.analysis.scope_full_archive')}
                                    />
                                    <Text className={styles.scopeDescription} size="sm">
                                        {t('mod_archive.analysis.scope_full_archive_desc')}
                                    </Text>
                                </Box>
                            </Stack>
                        </Radio.Group>}

                        {allowArchiveAnalysis && <Text className={styles.muted} size="xs">
                            {t('mod_archive.analysis.scope_switch_note')}
                        </Text>}

                        {allowArchiveAnalysis && <TextInput
                            label={t('mod_archive.analysis.upstream_version')}
                            placeholder={t('mod_archive.analysis.upstream_version_placeholder')}
                            value={upstreamVersion}
                            onChange={(event) => setUpstreamVersion(event.currentTarget.value)}
                        />}

                        <Select
                            label={t('neologism_review.mining.target_language')}
                            description={t('neologism_review.mining.target_language_desc')}
                            data={availableTargetLanguages}
                            value={targetLang}
                            onChange={setTargetLang}
                        />

                        <Select
                            label={t('mod_archive.analysis.description_language')}
                            description={t('mod_archive.analysis.description_language_desc')}
                            data={TARGET_LANGUAGE_OPTIONS}
                            value={descriptionLanguage}
                            onChange={setDescriptionLanguage}
                        />

                        <Select
                            label={t('mod_archive.analysis.concurrency_label')}
                            description={t('mod_archive.analysis.concurrency_desc')}
                            data={ANALYSIS_CONCURRENCY_OPTIONS.map((option) => ({
                                value: option.value,
                                label: option.labelKey ? t(option.labelKey) : option.label,
                            }))}
                            value={concurrencyLimit}
                            onChange={(value) => setConcurrencyLimit(value || 'auto')}
                            data-testid="mod-archive-concurrency"
                        />

                        <Select
                            label={t('neologism_review.mining.select_provider')}
                            data={providers}
                            value={apiProvider}
                            onChange={setApiProvider}
                        />

                        {provider?.available_models?.length > 0 && (
                            <Select
                                label={t('neologism_review.mining.model')}
                                data={provider.available_models}
                                value={modelName}
                                onChange={setModelName}
                                searchable
                            />
                        )}

                        <Button
                            className={styles.primaryAction}
                            size="lg"
                            leftSection={<IconRadar2 size={18} />}
                            onClick={startAnalysis}
                            loading={scanning}
                            data-remis-action="primary"
                            disabled={
                                !controller.selectedProject
                                || !targetLang
                                || !apiProvider
                                || normalizeSourceLanguage(targetLang, currentProject?.sourceLanguage)
                                || isActive
                            }
                            data-testid="mod-archive-start-analysis"
                        >
                            {t('mod_archive.analysis.start_analysis')}
                        </Button>
                        <Text className={styles.muted} size="xs">
                            {t('mod_archive.analysis.cost_notice')}
                        </Text>

                        {status && status.status !== 'idle' && (
                            <Paper
                                className={styles.statusSurface}
                                p="md"
                                withBorder
                                data-tone={getStatusTone(status.status)}
                                data-testid="mod-archive-analysis-status"
                                data-remis-surface="surface"
                            >
                                <Stack gap="sm">
                                    <Group justify="space-between" align="flex-start">
                                        <div>
                                            <Text fw={700}>
                                                {translateStatus(t, 'stage', status.stageCode)}
                                            </Text>
                                            <Text className={styles.muted} size="sm">
                                                {translateStatus(t, 'result', status.resultCode)}
                                            </Text>
                                        </div>
                                        <Badge variant="outline" data-testid="mod-archive-batch-progress">
                                            {progressCurrent || 0} / {progressTotal || 0}
                                        </Badge>
                                    </Group>
                                    <Progress value={progressValue} size="sm" />
                                    <div className={styles.statusGrid}>
                                        <div className={styles.statusCell}>
                                            <Text className={styles.statusLabel}>
                                                {t('mod_archive.status.next_step_label')}
                                            </Text>
                                            <Text size="sm">
                                                {translateStatus(t, 'next_step', status.nextStepCode)}
                                            </Text>
                                        </div>
                                        {status.taskId && (
                                            <div className={styles.statusCell}>
                                                <Text className={styles.statusLabel}>
                                                    {t('mod_archive.status.task_id')}
                                                </Text>
                                                <Text className={styles.technical} size="sm" title={status.taskId}>
                                                    {status.taskId}
                                                </Text>
                                            </div>
                                        )}
                                    </div>
                                    {status.error && (
                                        <Text c="red" size="sm">{status.error}</Text>
                                    )}
                                    <details>
                                        <summary>{t('mod_archive.status.diagnostics')}</summary>
                                        <Stack gap={4} mt="xs">
                                            <Text className={styles.technical} size="xs">
                                                {t('mod_archive.status.analysis_scope')}: {status.analysisScope}
                                            </Text>
                                            {status.sourceSnapshotHash && (
                                                <Text className={styles.technical} size="xs">
                                                    {t('mod_archive.status.source_snapshot')}: {status.sourceSnapshotHash}
                                                </Text>
                                            )}
                                            {status.contextReleaseId && (
                                                <Text className={styles.technical} size="xs">
                                                    {t('mod_archive.status.context_release')}: {status.contextReleaseId}
                                                </Text>
                                            )}
                                            {(status.provider || status.model) && (
                                                <Text className={styles.technical} size="xs">
                                                    {t('neologism_review.mining.select_provider')}: {status.provider || '—'}
                                                    {' · '}
                                                    {t('neologism_review.mining.model')}: {status.model || '—'}
                                                </Text>
                                            )}
                                            {(status.targetLang || status.descriptionLanguage) && (
                                                <Text className={styles.technical} size="xs">
                                                    {t('neologism_review.mining.target_language')}: {status.targetLang || '—'}
                                                    {' · '}
                                                    {t('mod_archive.analysis.description_language')}: {status.descriptionLanguage || '—'}
                                                </Text>
                                            )}
                                            {status.effectiveConcurrency && (
                                                <Text className={styles.technical} size="xs">
                                                    {t('mod_archive.analysis.concurrency_label')}: {status.effectiveConcurrency}
                                                </Text>
                                            )}
                                        </Stack>
                                    </details>
                                </Stack>
                            </Paper>
                        )}
                    </Stack>
                </Paper>

                <Paper className={styles.paper} p="lg" withBorder data-remis-surface="paper">
                    <Stack gap="xs">
                        <Title order={3}>{t('neologism_review.mining.select_files')}</Title>
                        <Text size="sm" c="dimmed">
                            {t('neologism_review.mining.select_files_desc')}
                        </Text>
                        <div className={styles.fileList}>
                            {files.filter(getFilePath).length > 0 ? (
                                <Checkbox.Group value={selectedFiles} onChange={setSelectedFiles}>
                                    <Stack gap="xs">
                                        {files.filter(getFilePath).map((file) => {
                                            const filePath = getFilePath(file);
                                            return (
                                                <Checkbox
                                                    key={filePath}
                                                    value={filePath}
                                                    label={(
                                                        <Group gap="xs" wrap="nowrap" align="flex-start">
                                                            <IconFileText size={15} />
                                                            <Text className={styles.fileLabel} size="sm">
                                                                {getFileLabel(file)}
                                                            </Text>
                                                        </Group>
                                                    )}
                                                />
                                            );
                                        })}
                                    </Stack>
                                </Checkbox.Group>
                            ) : (
                                <Text c="dimmed" fs="italic">
                                    {t('neologism_review.mining.no_files')}
                                </Text>
                            )}
                        </div>
                    </Stack>
                </Paper>
            </div>
        </Container>
    );
};

const getFilePath = (file) => file.file_path || file.path || '';
const getFileLabel = (file) => file.relative_path || file.rel_path || getFilePath(file);
const normalizeSourceLanguage = (target, source) => (
    source && target?.toLowerCase() === source.toLowerCase()
);

export default ModArchiveAnalysisSetup;
