import React from 'react';
import { Badge, Group, Paper, Stack, Text, Title } from '@mantine/core';

import { normalizeEntityEvidence } from './entityEvidenceModel';
import styles from './EntityEvidenceDetails.module.css';

const translate = (t, key, defaultValue, options = {}) => t(key, { ...options, defaultValue });

const displayText = (value, fallback) => value || fallback;

const EntityEvidenceDetails = ({ entry, preview, t }) => {
    const details = normalizeEntityEvidence(entry, preview);
    const entityId = details.aggregateId || entry?.aggregate_id || 'entity';
    return (
        <section className={styles.root} data-testid={`entity-evidence-details-${entityId}`}>
            <Group justify="space-between" align="center" gap="xs">
                <Title order={5} className={styles.heading}>
                    {translate(t, 'mod_archive.release.preview.entity_evidence.title', 'Evidence detail')}
                </Title>
                <Badge variant="outline">
                    {translate(t, 'mod_archive.release.preview.entity_evidence.tier', `Tier ${details.tier}`, { tier: details.tier })}
                </Badge>
            </Group>

            {details.isSummaryTier ? (
                <div className={styles.comparisonGrid} data-testid="entity-evidence-digest-comparison">
                    <Paper className={styles.comparisonPanel} withBorder>
                        <Text className={styles.panelLabel} fw={700}>
                            {translate(t, 'mod_archive.release.preview.entity_evidence.mechanical', 'Mechanical local description')}
                        </Text>
                        <Text className={styles.panelText} size="sm" data-testid="entity-evidence-mechanical">
                            {displayText(details.mechanicalLocalDescription, translate(
                                t,
                                'mod_archive.release.preview.entity_evidence.missing_mechanical',
                                'No mechanical concatenation was provided.',
                            ))}
                        </Text>
                    </Paper>
                    <Paper className={styles.comparisonPanel} withBorder>
                        <Text className={styles.panelLabel} fw={700}>
                            {translate(t, 'mod_archive.release.preview.entity_evidence.final_digest', 'Final LLM digest')}
                        </Text>
                        <Text className={styles.panelText} size="sm" data-testid="entity-evidence-final-digest">
                            {displayText(details.finalDigest, translate(
                                t,
                                'mod_archive.release.preview.entity_evidence.missing_final_digest',
                                'No final digest was generated.',
                            ))}
                        </Text>
                    </Paper>
                </div>
            ) : (
                <div className={styles.notice} data-testid="entity-evidence-no-summary">
                    <Text size="sm">
                        {translate(
                            t,
                            'mod_archive.release.preview.entity_evidence.no_summary',
                            'C-level candidates do not generate a long summary.',
                        )}
                    </Text>
                </div>
            )}

            {details.partialDigests.length > 0 && (
                <Stack gap="xs" data-testid="entity-evidence-partial-digests">
                    <Text className={styles.heading} fw={700} size="sm">
                        {translate(t, 'mod_archive.release.preview.entity_evidence.partial_digests', 'Partial digests')}
                    </Text>
                    <div className={styles.partialList}>
                        {details.partialDigests.map((digest) => (
                            <Paper className={styles.partialItem} withBorder key={`${digest.id}-${digest.text}`}>
                                <Text className={styles.evidenceMeta}>
                                    {translate(t, 'mod_archive.release.preview.entity_evidence.digest_segment_id', 'digest_segment_id')}: {digest.digestSegmentId}
                                </Text>
                                <Text className={styles.panelText} size="sm">{digest.text}</Text>
                            </Paper>
                        ))}
                    </div>
                </Stack>
            )}

            <Stack gap="xs" data-testid="entity-evidence-all">
                <Group justify="space-between" align="center" gap="xs">
                    <Text className={styles.heading} fw={700} size="sm">
                        {translate(t, 'mod_archive.release.preview.entity_evidence.all_evidence', 'All evidence')}
                    </Text>
                    <Badge variant="outline">{details.evidenceCount}</Badge>
                </Group>
                {!details.evidenceIsComplete && (
                    <Text className={styles.notice} size="xs" data-testid="entity-evidence-completeness-note">
                        {translate(
                            t,
                            'mod_archive.release.preview.entity_evidence.full_payload_unavailable',
                            'The full evidence payload is not available in this preview.',
                        )}
                    </Text>
                )}
                {details.evidence.length > 0 ? (
                    <ul className={styles.evidenceList}>
                        {details.evidence.map((evidence) => (
                            <li className={styles.evidenceItem} key={evidence.id}>
                                <Group justify="space-between" align="flex-start" gap="sm" wrap="wrap">
                                    <Text className={`${styles.evidenceMeta} ${styles.evidenceId}`}>
                                        {evidence.displayId}
                                        {evidence.sourceRef ? ` · ${evidence.sourceRef}` : ''}
                                    </Text>
                                    <Text className={styles.evidenceMeta}>
                                        {translate(t, 'mod_archive.release.preview.entity_evidence.digest_segment_id', 'digest_segment_id')}: {evidence.digestSegmentIds.join(' · ') || '—'}
                                    </Text>
                                </Group>
                                <Text className={styles.evidenceText} size="sm">
                                    {displayText(evidence.localDescription, translate(
                                        t,
                                        'mod_archive.release.preview.entity_evidence.missing_evidence_text',
                                        'No local description was provided.',
                                    ))}
                                </Text>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <Text className={styles.muted} size="sm">
                        {translate(t, 'mod_archive.release.preview.entity_evidence.no_evidence', 'No evidence was provided.')}
                    </Text>
                )}
            </Stack>
        </section>
    );
};

export default EntityEvidenceDetails;
