import React, { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Alert,
    Badge,
    Button,
    Container,
    Group,
    Loader,
    Paper,
    Switch,
    Stack,
    Text,
    Title,
} from '@mantine/core';
import { IconArchive, IconInfoCircle, IconRefresh } from '@tabler/icons-react';

import {
    getArchiveCounts,
    getArchiveEntries,
    getTraceabilityRows,
    isReleaseStale,
} from './modArchiveModel';
import AnalysisPreviewPanel from './AnalysisPreviewPanel';
import ModArchiveOverrideEditor from './ModArchiveOverrideEditor';
import { ArchiveSummary, ReleaseMetadata } from './PublishedArchiveContent';
import ProjectGlossaryToolbar from './ProjectGlossaryToolbar';
import RemoveModArchiveControl from './RemoveModArchiveControl';
import ContextArchiveTreeReview from './archiveTreeV2/ContextArchiveTreeReview';
import ContextTreeV2ArchiveSummary from './archiveTreeV2/ContextTreeV2ArchiveSummary';
import { useContextTreeV2Archive } from './archiveTreeV2/useContextTreeV2Archive';
import { useArchiveProjectContext } from './useArchiveProjectContext';
import { useModArchiveDraft } from './useModArchiveDraft';
import { useModArchiveRelease } from './useModArchiveRelease';
import styles from './ModArchive.module.css';

const scopeValue = (metadata) => {
    const scope = metadata?.analysis_scope;
    if (typeof scope === 'string') return scope;
    return scope?.mode || scope?.scope || '';
};

const PublishedArchivePanel = ({
    selectedProject,
    onSelectedProjectChange,
    onOpenGlossary,
    status,
}) => {
    const { t } = useTranslation();
    const [publishedChildReleaseId, setPublishedChildReleaseId] = useState(null);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const releaseState = useModArchiveRelease(selectedProject);
    const treeV2State = useContextTreeV2Archive(selectedProject, 'published');
    const {
        phase,
        release,
        effective,
        error,
        traceability,
        traceabilityState,
        traceabilityError,
        refresh,
        loadTraceability,
    } = releaseState;
    const stale = isReleaseStale(release, status);
    const targetLanguage = release?.metadata?.analysis_config?.description_language;
    const projectContext = useArchiveProjectContext({
        selectedProject,
        onSelectedProjectChange,
        targetLanguage,
    });
    const entries = useMemo(
        () => getArchiveEntries(effective, projectContext.terminologyIndex),
        [effective, projectContext.terminologyIndex],
    );
    const counts = useMemo(() => getArchiveCounts(effective), [effective]);
    const rows = getTraceabilityRows(traceability);
    const treeData = effective?.context_tree_v2
        || effective?.context_tree
        || effective?.archive_tree
        || effective?.tree
        || release?.context_tree_v2
        || release?.context_tree
        || release?.tree
        || null;
    const projectToolbar = (
        <div className={styles.projectToolbar}>
            <ProjectGlossaryToolbar
                projects={projectContext.projects}
                selectedProject={selectedProject}
                onSelectedProjectChange={onSelectedProjectChange}
                projectGlossary={projectContext.projectGlossary}
                onOpenGlossary={onOpenGlossary ? () => onOpenGlossary({
                    glossaryId: projectContext.projectGlossary?.glossary_id,
                    gameId: projectContext.projectGlossary?.game_id || projectContext.currentProject?.game_id,
                }) : undefined}
            />
        </div>
    );
    const handlePublished = useCallback(async (nextRelease) => {
        setPublishedChildReleaseId(nextRelease?.release_id || null);
        await refresh();
    }, [refresh]);
    const draftState = useModArchiveDraft({
        selectedProject,
        baseReleaseId: release?.release_id,
        contextEntries: entries,
        onPublished: handlePublished,
    });

    if (!selectedProject) {
        return (
            <Container className={styles.page} size="xl" py="xl" data-remis-surface="canvas">
                {projectToolbar}
                <StateCard
                    icon={<IconArchive size={30} />}
                    title={t('mod_archive.release.no_project_title')}
                    description={t('mod_archive.release.no_project_desc')}
                    testId="mod-archive-release-empty"
                />
            </Container>
        );
    }

    if (treeV2State.phase === 'ready' && treeV2State.tree) {
        return (
            <Container className={styles.page} size="xl" py="xl" data-remis-surface="canvas">
                {projectToolbar}
                <ContextTreeV2ArchiveSummary tree={treeV2State.tree} mode="published" />
            </Container>
        );
    }

    if (phase === 'idle' || phase === 'loading') {
        return (
            <Container className={styles.page} size="xl" py="xl" data-remis-surface="canvas">
                {projectToolbar}
                <StateCard
                    icon={<Loader size="md" />}
                    title={t('mod_archive.release.loading_title')}
                    description={t('mod_archive.release.loading_desc')}
                    testId="mod-archive-release-loading"
                />
            </Container>
        );
    }

    if (phase === 'empty') {
        return (
            <AnalysisPreviewPanel
                selectedProject={selectedProject}
                projectToolbar={projectToolbar}
            />
        );
    }

    if (phase === 'error' && !release) {
        return (
            <Container className={styles.page} size="xl" py="xl" data-remis-surface="canvas">
                {projectToolbar}
                <StateCard
                    icon={<IconInfoCircle size={30} />}
                    title={t('mod_archive.release.error_title')}
                    description={error || t('mod_archive.release.error_desc')}
                    testId="mod-archive-release-error"
                    action={(
                        <Button className={styles.secondaryAction} leftSection={<IconRefresh size={16} />} onClick={refresh}>
                            {t('mod_archive.release.retry')}
                        </Button>
                    )}
                />
            </Container>
        );
    }

    const showPartialNotice = phase === 'partial' || Boolean(error);
    return (
        <Container
            className={styles.page}
            size="xl"
            py="xl"
            data-testid="mod-archive-release-panel"
            data-remis-surface="canvas"
        >
            {projectToolbar}
            <Group className={styles.header} wrap="wrap">
                <Badge className={styles.headerIcon} size="xl" radius="sm">
                    <IconArchive size={22} />
                </Badge>
                <Stack gap={2} style={{ flex: '1 1 20rem', minWidth: 0 }}>
                    <Title order={2}>{t('mod_archive.release.title')}</Title>
                    <Text className={styles.subtitle} size="sm">
                        {t('mod_archive.release.subtitle')}
                    </Text>
                </Stack>
                <RemoveModArchiveControl
                    projectId={selectedProject}
                    projectName={projectContext.currentProject?.name || selectedProject}
                    onRemoved={refresh}
                    t={t}
                />
                <Switch
                    checked={showAdvanced}
                    onChange={(event) => setShowAdvanced(event.currentTarget.checked)}
                    label={t('advanced_options')}
                    data-testid="mod-archive-advanced-toggle"
                />
            </Group>

            {stale && (
                <Alert className={styles.surface} mb="md" data-testid="mod-archive-release-stale" data-remis-surface="surface">
                    <Text fw={700}>{t('mod_archive.release.stale_title')}</Text>
                    <Text size="sm">{t('mod_archive.release.stale_desc')}</Text>
                </Alert>
            )}
            {showPartialNotice && (
                <Alert className={styles.surface} mb="md" data-testid="mod-archive-release-partial" data-remis-surface="surface">
                    <Text fw={700}>{t('mod_archive.release.partial_title')}</Text>
                    <Text size="sm">{error || t('mod_archive.release.partial_desc')}</Text>
                </Alert>
            )}

            <ReleaseMetadata
                release={release}
                selectedProject={selectedProject}
                scope={scopeValue(release.metadata)}
                draftState={draftState}
                refresh={refresh}
                showAdvanced={showAdvanced}
                t={t}
            />

            {publishedChildReleaseId === release.release_id && (
                <Alert className={styles.statusSurface} mt="md" data-tone="success" data-testid="mod-archive-published-notice">
                    <Text fw={700}>{t('mod_archive.release.draft.publish_success')}</Text>
                    <Text size="sm">{publishedChildReleaseId}</Text>
                </Alert>
            )}

            <ModArchiveOverrideEditor
                draftState={draftState}
                contextEntries={entries}
                baseReleaseId={release.release_id}
                t={t}
            />

            <ArchiveSummary
                entries={entries}
                counts={counts}
                rows={rows}
                traceabilityState={traceabilityState}
                traceabilityError={traceabilityError}
                loadTraceability={loadTraceability}
                showAdvanced={showAdvanced}
                t={t}
            />

            {showAdvanced && (
                <ContextArchiveTreeReview
                    projectId={selectedProject}
                    releaseId={release.release_id}
                    treeData={treeData}
                />
            )}
        </Container>
    );
};

const StateCard = ({ icon, title, description, action, testId }) => (
    <Paper className={`${styles.surface} ${styles.stateCard}`} p="xl" withBorder data-testid={testId} data-remis-surface="surface">
        <Stack align="center" gap="sm">
            {icon}
            <Title order={3}>{title}</Title>
            <Text className={styles.muted} ta="center" maw={560}>{description}</Text>
            {action}
        </Stack>
    </Paper>
);

export default PublishedArchivePanel;
