import React, { useMemo, useState } from 'react';
import {
    Badge, Group, Paper, SimpleGrid, Stack, Switch, Text, Title,
} from '@mantine/core';
import { useTranslation } from 'react-i18next';

import ContextArchiveTreeReview from './ContextArchiveTreeReview';
import { createContextArchiveTreeApi } from './contextArchiveTreeApi';
import styles from '../ModArchive.module.css';

const tierRank = { A: 0, B: 1, C: 2 };
const text = (t, key, fallback, options = {}) => t(key, { defaultValue: fallback, ...options });

const EntityCard = ({ candidate, digest, evidence, advanced, t }) => (
    <Paper className={styles.previewCard} p="md" withBorder data-remis-surface="paper">
        <Stack gap="sm">
            <Group justify="space-between" align="flex-start">
                <div>
                    <Text fw={700}>{candidate.canonical_display_name}</Text>
                    {advanced && <Text size="xs" className={styles.technical}>{candidate.candidate_id}</Text>}
                </div>
                <Group gap="xs">
                    <Badge variant="outline">{candidate.tier}</Badge>
                    <Badge variant="light">{text(t, 'mod_archive.tree_v2.units', 'Units: {{count}}', { count: candidate.local_unit_coverage || 0 })}</Badge>
                </Group>
            </Group>
            {digest?.final_digest || digest?.summary ? (
                <Text size="sm">{digest.final_digest || digest.summary}</Text>
            ) : (
                <Text size="sm" className={styles.paperMuted}>
                    {candidate.summary_eligible
                        ? text(t, 'mod_archive.tree_v2.summary_incomplete', 'Required A/B summary is incomplete; this analysis remains unpublished.')
                        : text(t, 'mod_archive.tree_v2.summary_not_required', 'C-level candidates stay compact.')}
                </Text>
            )}
            <Group gap="xs">
                <Badge variant="light">{text(t, 'mod_archive.tree_v2.mentions', 'Mentions: {{count}}', { count: candidate.mention_count || 0 })}</Badge>
                <Badge variant="light">{text(t, 'mod_archive.tree_v2.groups', 'Event groups: {{count}}', { count: candidate.event_group_coverage || 0 })}</Badge>
            </Group>
            {advanced && (
                <details className={styles.previewDetails}>
                    <summary>{text(t, 'mod_archive.tree_v2.evidence', 'All chunk evidence')} · {evidence.length}</summary>
                    <Stack gap="xs" mt="xs">
                        {evidence.map((item) => (
                            <Paper p="xs" withBorder key={item.evidence_id}>
                                <Text size="xs" className={styles.technical}>
                                    {item.batch_id || '—'} · {item.item_key || item.source_item_id}
                                    {item.digest_segment_id ? ` · ${item.digest_segment_id}` : ''}
                                </Text>
                                <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                                    {item.full_source_text || item.excerpt || '—'}
                                </Text>
                            </Paper>
                        ))}
                        {(candidate.raw_chunk_contributions || []).map((item, index) => (
                            <Text size="xs" className={styles.paperMuted} key={`${candidate.candidate_id}-raw-${index}`}>
                                #{item.batch_index} · {item.surface} · {item.local_description || '—'}
                            </Text>
                        ))}
                    </Stack>
                </details>
            )}
        </Stack>
    </Paper>
);

const EntityList = ({ entities, digestById, evidenceById, advanced, t }) => (
    <div className={styles.previewList}>
        {entities.map((candidate) => (
            <EntityCard
                key={candidate.candidate_id}
                candidate={candidate}
                digest={digestById.get(candidate.candidate_id)}
                evidence={evidenceById.get(candidate.candidate_id) || []}
                advanced={advanced}
                t={t}
            />
        ))}
    </div>
);

export const ContextTreeV2ArchiveSummary = ({ tree, mode = 'published' }) => {
    const { t } = useTranslation();
    const [advanced, setAdvanced] = useState(false);
    const adapter = useMemo(() => createContextArchiveTreeApi(), []);
    const fragments = useMemo(
        () => new Map((tree.local_fragments || []).map((item) => [item.fragment_id, item])),
        [tree.local_fragments],
    );
    const entities = useMemo(() => (tree.candidates || [])
        .filter((item) => item.candidate_kind === 'entity')
        .sort((left, right) => (tierRank[left.tier] ?? 9) - (tierRank[right.tier] ?? 9)
            || String(left.canonical_display_name).localeCompare(String(right.canonical_display_name))), [tree.candidates]);
    const primary = entities.filter((item) => ['A', 'B'].includes(item.tier));
    const lower = entities.filter((item) => !['A', 'B'].includes(item.tier));
    const digestById = useMemo(
        () => new Map((tree.entity_digests || []).map((item) => [item.entity_id, item])),
        [tree.entity_digests],
    );
    const evidenceById = useMemo(() => {
        const result = new Map();
        (tree.entity_evidence || []).forEach((item) => {
            if (!result.has(item.entity_id)) result.set(item.entity_id, []);
            result.get(item.entity_id).push(item);
        });
        return result;
    }, [tree.entity_evidence]);

    return (
        <Stack gap="lg" data-testid={`context-tree-v2-${mode}`}>
            <Group justify="space-between" align="flex-start">
                <div>
                    <Title order={2}>{tree.project_title || text(t, 'mod_archive.tree_v2.title', 'Project archive')}</Title>
                    <Text size="sm" className={styles.subtitle}>{tree.project_summary || '—'}</Text>
                </div>
                <Switch
                    checked={advanced}
                    onChange={(event) => setAdvanced(event.currentTarget.checked)}
                    label={t('advanced_options')}
                />
            </Group>
            {mode !== 'published' && (
                <Paper p="sm" withBorder>
                    <Text size="sm">{text(t, 'mod_archive.tree_v2.unpublished', 'Unpublished analysis preview. Review incomplete summaries or unresolved relationships before publishing.')}</Text>
                </Paper>
            )}
            <section>
                <Group justify="space-between" mb="xs">
                    <Title order={3}>{text(t, 'mod_archive.tree_v2.events', 'Event groups')}</Title>
                    <Badge variant="outline">{(tree.groups || []).length}</Badge>
                </Group>
                <SimpleGrid cols={{ base: 1, md: 2 }}>
                    {(tree.groups || []).map((group) => (
                        <Paper p="md" withBorder key={group.group_id}>
                            <Text fw={700}>{group.title || group.group_id}</Text>
                            <Stack gap={4} mt="xs">
                                {(group.fragment_ids || []).map((id) => (
                                    <Text size="sm" key={id}>• {fragments.get(id)?.summary || id}</Text>
                                ))}
                            </Stack>
                        </Paper>
                    ))}
                </SimpleGrid>
            </section>
            <section>
                <Group justify="space-between" mb="xs">
                    <Title order={3}>{text(t, 'mod_archive.tree_v2.entities', 'Entities')}</Title>
                    <Badge variant="outline">{entities.length}</Badge>
                </Group>
                <EntityList entities={primary} digestById={digestById} evidenceById={evidenceById} advanced={advanced} t={t} />
                {lower.length > 0 && (
                    <details className={styles.previewDetails}>
                        <summary>{text(t, 'mod_archive.tree_v2.lower_entities', 'C / unclassified entities')} · {lower.length}</summary>
                        <EntityList entities={lower} digestById={digestById} evidenceById={evidenceById} advanced={advanced} t={t} />
                    </details>
                )}
            </section>
            {advanced && (
                <ContextArchiveTreeReview
                    projectId={tree.project_id}
                    releaseId={tree.release_id}
                    draftId={tree.draft_id}
                    mode={mode}
                    treeData={tree}
                    adapter={adapter}
                />
            )}
        </Stack>
    );
};

export default ContextTreeV2ArchiveSummary;
