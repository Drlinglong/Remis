import React, { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Alert,
    Badge,
    Button,
    Container,
    Divider,
    Group,
    Loader,
    Paper,
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
import ModArchiveOverrideEditor from './ModArchiveOverrideEditor';
import { useModArchiveDraft } from './useModArchiveDraft';
import { useModArchiveRelease } from './useModArchiveRelease';
import styles from './ModArchive.module.css';

const formatValue = (value) => {
    if (typeof value === 'string') return value;
    if (value?.summary && typeof value.summary === 'string') return value.summary;
    return JSON.stringify(value || {}, null, 2);
};

const scopeValue = (metadata) => {
    const scope = metadata?.analysis_scope;
    if (typeof scope === 'string') return scope;
    return scope?.mode || scope?.scope || '';
};

const SummarySection = ({ kind, title, entries, emptyLabel, t }) => (
    <section className={styles.summarySection} data-kind={kind}>
        <Group justify="space-between" mb="xs">
            <Title order={4}>{title}</Title>
            <Badge variant="outline">{entries.length}</Badge>
        </Group>
        {entries.length > 0 ? (
            <div className={styles.entryList}>
                {entries.map((entry) => (
                    <Paper
                        className={styles.entryCard}
                        key={entry.key}
                        data-remis-surface="paper"
                    >
                        <Text fw={700} className={styles.technical}>{entry.label}</Text>
                        <Text className={styles.entryValue} size="sm">
                            {formatValue(entry.value)}
                        </Text>
                        {entry.override && (
                            <Stack gap={2} mt="xs">
                                <Badge variant="light" w="fit-content">
                                    {t('mod_archive.release.override_badge')}
                                </Badge>
                                <Text size="xs" className={styles.entryValue}>
                                    {t('mod_archive.release.effective_override')}: {formatValue(entry.override)}
                                </Text>
                            </Stack>
                        )}
                    </Paper>
                ))}
            </div>
        ) : (
            <Text className={styles.muted} size="sm">{emptyLabel}</Text>
        )}
    </section>
);

const PublishedArchivePanel = ({ selectedProject, status }) => {
    const { t } = useTranslation();
    const [publishedChildReleaseId, setPublishedChildReleaseId] = useState(null);
    const releaseState = useModArchiveRelease(selectedProject);
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
    const entries = useMemo(() => getArchiveEntries(effective), [effective]);
    const counts = useMemo(() => getArchiveCounts(effective), [effective]);
    const rows = getTraceabilityRows(traceability);
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
                <StateCard
                    icon={<IconArchive size={30} />}
                    title={t('mod_archive.release.no_project_title')}
                    description={t('mod_archive.release.no_project_desc')}
                    testId="mod-archive-release-empty"
                />
            </Container>
        );
    }

    if (phase === 'idle' || phase === 'loading') {
        return (
            <Container className={styles.page} size="xl" py="xl" data-remis-surface="canvas">
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
            <Container className={styles.page} size="xl" py="xl" data-remis-surface="canvas">
                <StateCard
                    icon={<IconArchive size={30} />}
                    title={t('mod_archive.release.empty_title')}
                    description={t('mod_archive.release.empty_desc')}
                    testId="mod-archive-release-empty"
                />
            </Container>
        );
    }

    if (phase === 'error' && !release) {
        return (
            <Container className={styles.page} size="xl" py="xl" data-remis-surface="canvas">
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
            <Group className={styles.header} wrap="nowrap">
                <Badge className={styles.headerIcon} size="xl" radius="sm">
                    <IconArchive size={22} />
                </Badge>
                <Stack gap={2} style={{ minWidth: 0 }}>
                    <Title order={2}>{t('mod_archive.release.title')}</Title>
                    <Text className={styles.subtitle} size="sm">
                        {t('mod_archive.release.subtitle')}
                    </Text>
                </Stack>
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

            <Paper className={styles.releaseHeader} p="lg" withBorder data-remis-surface="surface">
                <Stack gap="md">
                    <Group justify="space-between" align="flex-start">
                        <div>
                            <Title order={3}>{t('mod_archive.release.metadata_title')}</Title>
                            <Text className={styles.muted} size="sm">
                                {t('mod_archive.release.read_only')}
                            </Text>
                        </div>
                        <Group gap="xs">
                            <Button
                                className={styles.secondaryAction}
                                variant="outline"
                                size="sm"
                                onClick={draftState.startDraft}
                                loading={draftState.phase === 'starting'}
                                disabled={draftState.phase === 'starting' || draftState.phase === 'publishing'}
                                data-remis-action="secondary"
                                data-testid="mod-archive-start-draft"
                            >
                                {t('mod_archive.release.start_draft')}
                            </Button>
                            <Button className={styles.secondaryAction} variant="outline" size="sm" onClick={refresh} leftSection={<IconRefresh size={15} />} data-remis-action="secondary">
                                {t('mod_archive.release.refresh')}
                            </Button>
                        </Group>
                    </Group>
                    <div className={styles.metadataGrid}>
                        <MetadataCell label={t('mod_archive.release.release_id')} value={release.release_id} technical />
                        <MetadataCell label={t('mod_archive.release.project_id')} value={release.project_id || selectedProject} technical />
                        <MetadataCell label={t('mod_archive.release.created_at')} value={release.metadata?.created_at} />
                        <MetadataCell label={t('mod_archive.release.analysis_scope')} value={scopeValue(release.metadata)} />
                        <MetadataCell label={t('mod_archive.release.source_snapshot')} value={release.metadata?.source_snapshot_hash} technical />
                        <MetadataCell label={t('mod_archive.release.upstream_version')} value={release.metadata?.upstream_version || t('mod_archive.release.not_available')} />
                        <MetadataCell label={t('mod_archive.release.provider')} value={release.metadata?.provider_id} />
                        <MetadataCell label={t('mod_archive.release.model')} value={release.metadata?.model_id} />
                        {release.metadata?.parent_release_id && (
                            <MetadataCell label={t('mod_archive.release.parent_release')} value={release.metadata.parent_release_id} technical />
                        )}
                    </div>
                </Stack>
            </Paper>

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

            <Paper className={styles.paper} p="lg" mt="md" withBorder data-remis-surface="paper">
                <Stack gap="md">
                    <div>
                        <Title order={3}>{t('mod_archive.release.summary_title')}</Title>
                        <Text c="dimmed" size="sm">
                            {t('mod_archive.release.summary_desc')}
                        </Text>
                    </div>
                    <div className={styles.summaryGrid}>
                        <SummarySection
                            kind="project"
                            title={t('mod_archive.release.project_summary')}
                            entries={entries.filter((entry) => entry.kind === 'project')}
                            emptyLabel={t('mod_archive.release.no_project_summary')}
                            t={t}
                        />
                        <SummarySection
                            kind="entity"
                            title={t('mod_archive.release.entity_summary', { count: counts.entity })}
                            entries={entries.filter((entry) => entry.kind === 'entity')}
                            emptyLabel={t('mod_archive.release.no_entity_summary')}
                            t={t}
                        />
                        <SummarySection
                            kind="event"
                            title={t('mod_archive.release.event_summary', { count: counts.event })}
                            entries={entries.filter((entry) => entry.kind === 'event')}
                            emptyLabel={t('mod_archive.release.no_event_summary')}
                            t={t}
                        />
                    </div>

                    <Divider />
                    <details className={styles.traceability} data-testid="mod-archive-traceability">
                        <summary className={styles.traceabilitySummary}>
                            {t('mod_archive.release.traceability_title')}
                        </summary>
                        <Stack gap="sm" mt="sm">
                            <Text size="sm" c="dimmed">{t('mod_archive.release.traceability_desc')}</Text>
                            {traceabilityState === 'idle' && (
                                <Button
                                    className={styles.secondaryAction}
                                    variant="outline"
                                    onClick={loadTraceability}
                                    data-remis-action="secondary"
                                    data-testid="mod-archive-load-traceability"
                                >
                                    {t('mod_archive.release.load_traceability')}
                                </Button>
                            )}
                            {traceabilityState === 'loading' && <Loader size="sm" />}
                            {traceabilityState === 'error' && (
                                <Text c="red" size="sm">{traceabilityError}</Text>
                            )}
                            {traceabilityState === 'ready' && rows.length === 0 && (
                                <Text c="dimmed" size="sm">{t('mod_archive.release.traceability_empty')}</Text>
                            )}
                            {traceabilityState === 'ready' && rows.length > 0 && (
                                <div className={styles.traceabilityList}>
                                    {rows.map((row, index) => (
                                        <Paper className={styles.traceabilityRow} key={`${row.aggregateKey}-${row.sourceRef}-${index}`} data-remis-surface="surface">
                                            <Group gap="xs" mb={4}>
                                                <Badge variant="outline">{row.provenance}</Badge>
                                                <Badge variant="light">{row.contributionType}</Badge>
                                            </Group>
                                            <Text className={styles.technical} size="sm">{row.aggregateKey}</Text>
                                            <Text className={styles.technical} size="xs" c="dimmed">{row.sourceRef}</Text>
                                            {row.sourceContent && <Text size="sm" mt={4}>{row.sourceContent}</Text>}
                                        </Paper>
                                    ))}
                                </div>
                            )}
                        </Stack>
                    </details>
                </Stack>
            </Paper>
        </Container>
    );
};

const MetadataCell = ({ label, value, technical = false }) => (
    <div className={styles.metadataCell}>
        <Text className={styles.metadataLabel}>{label}</Text>
        <Text className={technical ? styles.technical : undefined} size="sm" title={value || ''}>
            {value || '—'}
        </Text>
    </div>
);

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
