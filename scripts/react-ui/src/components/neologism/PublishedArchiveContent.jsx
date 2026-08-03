import React, { useMemo } from 'react';
import {
    Badge,
    Button,
    Divider,
    Group,
    Loader,
    Paper,
    Stack,
    Text,
    Title,
} from '@mantine/core';
import { IconRefresh } from '@tabler/icons-react';

import CandidateGovernanceSection from './CandidateGovernanceSection';
import styles from './ModArchive.module.css';

const CODE_LABELS = {
    provenance: {
        text_inferred: 'Text-inferred',
        script_derived: 'Script-derived',
        user_confirmed: 'User-confirmed',
    },
    contribution_type: {
        mention: 'Mention',
        fact: 'Fact',
        event: 'Event',
        relationship: 'Relationship',
    },
};

const KIND_ORDER = { project: 0, event: 1, entity: 2 };

export const formatContextSchemaVersion = (value) => {
    const match = /^context-v(\d+)$/.exec(value || '');
    return match ? `v0.0.${match[1]}` : value;
};

const formatValue = (value) => {
    if (typeof value === 'string') return value;
    if (value?.summary && typeof value.summary === 'string') return value.summary;
    return JSON.stringify(value || {}, null, 2);
};

const entryDisplayLabel = (entry) => (
    entry.termReference?.translation
        ? `${entry.label}（${entry.termReference.translation}）`
        : entry.label
);

const translateCode = (t, namespace, code) => t(
    `mod_archive.release.${namespace}.${code}`,
    { defaultValue: CODE_LABELS[namespace]?.[code] || code },
);

const formatPublishedAt = (value) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    const pad = (part) => String(part).padStart(2, '0');
    return [
        `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
        `${pad(date.getHours())}:${pad(date.getMinutes())}`,
    ].join(' ');
};

const MetadataCell = ({ label, value, technical = false }) => (
    <div className={styles.metadataCell}>
        <Text className={styles.metadataLabel}>{label}</Text>
        <Text
            className={`${styles.metadataValue} ${technical ? styles.technical : ''}`}
            size="sm"
            title={value || ''}
        >
            {value || '—'}
        </Text>
    </div>
);

export const ReleaseMetadata = ({
    release,
    selectedProject,
    scope,
    draftState,
    refresh,
    t,
}) => {
    const scopeLabel = t(`mod_archive.release.analysis_scopes.${scope}`, {
        defaultValue: scope,
    });
    const schemaLabel = formatContextSchemaVersion(release.metadata?.schema_version);
    return (
        <Paper className={styles.releaseHeader} p="lg" withBorder data-remis-surface="surface">
        <Stack gap="md">
            <Group justify="space-between" align="flex-start">
                <Text className={styles.muted} size="sm">
                    {t('mod_archive.release.read_only')}
                </Text>
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
                    <Button
                        className={styles.secondaryAction}
                        variant="outline"
                        size="sm"
                        onClick={refresh}
                        leftSection={<IconRefresh size={15} />}
                        data-remis-action="secondary"
                    >
                        {t('mod_archive.release.refresh')}
                    </Button>
                </Group>
            </Group>
            <div className={styles.primaryMetadataGrid}>
                <MetadataCell
                    label={t('mod_archive.release.created_at')}
                    value={formatPublishedAt(release.metadata?.created_at)}
                />
                <MetadataCell label={t('mod_archive.release.provider')} value={release.metadata?.provider_id} />
                <MetadataCell label={t('mod_archive.release.model')} value={release.metadata?.model_id} />
            </div>
            <details className={styles.metadataDetails} data-testid="mod-archive-metadata-details">
                <summary className={styles.metadataSummary}>
                    {t('mod_archive.release.metadata_title')}
                </summary>
                <div className={styles.metadataGrid}>
                    <MetadataCell label={t('mod_archive.release.release_id')} value={release.release_id} technical />
                    <MetadataCell label={t('mod_archive.release.project_id')} value={release.project_id || selectedProject} technical />
                    <MetadataCell label={t('mod_archive.release.analysis_scope')} value={scopeLabel} />
                    <MetadataCell label={t('mod_archive.release.schema_version')} value={schemaLabel} technical />
                    <MetadataCell label={t('mod_archive.release.source_snapshot')} value={release.metadata?.source_snapshot_hash} technical />
                    <MetadataCell label={t('mod_archive.release.upstream_version')} value={release.metadata?.upstream_version || t('mod_archive.release.not_available')} />
                    {release.metadata?.parent_release_id && (
                        <MetadataCell label={t('mod_archive.release.parent_release')} value={release.metadata.parent_release_id} technical />
                    )}
                </div>
                <div className={styles.promptExample}>
                    <Text className={styles.metadataLabel}>
                        {t('mod_archive.release.prompt_example')}
                    </Text>
                    <pre className={styles.promptExampleText} data-testid="mod-archive-prompt-example">
                        {release.metadata?.prompt_example || t('mod_archive.release.prompt_example_unavailable')}
                    </pre>
                </div>
            </details>
        </Stack>
        </Paper>
    );
};

const SummarySection = ({ kind, title, entries, emptyLabel, hideEntryLabel = false, t }) => (
    <section className={styles.summarySection} data-kind={kind}>
        <Group justify="space-between" mb="xs">
            <Title order={4}>{title}</Title>
            <Badge variant="outline">{entries.length}</Badge>
        </Group>
        {entries.length > 0 ? (
            <div className={styles.entryList}>
                {entries.map((entry) => (
                    <Paper className={styles.entryCard} key={entry.key} data-remis-surface="paper">
                        {!hideEntryLabel && (
                            <Group gap="xs" align="center">
                                <Text fw={700} className={styles.technical}>
                                    {entryDisplayLabel(entry)}
                                </Text>
                                {entry.termReference && (
                                    <Badge variant="light" size="xs">
                                        {t(`mod_archive.release.term_status.${entry.termReference.status}`, {
                                            defaultValue: entry.termReference.status,
                                        })}
                                    </Badge>
                                )}
                            </Group>
                        )}
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
            <Text className={styles.paperMuted} size="sm">{emptyLabel}</Text>
        )}
    </section>
);

const groupTraceabilityRows = (rows) => {
    const groups = new Map();
    rows.forEach((row) => {
        const key = row.aggregateKey || `${row.aggregateType}:unknown`;
        if (!groups.has(key)) {
            groups.set(key, {
                key,
                kind: row.aggregateType || 'entity',
                rows: [],
                deliveryMembershipCount: 0,
            });
        }
        groups.get(key).rows.push(row);
        groups.get(key).deliveryMembershipCount = Math.max(
            groups.get(key).deliveryMembershipCount,
            row.deliveryMembershipCount || 0,
        );
    });
    return Array.from(groups.values()).sort((left, right) => (
        (KIND_ORDER[left.kind] - KIND_ORDER[right.kind]) || left.key.localeCompare(right.key)
    ));
};

const EvidenceGroup = ({ group, entry, t }) => {
    const fallbackLabel = group.key.replace(/^(project|entity|event)[:/]/, '');
    const displayLabel = group.kind === 'project'
        ? t('mod_archive.release.project_summary')
        : (entry ? entryDisplayLabel(entry) : fallbackLabel);
    const evidenceRows = group.rows.filter((row) => !row.placeholder);
    return (
        <details className={styles.evidenceGroup}>
            <summary className={styles.evidenceGroupSummary}>
                <span className={styles.technical}>{displayLabel}</span>
                <Group gap="xs">
                    <Badge variant="outline" size="sm">
                        {t('mod_archive.release.evidence_membership_count', { count: evidenceRows.length })}
                    </Badge>
                    {group.kind === 'event' && (
                        <Badge variant="light" size="sm">
                            {t('mod_archive.release.delivery_membership_count', {
                                count: group.deliveryMembershipCount,
                            })}
                        </Badge>
                    )}
                </Group>
            </summary>
            <div className={styles.traceabilityList}>
                {evidenceRows.map((row, index) => (
                    <Paper
                        className={styles.traceabilityRow}
                        key={`${row.sourceRef}-${index}`}
                        data-remis-surface="paper"
                    >
                        <Group gap="xs" mb={4}>
                            <Badge variant="outline">
                                {translateCode(t, 'provenance', row.provenance)}
                            </Badge>
                            <Badge variant="light">
                                {translateCode(t, 'contribution_type', row.contributionType)}
                            </Badge>
                        </Group>
                        <Text className={styles.technical} size="xs" c="dimmed">{row.sourceRef}</Text>
                        {row.sourceContent && <Text size="sm" mt={4}>{row.sourceContent}</Text>}
                    </Paper>
                ))}
            </div>
        </details>
    );
};

const TraceabilityContent = ({ rows, entries, t }) => {
    const groups = useMemo(() => groupTraceabilityRows(rows), [rows]);
    const entriesByKey = useMemo(() => new Map(entries.map((entry) => [entry.key, entry])), [entries]);
    return (
        <Stack gap="lg">
            <CandidateGovernanceSection rows={rows} t={t} />
            {['project', 'event', 'entity'].map((kind) => {
                const kindGroups = groups.filter((group) => group.kind === kind);
                if (kindGroups.length === 0) return null;
                return (
                    <section className={styles.evidenceSection} data-kind={kind} key={kind}>
                        <Title order={4} mb="xs">
                            {t(`mod_archive.release.${kind}_summary`, { count: kindGroups.length })}
                        </Title>
                        <Stack gap="xs">
                            {kindGroups.map((group) => (
                                <EvidenceGroup
                                    group={group}
                                    entry={entriesByKey.get(group.key)}
                                    key={group.key}
                                    t={t}
                                />
                            ))}
                        </Stack>
                    </section>
                );
            })}
        </Stack>
    );
};

export const ArchiveSummary = ({
    entries,
    counts,
    rows,
    traceabilityState,
    traceabilityError,
    loadTraceability,
    t,
}) => (
    <Paper className={styles.paper} p="lg" mt="md" withBorder data-remis-surface="paper">
        <Stack gap="md">
            <div>
                <Title order={3}>{t('mod_archive.release.summary_title')}</Title>
                <Text className={styles.paperMuted} size="sm">
                    {t('mod_archive.release.summary_desc')}
                </Text>
            </div>
            <div className={styles.summaryFlow}>
                <SummarySection
                    kind="project"
                    title={t('mod_archive.release.project_summary')}
                    entries={entries.filter((entry) => entry.kind === 'project')}
                    emptyLabel={t('mod_archive.release.no_project_summary')}
                    hideEntryLabel
                    t={t}
                />
                <SummarySection
                    kind="event"
                    title={t('mod_archive.release.event_summary', { count: counts.event })}
                    entries={entries.filter((entry) => entry.kind === 'event')}
                    emptyLabel={t('mod_archive.release.no_event_summary')}
                    t={t}
                />
                <SummarySection
                    kind="entity"
                    title={t('mod_archive.release.entity_summary', { count: counts.entity })}
                    entries={entries.filter((entry) => entry.kind === 'entity')}
                    emptyLabel={t('mod_archive.release.no_entity_summary')}
                    t={t}
                />
            </div>

            <Divider />
            <details className={styles.traceability} data-testid="mod-archive-traceability">
                <summary className={styles.traceabilitySummary}>
                    {t('mod_archive.release.traceability_title')}
                </summary>
                <Stack gap="sm" mt="sm">
                    <Text size="sm" className={styles.paperMuted}>
                        {t('mod_archive.release.traceability_desc')}
                    </Text>
                    {traceabilityState === 'idle' && (
                        <Button
                            className={styles.paperSecondaryAction}
                            variant="outline"
                            onClick={loadTraceability}
                            data-remis-action="paper-secondary"
                            data-testid="mod-archive-load-traceability"
                        >
                            {t('mod_archive.release.load_traceability')}
                        </Button>
                    )}
                    {traceabilityState === 'loading' && <Loader size="sm" />}
                    {traceabilityState === 'error' && <Text c="red" size="sm">{traceabilityError}</Text>}
                    {traceabilityState === 'ready' && rows.length === 0 && (
                        <Text className={styles.paperMuted} size="sm">
                            {t('mod_archive.release.traceability_empty')}
                        </Text>
                    )}
                    {traceabilityState === 'ready' && rows.length > 0 && (
                        <TraceabilityContent rows={rows} entries={entries} t={t} />
                    )}
                </Stack>
            </details>
        </Stack>
    </Paper>
);
