import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Button,
    Container,
    Loader,
    Paper,
    Stack,
    Text,
    Title,
} from '@mantine/core';
import { IconArchive, IconInfoCircle, IconRefresh } from '@tabler/icons-react';

import AnalysisPreviewPanel from './AnalysisPreviewPanel';
import ContextTreeV2ArchiveSummary from './archiveTreeV2/ContextTreeV2ArchiveSummary';
import PublishedArchiveToolbar from './PublishedArchiveToolbar';
import {
    PUBLISHED_ARCHIVE_DEMO_PROJECT_ID,
    publishedArchiveDemoProject,
    publishedArchiveDemoRelease,
    publishedArchiveDemoTree,
} from './archiveTreeV2/publishedArchiveDemoFixture';
import { useContextTreeV2Archive } from './archiveTreeV2/useContextTreeV2Archive';
import { useArchiveProjectContext } from './useArchiveProjectContext';
import { useModArchiveRelease } from './useModArchiveRelease';
import styles from './ModArchive.module.css';

const PublishedArchivePanel = ({
    selectedProject,
    onSelectedProjectChange,
}) => {
    const { t } = useTranslation();
    const isDemoProject = selectedProject === PUBLISHED_ARCHIVE_DEMO_PROJECT_ID;
    const archiveProjectId = isDemoProject ? null : selectedProject;
    const [selectedReleaseId, setSelectedReleaseId] = useState(null);
    const [releaseVersions, setReleaseVersions] = useState([]);
    const releaseState = useModArchiveRelease(archiveProjectId, isDemoProject ? null : selectedReleaseId);
    const treeV2State = useContextTreeV2Archive(archiveProjectId, 'published', isDemoProject ? null : selectedReleaseId);
    const {
        release,
        error,
        refresh,
    } = releaseState;
    const displayRelease = isDemoProject ? publishedArchiveDemoRelease : release;
    const availableVersions = displayRelease?.versions;
    const currentReleaseId = displayRelease?.release_id;
    useEffect(() => {
        setSelectedReleaseId(null);
        setReleaseVersions([]);
    }, [selectedProject]);
    useEffect(() => {
        if (Array.isArray(availableVersions) && availableVersions.length > 0) {
            setReleaseVersions(availableVersions);
        } else if (currentReleaseId && releaseVersions.length === 0 && displayRelease) {
            setReleaseVersions([displayRelease]);
        }
    }, [availableVersions, currentReleaseId, displayRelease, releaseVersions.length]);
    const targetLanguage = displayRelease?.metadata?.analysis_config?.description_language;
    const projectContext = useArchiveProjectContext({
        selectedProject,
        onSelectedProjectChange,
        targetLanguage,
        skipGlossary: isDemoProject,
    });
    const toolbarProjects = useMemo(() => {
        if (projectContext.projects.some((project) => project.project_id === PUBLISHED_ARCHIVE_DEMO_PROJECT_ID)) {
            return projectContext.projects;
        }
        return [...projectContext.projects, publishedArchiveDemoProject];
    }, [projectContext.projects]);
    const projectToolbar = (
        <PublishedArchiveToolbar
            projects={toolbarProjects}
            selectedProject={selectedProject}
            onSelectedProjectChange={onSelectedProjectChange}
            versions={isDemoProject ? [publishedArchiveDemoRelease] : releaseVersions}
            currentRelease={displayRelease}
            selectedReleaseId={isDemoProject ? publishedArchiveDemoRelease.release_id : selectedReleaseId}
            onReleaseChange={isDemoProject ? undefined : setSelectedReleaseId}
            projectName={projectContext.currentProject?.name || (isDemoProject ? publishedArchiveDemoProject.name : selectedProject)}
            onRemoved={isDemoProject ? undefined : refresh}
            disableDelete={isDemoProject}
            t={t}
        />
    );
    if (!selectedProject) {
        return (
            <Container className={`${styles.page} ${styles.publishedContextPage}`} fluid py="xl" data-remis-surface="canvas">
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

    if (isDemoProject) {
        return (
            <Container className={`${styles.page} ${styles.publishedContextPage}`} fluid py="xl" data-remis-surface="canvas">
                {projectToolbar}
                <div data-testid="published-archive-workbench">
                    <ContextTreeV2ArchiveSummary tree={publishedArchiveDemoTree} mode="published" />
                </div>
            </Container>
        );
    }

    if (treeV2State.phase === 'ready' && treeV2State.tree) {
        return (
            <Container className={`${styles.page} ${styles.publishedContextPage}`} fluid py="xl" data-remis-surface="canvas">
                {projectToolbar}
                <div data-testid="published-archive-workbench">
                    <ContextTreeV2ArchiveSummary tree={treeV2State.tree} mode="published" />
                </div>
            </Container>
        );
    }

    if (releaseState.phase === 'idle' || releaseState.phase === 'loading'
        || treeV2State.phase === 'loading') {
        return (
            <Container className={`${styles.page} ${styles.publishedContextPage}`} fluid py="xl" data-remis-surface="canvas">
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

    if (releaseState.phase === 'empty') {
        return (
            <AnalysisPreviewPanel
                selectedProject={selectedProject}
                projectToolbar={projectToolbar}
            />
        );
    }

    if ((releaseState.phase === 'error' || treeV2State.phase === 'error') && !release) {
        return (
            <Container className={`${styles.page} ${styles.publishedContextPage}`} fluid py="xl" data-remis-surface="canvas">
                {projectToolbar}
                <StateCard
                    icon={<IconInfoCircle size={30} />}
                    title={t('mod_archive.release.error_title')}
                    description={treeV2State.error || error || t('mod_archive.release.error_desc')}
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

    return (
        <Container
            className={`${styles.page} ${styles.publishedContextPage}`}
            fluid
            py="xl"
            data-testid="mod-archive-release-panel"
            data-remis-surface="canvas"
        >
            {projectToolbar}
            <StateCard
                icon={<IconArchive size={30} />}
                title={t('mod_archive.release.context_tree_unavailable_title', { defaultValue: 'Context map unavailable' })}
                description={error || t('mod_archive.release.context_tree_unavailable_desc', { defaultValue: 'This release does not contain a published context map yet.' })}
                testId="published-archive-context-map-unavailable"
                action={<Button className={styles.secondaryAction} onClick={refresh}>{t('mod_archive.release.retry')}</Button>}
            />
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
