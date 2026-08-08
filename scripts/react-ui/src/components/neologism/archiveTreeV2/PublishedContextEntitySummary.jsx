import React, { useMemo } from 'react';
import { Badge, Group, Paper, Stack, Text, Title } from '@mantine/core';

import styles from './PublishedContextWorkbench.module.css';

const text = (t, key, fallback, options = {}) => {
    const value = t(key, { defaultValue: fallback, ...options });
    return typeof value === 'string'
        ? value.replace(/\{\{(\w+)\}\}/g, (_, name) => options[name] ?? `{{${name}}}`)
        : value;
};
const tierRank = { A: 0, B: 1, C: 2 };

const toTier = (value) => {
    const normalized = String(value || '').toUpperCase();
    if (normalized === 'CORE' || normalized === 'TIER_A') return 'A';
    if (normalized === 'SECONDARY' || normalized === 'TIER_B') return 'B';
    return ['A', 'B', 'C'].includes(normalized) ? normalized : 'C';
};

const list = (value) => (Array.isArray(value) ? value : Object.values(value || {}));

const EntityCard = ({ entity, digest, evidence, t }) => (
    <Paper className={styles.entityCard} p="sm" withBorder data-remis-surface="paper" data-testid={`published-context-entity-${entity.id}`}>
        <div className={styles.entityHeader}>
            <Text className={styles.entityName}>{entity.label}</Text>
            <Badge size="sm" variant={entity.tier === 'A' ? 'light' : 'outline'}>{entity.tier}</Badge>
        </div>
        {entity.summary && <Text className={styles.entitySummary} size="sm">{entity.summary}</Text>}
        <div className={styles.entityMeta}>
            <Badge size="xs" variant="light">{text(t, 'mod_archive.tree_v2.mentions', '{{count}} mentions', { count: entity.mentions })}</Badge>
            {entity.unitCount > 0 && <Badge size="xs" variant="light">{text(t, 'mod_archive.tree_v2.units', '{{count}} units', { count: entity.unitCount })}</Badge>}
        </div>
        {evidence.length > 0 && (
            <details className={styles.entityDetails}>
                <summary>{text(t, 'mod_archive.tree_v2.entity_evidence', 'View source evidence')} · {evidence.length}</summary>
                <div className={styles.detailsContent}>
                    <div className={styles.detailsContentInner}>
                        <div className={styles.entityEvidence}>
                            {evidence.map((item, index) => (
                                <Text className={styles.entityEvidenceItem} key={item.evidence_id || `${entity.id}-${index}`}>
                                    {item.source_ref || item.batch_id || item.item_key || '—'}{item.full_source_text || item.excerpt ? ` · ${item.full_source_text || item.excerpt}` : ''}
                                </Text>
                            ))}
                        </div>
                    </div>
                </div>
            </details>
        )}
        {digest && !entity.summary && <Text className={styles.entitySummary} size="sm">{digest.final_digest || digest.summary}</Text>}
    </Paper>
);

const PublishedContextEntitySummary = ({ tree, normalizedTree, t }) => {
    const digestById = useMemo(() => new Map(list(tree.entity_digests).map((item) => [item.entity_id || item.id, item])), [tree.entity_digests]);
    const evidenceById = useMemo(() => {
        const result = new Map();
        list(tree.entity_evidence).forEach((item) => {
            const id = item.entity_id || item.id;
            if (!result.has(id)) result.set(id, []);
            result.get(id).push(item);
        });
        return result;
    }, [tree.entity_evidence]);
    const entities = useMemo(() => {
        const candidates = list(tree.candidates)
            .filter((item) => !item.candidate_kind || item.candidate_kind === 'entity')
            .map((item, index) => ({
                id: String(item.candidate_id || item.entity_id || item.id || `entity-${index + 1}`),
                label: item.canonical_display_name || item.label || item.name || item.entity_id || `Entity ${index + 1}`,
                tier: toTier(item.tier),
                mentions: Number(item.mention_count || item.mentions || 0),
                unitCount: Number(item.local_unit_coverage || item.unit_count || 0),
                summary: item.summary || '',
            }));
        if (candidates.length > 0) return candidates;
        return normalizedTree.referenceAssets.map((asset) => ({
            id: asset.id,
            label: asset.label,
            tier: asset.tier,
            mentions: asset.metadata?.mention_count || 0,
            unitCount: asset.unitIds.length,
            summary: asset.summary,
        }));
    }, [normalizedTree.referenceAssets, tree.candidates]);
    const ordered = [...entities].sort((left, right) => tierRank[left.tier] - tierRank[right.tier] || right.mentions - left.mentions || left.label.localeCompare(right.label));
    const primary = ordered.filter((entity) => entity.tier === 'A' || entity.tier === 'B');
    const lower = ordered.filter((entity) => entity.tier === 'C');
    return (
        <Paper className={styles.entitySection} p="md" withBorder data-remis-surface="surface" data-testid="published-context-entities">
            <header className={styles.panelHeader}>
                <div>
                    <Text className={styles.eyebrow}>{text(t, 'mod_archive.tree_v2.entity_eyebrow', 'ENTITY SUMMARY')}</Text>
                    <Title order={2} className={styles.panelTitle}>{text(t, 'mod_archive.tree_v2.entities', 'Entities')}</Title>
                    <Text className={styles.panelDescription} size="sm">{text(t, 'mod_archive.tree_v2.entities_desc', 'Important entities are ranked by tier and occurrence. Source evidence stays available on demand.')}</Text>
                </div>
                <Badge variant="outline">{ordered.length}</Badge>
            </header>
            {primary.length > 0 ? (
                <div className={styles.entityGrid}>
                    {primary.map((entity) => (
                        <EntityCard key={entity.id} entity={entity} digest={digestById.get(entity.id)} evidence={evidenceById.get(entity.id) || []} t={t} />
                    ))}
                </div>
            ) : (
                <Text className={styles.noSource} mt="md">{text(t, 'mod_archive.tree_v2.no_entities', 'No ranked entities are available in this release.')}</Text>
            )}
            {lower.length > 0 && (
                <details className={styles.lowerEntityGroup}>
                    <summary>{text(t, 'mod_archive.tree_v2.lower_entities', 'Other entities')} · {lower.length}</summary>
                    <div className={styles.detailsContent}>
                        <div className={styles.detailsContentInner}>
                            <div className={styles.entityGrid}>
                                {lower.map((entity) => (
                                    <EntityCard key={entity.id} entity={entity} digest={digestById.get(entity.id)} evidence={evidenceById.get(entity.id) || []} t={t} />
                                ))}
                            </div>
                        </div>
                    </div>
                </details>
            )}
        </Paper>
    );
};

export default PublishedContextEntitySummary;
