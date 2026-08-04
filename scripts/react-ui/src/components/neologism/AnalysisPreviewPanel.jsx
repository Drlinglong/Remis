import React, { useMemo, useState } from 'react';
import {
    Alert, Badge, Button, Container, Group, Loader, Paper, SegmentedControl,
    Select, SimpleGrid, Stack, Switch, Text, TextInput, Title,
} from '@mantine/core';
import { IconArchive, IconInfoCircle, IconRefresh, IconSearch } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import { filterAnalysisPreviewEntries } from './contextAnalysisPreviewModel';
import { useContextAnalysisPreview } from './useContextAnalysisPreview';
import styles from './ModArchive.module.css';

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

const Metric = ({ label, value }) => (
    <div className={styles.previewMetric}>
        <Text className={styles.candidateFieldLabel}>{label}</Text>
        <Text fw={700}>{value ?? 0}</Text>
    </div>
);

const EntityCard = ({ entry, t, advanced = false }) => {
    const payload = entry.payload || {};
    return (
        <Paper className={styles.previewCard} p="md" withBorder data-remis-surface="paper">
            <Stack gap="sm">
                <Group justify="space-between" align="flex-start" wrap="wrap">
                    <div>
                        <Text fw={700} className={styles.candidateName}>{entry.label}</Text>
                        {advanced && <Text size="xs" className={styles.candidateMatchKey}>{entry.aggregate_key}</Text>}
                    </div>
                    <Group gap="xs">
                        {advanced && <Badge variant="light">
                            {t(`mod_archive.release.candidate_kind.${payload.candidate_kind}`, {
                                defaultValue: payload.candidate_kind || '—',
                            })}
                        </Badge>}
                        <Badge variant="outline">
                            {t(`mod_archive.release.candidate_tier.${payload.tier}`, {
                                defaultValue: payload.tier || '—',
                            })}
                        </Badge>
                    </Group>
                </Group>
                {entry.summary ? (
                    <Text size="sm" className={styles.previewSummary}>{entry.summary}</Text>
                ) : (
                    <Text size="sm" className={styles.paperMuted}>
                        {t(
                            payload.summary_eligible
                                ? 'mod_archive.release.preview.summary_missing'
                                : 'mod_archive.release.preview.no_summary',
                            { defaultValue: payload.summary_eligible
                                ? 'This A/B entity summary is missing; rerun analysis to regenerate it.'
                                : 'No long summary is required by the current candidate policy.' },
                        )}
                    </Text>
                )}
                <SimpleGrid cols={{ base: 2, sm: advanced ? 4 : 2 }} spacing="xs">
                    <Metric label={t('mod_archive.release.candidate_coverage.mention_count')} value={payload.mention_count} />
                    {advanced && <Metric label={t('mod_archive.release.candidate_coverage.source_item_coverage')} value={payload.source_item_coverage} />}
                    {advanced && <Metric label={t('mod_archive.release.candidate_coverage.local_unit_coverage')} value={payload.local_unit_coverage} />}
                    <Metric label={t('mod_archive.release.candidate_coverage.event_chain_coverage')} value={payload.event_chain_coverage} />
                </SimpleGrid>
                {advanced && <Group gap="xs">
                    {payload.summary_eligible && <Badge color="green" variant="light">{t('mod_archive.release.preview.summary_eligible')}</Badge>}
                    {payload.glossary_eligible && <Badge color="blue" variant="light">{t('mod_archive.release.preview.glossary_eligible')}</Badge>}
                    {payload.audit_only && <Badge color="gray" variant="outline">{t('mod_archive.release.candidate_audit_only')}</Badge>}
                </Group>}
                {advanced && (payload.aliases || []).length > 0 && (
                    <details className={styles.previewDetails}>
                        <summary>{t('mod_archive.release.candidate_aliases')} · {payload.aliases.length}</summary>
                        <Text size="sm" mt="xs">{payload.aliases.join(' · ')}</Text>
                    </details>
                )}
            </Stack>
        </Paper>
    );
};

const EventCard = ({ entry, t, advanced = false }) => {
    const payload = entry.payload || {};
    const coverage = payload.delivery_coverage || {};
    return (
        <Paper className={styles.previewCard} p="md" withBorder data-remis-surface="paper">
            <Stack gap="sm">
                <Group justify="space-between" align="flex-start" wrap="wrap">
                    <div>
                        <Text fw={700} className={advanced ? styles.technical : undefined}>
                            {advanced ? entry.label : (payload.event || entry.label)}
                        </Text>
                        {advanced && payload.parent_story_id && (
                            <Text size="xs" className={styles.paperMuted}>
                                {t('mod_archive.release.preview.parent_chain')}: {payload.parent_story_id}
                            </Text>
                        )}
                    </div>
                    <Badge variant="outline">
                        {t('mod_archive.release.preview.local_units', {
                            count: coverage.local_unit_coverage || 0,
                        })}
                    </Badge>
                </Group>
                {entry.summary && <Text size="sm" className={styles.previewSummary}>{entry.summary}</Text>}
                <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="xs">
                    <Metric label={t('mod_archive.release.preview.primary')} value={coverage.primary_member} />
                    <Metric label={t('mod_archive.release.preview.supporting')} value={coverage.supporting_context} />
                    <Metric label={t('mod_archive.release.preview.theme')} value={coverage.theme_related} />
                    <Metric label={t('mod_archive.release.preview.evidence_units')} value={(payload.evidence_unit_ids || []).length} />
                </SimpleGrid>
                {advanced && <details className={styles.previewDetails}>
                    <summary>{t('mod_archive.release.preview.chain_details')}</summary>
                    <Stack gap="xs" mt="xs">
                        <Text size="sm"><strong>{t('mod_archive.release.preview.event')}</strong> {payload.event || '—'}</Text>
                        <Text size="sm"><strong>{t('mod_archive.release.preview.consequence')}</strong> {payload.consequence || '—'}</Text>
                        <Text size="sm"><strong>{t('mod_archive.release.preview.participants')}</strong> {(payload.participants || []).join(' · ') || '—'}</Text>
                    </Stack>
                </details>}
            </Stack>
        </Paper>
    );
};

const filterOptions = (t, namespace, values) => values.map((value) => ({
    value,
    label: t(`mod_archive.release.preview.${namespace}.${value}`),
}));

const SimplePreview = ({ preview, t }) => {
    const events = filterAnalysisPreviewEntries(preview.entries, { section: 'event' });
    const entities = filterAnalysisPreviewEntries(preview.entries, { section: 'entity' })
        .filter((entry) => !entry.payload?.candidate_kind || entry.payload.candidate_kind === 'entity');
    const primary = entities.filter((entry) => ['core', 'secondary'].includes(entry.payload?.tier));
    const lower = entities.filter((entry) => !primary.includes(entry));
    return (
        <Paper className={styles.paper} p="lg" mt="md" withBorder data-remis-surface="paper">
            <Stack gap="xl">
                <section>
                    <Group justify="space-between" mb="xs">
                        <Title order={3}>{t('mod_archive.release.preview.events')}</Title>
                        <Badge variant="outline">{events.length}</Badge>
                    </Group>
                    <div className={styles.previewList}>
                        {events.map((entry) => <EventCard entry={entry} key={entry.aggregate_id} t={t} />)}
                    </div>
                </section>
                <section>
                    <Group justify="space-between" mb="xs">
                        <Title order={3}>{t('mod_archive.release.preview.entities')}</Title>
                        <Badge variant="outline">{entities.length}</Badge>
                    </Group>
                    <div className={styles.previewList}>
                        {primary.map((entry) => <EntityCard entry={entry} key={entry.aggregate_id} t={t} />)}
                    </div>
                    {lower.length > 0 && (
                        <details className={styles.previewDetails} data-testid="mod-archive-preview-lower-entities">
                            <summary>
                                {t('mod_archive.release.candidate_tier.incidental', { defaultValue: 'C / Unclassified' })}
                                {' · '}{lower.length}
                            </summary>
                            <div className={styles.previewList}>
                                {lower.map((entry) => <EntityCard entry={entry} key={entry.aggregate_id} t={t} />)}
                            </div>
                        </details>
                    )}
                </section>
            </Stack>
        </Paper>
    );
};

const PreviewContent = ({ preview, refresh, projectToolbar, t }) => {
    const [advanced, setAdvanced] = useState(false);
    const [section, setSection] = useState('entity');
    const [search, setSearch] = useState('');
    const [kind, setKind] = useState('all');
    const [tier, setTier] = useState('all');
    const [summary, setSummary] = useState('all');
    const [policy, setPolicy] = useState('all');
    const entries = useMemo(() => filterAnalysisPreviewEntries(preview.entries, {
        section, search, kind, tier, summary, policy,
    }), [preview.entries, section, search, kind, tier, summary, policy]);
    const counts = preview.counts || {};

    return (
        <Container className={styles.page} size="xl" py="xl" data-testid="mod-archive-analysis-preview" data-remis-surface="canvas">
            {projectToolbar}
            <Group className={styles.header} wrap="wrap">
                <Badge className={styles.headerIcon} size="xl" radius="sm"><IconArchive size={22} /></Badge>
                <Stack gap={2} style={{ flex: '1 1 20rem', minWidth: 0 }}>
                    <Title order={2}>{t('mod_archive.release.preview.title')}</Title>
                    <Text className={styles.subtitle} size="sm">{t('mod_archive.release.preview.subtitle')}</Text>
                </Stack>
                <Button className={styles.secondaryAction} variant="outline" onClick={refresh} leftSection={<IconRefresh size={15} />}>
                    {t('mod_archive.release.refresh')}
                </Button>
                <Switch
                    checked={advanced}
                    onChange={(event) => setAdvanced(event.currentTarget.checked)}
                    label={t('advanced_options')}
                    data-testid="mod-archive-preview-advanced-toggle"
                />
            </Group>
            <Alert className={styles.statusSurface} data-tone="error" mb="md" title={t('mod_archive.release.preview.warning_title')}>
                {t('mod_archive.release.preview.warning_desc')}
            </Alert>
            {advanced && <Paper className={styles.surface} p="lg" withBorder data-remis-surface="surface">
                <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
                    <Metric label={t('mod_archive.release.preview.entities')} value={counts.entities} />
                    <Metric label={t('mod_archive.release.preview.events')} value={counts.events} />
                    <Metric label={t('mod_archive.release.preview.entity_summaries')} value={counts.entity_summaries} />
                    <Metric label={t('mod_archive.release.preview.event_summaries')} value={counts.event_summaries} />
                </SimpleGrid>
                <details className={styles.metadataDetails}>
                    <summary className={styles.metadataSummary}>{t('mod_archive.release.preview.run_metadata')}</summary>
                    <Text size="xs" mt="xs" className={styles.technical}>{preview.run.run_id}</Text>
                    <Text size="sm" mt="xs">{preview.run.provider_id || '—'} · {preview.run.model_id || '—'} · {preview.run.status}</Text>
                </details>
            </Paper>}
            {!advanced && <SimplePreview preview={preview} t={t} />}
            {advanced && <Paper className={styles.paper} p="lg" mt="md" withBorder data-remis-surface="paper">
                <Stack gap="md">
                    <SegmentedControl
                        value={section}
                        onChange={setSection}
                        data={[
                            { label: t('mod_archive.release.preview.entity_tab', { count: counts.entities || 0 }), value: 'entity' },
                            { label: t('mod_archive.release.preview.event_tab', { count: counts.events || 0 }), value: 'event' },
                        ]}
                    />
                    <div className={styles.previewFilters}>
                        <TextInput value={search} onChange={(event) => setSearch(event.currentTarget.value)} leftSection={<IconSearch size={15} />} placeholder={t('mod_archive.release.preview.search')} />
                        {section === 'entity' && (
                            <>
                                <Select value={kind} onChange={(value) => setKind(value || 'all')} data={filterOptions(t, 'kind_filter', ['all', 'entity', 'glossary_term', 'named_phrase', 'incidental_concept'])} />
                                <Select value={tier} onChange={(value) => setTier(value || 'all')} data={filterOptions(t, 'tier_filter', ['all', 'core', 'secondary', 'incidental', 'not_recorded'])} />
                                <Select value={policy} onChange={(value) => setPolicy(value || 'all')} data={filterOptions(t, 'policy_filter', ['all', 'summary_eligible', 'glossary_eligible', 'audit_only'])} />
                            </>
                        )}
                        <Select value={summary} onChange={(value) => setSummary(value || 'all')} data={filterOptions(t, 'summary_filter', ['all', 'with_summary', 'without_summary'])} />
                    </div>
                    <Group justify="space-between">
                        <Title order={3}>{section === 'entity' ? t('mod_archive.release.preview.entities') : t('mod_archive.release.preview.events')}</Title>
                        <Badge variant="outline">{t('mod_archive.release.preview.visible_count', { count: entries.length })}</Badge>
                    </Group>
                    {entries.length === 0 ? (
                        <Text className={styles.paperMuted}>{t('mod_archive.release.preview.no_matches')}</Text>
                    ) : (
                        <div className={styles.previewList}>
                            {entries.map((entry) => (
                                section === 'entity'
                                    ? <EntityCard advanced entry={entry} key={entry.aggregate_id} t={t} />
                                    : <EventCard advanced entry={entry} key={entry.aggregate_id} t={t} />
                            ))}
                        </div>
                    )}
                </Stack>
            </Paper>}
        </Container>
    );
};

const AnalysisPreviewPanel = ({ selectedProject, projectToolbar }) => {
    const { t } = useTranslation();
    const { phase, preview, error, refresh } = useContextAnalysisPreview(selectedProject);
    if (phase === 'ready' && preview) {
        return <PreviewContent preview={preview} refresh={refresh} projectToolbar={projectToolbar} t={t} />;
    }
    const state = phase === 'loading' ? {
        icon: <Loader size="md" />,
        title: t('mod_archive.release.preview.loading_title'),
        description: t('mod_archive.release.preview.loading_desc'),
        testId: 'mod-archive-preview-loading',
    } : phase === 'error' ? {
        icon: <IconInfoCircle size={30} />,
        title: t('mod_archive.release.preview.error_title'),
        description: error,
        testId: 'mod-archive-preview-error',
        action: <Button className={styles.secondaryAction} onClick={refresh}>{t('mod_archive.release.retry')}</Button>,
    } : {
        icon: <IconArchive size={30} />,
        title: t('mod_archive.release.empty_title'),
        description: t('mod_archive.release.empty_desc'),
        testId: 'mod-archive-release-empty',
    };
    return (
        <Container className={styles.page} size="xl" py="xl" data-remis-surface="canvas">
            {projectToolbar}
            <StateCard {...state} />
        </Container>
    );
};

export default AnalysisPreviewPanel;
