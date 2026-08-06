import React from 'react';
import { Badge, Group, Paper, Stack, Text, Title } from '@mantine/core';

import styles from './PublishedContextWorkbench.module.css';

const text = (t, key, fallback, options = {}) => {
    const value = t(key, { defaultValue: fallback, ...options });
    return typeof value === 'string'
        ? value.replace(/\{\{(\w+)\}\}/g, (_, name) => options[name] ?? `{{${name}}}`)
        : value;
};

const sourceForUnit = (unit, index) => ({
    id: `${unit.id}-${index}`,
    label: unit.sourceRef || unit.label || unit.id,
    text: unit.sourceText || unit.summary || '',
});

const PublishedContextEventDetail = ({ tree, selectedFragmentId, selectedGroupId, onClearSelection, onSelectFragment, t }) => {
    const fragment = selectedFragmentId ? tree.fragments[selectedFragmentId] : null;
    const group = (fragment && tree.groups.find((item) => item.fragmentIds.includes(fragment.id)))
        || tree.groups.find((item) => item.id === selectedGroupId);
    const groupFragments = group
        ? group.fragmentIds.map((fragmentId) => tree.fragments[fragmentId]).filter(Boolean)
        : [];
    const sources = fragment
        ? fragment.unitIds.map((unitId, index) => sourceForUnit(tree.units[unitId] || { id: unitId, label: unitId }, index))
        : [];
    return (
        <Paper className={styles.detailPanel} p="md" withBorder data-remis-surface="paper" data-testid="published-context-detail">
            <header className={styles.detailHeader}>
                <div>
                    <Text className={styles.detailEyebrow}>{text(t, 'mod_archive.tree_v2.detail_eyebrow', 'EVENT DETAIL')}</Text>
                    <Title order={2} className={styles.detailTitle}>
                        {fragment?.label || group?.label || text(t, 'mod_archive.tree_v2.detail_title', 'Event details')}
                    </Title>
                </div>
                {(fragment || group) && <button type="button" className={styles.mapBack} onClick={onClearSelection}>{text(t, 'mod_archive.tree_v2.detail_back', 'Back to map')}</button>}
            </header>
            {!fragment && !group ? (
                <div className={styles.emptyDetail} data-testid="published-context-detail-empty">
                    <div>
                        <Text className={styles.emptyDetailTitle}>{text(t, 'mod_archive.tree_v2.detail_empty_title', 'Select an event chain')}</Text>
                        <Text size="sm" mt="xs">{text(t, 'mod_archive.tree_v2.detail_empty_desc', 'Choose a card on the map to inspect its context and source text.')}</Text>
                    </div>
                </div>
            ) : (
                <Stack className={styles.detailBody} gap="md" mt="md">
                    <Group className={styles.detailMeta} gap="xs">
                        {group && <Badge variant="light">{group.label}</Badge>}
                        {fragment ? (
                            <>
                                <Badge variant="outline">{fragment.route}</Badge>
                                <Badge variant="outline">{text(t, 'mod_archive.tree_v2.units', '{{count}} units', { count: fragment.unitIds.length })}</Badge>
                            </>
                        ) : (
                            <Badge variant="outline">{text(t, 'mod_archive.tree_v2.fragments', '{{count}} cards', { count: groupFragments.length })}</Badge>
                        )}
                    </Group>
                    <Text className={styles.detailSummary}>
                        {fragment?.summary || group?.summary || text(t, 'mod_archive.tree_v2.no_summary', 'No fragment summary is available.')}
                    </Text>
                    {!fragment && group && (
                        <section className={styles.chainDetailSection}>
                            <Text className={styles.sourceHeading}>{text(t, 'mod_archive.tree_v2.chain_fragments', 'Chain details')}</Text>
                            <div className={styles.chainDetailList}>
                                {groupFragments.map((item, index) => (
                                    <button
                                        type="button"
                                        className={styles.chainDetailItem}
                                        key={item.id}
                                        onClick={() => onSelectFragment?.(item.id)}
                                    >
                                        <span className={styles.fragmentOrder}>{String(index + 1).padStart(2, '0')}</span>
                                        <span>
                                            <strong>{item.label}</strong>
                                            <span className={styles.chainDetailSummary}>{item.summary || '—'}</span>
                                        </span>
                                    </button>
                                ))}
                            </div>
                        </section>
                    )}
                    {fragment && (
                        <section className={styles.sourceSection}>
                            <Text className={styles.sourceHeading}>{text(t, 'mod_archive.tree_v2.source_text', 'Original source text')}</Text>
                            <div className={styles.sourceList}>
                                {sources.length > 0 ? sources.map((source) => (
                                    <details className={styles.sourceItem} key={source.id}>
                                        <summary>{source.label}</summary>
                                        <Text className={styles.sourceText}>{source.text || text(t, 'mod_archive.tree_v2.source_unavailable', 'Source text is unavailable for this unit.')}</Text>
                                    </details>
                                )) : (
                                    <Text className={styles.noSource}>{text(t, 'mod_archive.tree_v2.no_source', 'No source units are attached to this card.')}</Text>
                                )}
                            </div>
                        </section>
                    )}
                </Stack>
            )}
        </Paper>
    );
};

export default PublishedContextEventDetail;
