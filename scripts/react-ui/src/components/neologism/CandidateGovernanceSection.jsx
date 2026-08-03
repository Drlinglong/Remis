import React, { useMemo } from 'react';
import {
    Badge,
    Group,
    Paper,
    Stack,
    Text,
    Title,
} from '@mantine/core';

import { getCandidateGovernanceGroups } from './modArchiveModel';
import styles from './ModArchive.module.css';

const VISIBLE_GROUPS = ['core', 'secondary'];

const translateCandidate = (t, namespace, value, fallback = value) => t(
    `mod_archive.release.${namespace}.${value}`,
    { defaultValue: fallback },
);

const formatValue = (value, fallback) => {
    if (value === undefined || value === null || value === '') return fallback;
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
};

const formatCandidateLabel = (candidate) => (
    candidate.canonicalDisplayName
        || candidate.aggregateKey?.replace(/^(project|entity|event)[:/]/, '')
        || candidate.normalizedMatchKey
        || '—'
);

const CandidateField = ({ label, value }) => (
    <div className={styles.candidateField}>
        <Text className={styles.candidateFieldLabel}>{label}</Text>
        <Text className={styles.candidateFieldValue} size="sm">{value}</Text>
    </div>
);

const CandidateCard = ({ candidate, index, t }) => {
    const kind = candidate.group;
    const candidateKind = candidate.candidateKind || 'not_recorded';
    const tier = candidate.tier || 'not_recorded';
    const notRecorded = t('mod_archive.release.candidate_not_recorded');
    const eligibility = (value) => (
        value === null || value === undefined
            ? null
            : t(`mod_archive.release.candidate_eligibility.${value ? 'yes' : 'no'}`)
    );
    return (
        <Paper
            className={`${styles.candidateCard} ${kind === 'secondary' ? styles.candidateCardSecondary : ''}`}
            p="sm"
            withBorder
            data-candidate-group={kind}
            data-testid={`mod-archive-candidate-${kind}-${index}`}
            data-remis-surface="paper"
        >
            <Group justify="space-between" align="flex-start" wrap="wrap" gap="xs">
                <Text className={styles.candidateName} fw={700}>{formatCandidateLabel(candidate)}</Text>
                <Group gap="xs">
                    <Badge variant={kind === 'secondary' ? 'light' : 'outline'}>
                        {translateCandidate(t, 'candidate_kind', candidateKind, candidateKind)}
                    </Badge>
                    <Badge variant="outline">
                        {translateCandidate(t, 'candidate_tier', tier, candidate.tier || notRecorded)}
                    </Badge>
                    {candidate.auditOnly && (
                        <Badge variant="light">
                            {t('mod_archive.release.candidate_audit_only')}
                        </Badge>
                    )}
                </Group>
            </Group>

            {candidate.normalizedMatchKey && (
                <Text className={styles.candidateMatchKey} size="xs">
                    {t('mod_archive.release.candidate_match_key')}: {candidate.normalizedMatchKey}
                </Text>
            )}

            <div className={styles.candidateFieldGrid}>
                <CandidateField
                    label={t('mod_archive.release.candidate_aliases')}
                    value={formatValue(candidate.aliases.join(', '), notRecorded)}
                />
            </div>

            <div className={styles.candidateMetricGrid}>
                <CandidateField
                    label={t('mod_archive.release.candidate_coverage.mention_count')}
                    value={formatValue(candidate.mentionCount, notRecorded)}
                />
                <CandidateField
                    label={t('mod_archive.release.candidate_coverage.source_item_coverage')}
                    value={formatValue(candidate.sourceItemCoverage, notRecorded)}
                />
                <CandidateField
                    label={t('mod_archive.release.candidate_coverage.local_unit_coverage')}
                    value={formatValue(candidate.localUnitCoverage, notRecorded)}
                />
                <CandidateField
                    label={t('mod_archive.release.candidate_coverage.event_chain_coverage')}
                    value={formatValue(candidate.eventChainCoverage, notRecorded)}
                />
            </div>

            {candidate.policyReasons.length > 0 && (
                <CandidateField
                    label={t('mod_archive.release.candidate_policy_reasons')}
                    value={candidate.policyReasons.join('; ')}
                />
            )}

            <Group gap="xs" mt="sm">
                {eligibility(candidate.summaryEligible) && (
                    <Badge variant="outline">
                        {t('mod_archive.release.candidate_summary_eligible')}: {eligibility(candidate.summaryEligible)}
                    </Badge>
                )}
                {eligibility(candidate.glossaryEligible) && (
                    <Badge variant="outline">
                        {t('mod_archive.release.candidate_glossary_eligible')}: {eligibility(candidate.glossaryEligible)}
                    </Badge>
                )}
            </Group>
        </Paper>
    );
};

const CandidateGroup = ({ group, candidates, t }) => {
    if (candidates.length === 0) return null;
    return (
        <section className={styles.candidateGroup} data-candidate-group={group}>
            <Group justify="space-between" mb="xs">
                <Title order={5}>{translateCandidate(t, 'candidate_group', group)}</Title>
                <Badge variant="outline">{candidates.length}</Badge>
            </Group>
            <Stack gap="xs">
                {candidates.map((candidate, index) => (
                    <CandidateCard candidate={candidate} index={index} key={`${candidate.group}-${candidate.aggregateKey}-${index}`} t={t} />
                ))}
            </Stack>
        </section>
    );
};

export const CandidateGovernanceSection = ({ rows, t }) => {
    const groups = useMemo(() => getCandidateGovernanceGroups(rows), [rows]);
    const hasCandidates = Object.values(groups).some((candidates) => candidates.length > 0);
    if (!hasCandidates) return null;

    return (
        <section className={styles.candidateGovernance} data-testid="mod-archive-candidate-governance">
            <div>
                <Title order={4}>{t('mod_archive.release.candidate_governance_title')}</Title>
                <Text className={styles.paperMuted} size="sm">
                    {t('mod_archive.release.candidate_governance_desc')}
                </Text>
            </div>
            <Stack gap="md">
                {VISIBLE_GROUPS.map((group) => (
                    <CandidateGroup
                        candidates={groups[group]}
                        group={group}
                        key={group}
                        t={t}
                    />
                ))}
                {groups.incidental.length > 0 && (
                    <details
                        className={styles.candidateAuditSection}
                        data-candidate-group="incidental"
                        data-testid="mod-archive-candidate-audit"
                    >
                        <summary className={styles.candidateAuditSummary}>
                            <span>{translateCandidate(t, 'candidate_group', 'incidental')}</span>
                            <Badge variant="outline">{groups.incidental.length}</Badge>
                        </summary>
                        <Stack gap="xs" mt="sm">
                            {groups.incidental.map((candidate, index) => (
                                <CandidateCard
                                    candidate={candidate}
                                    index={index}
                                    key={`${candidate.group}-${candidate.aggregateKey}-${index}`}
                                    t={t}
                                />
                            ))}
                        </Stack>
                    </details>
                )}
            </Stack>
        </section>
    );
};

export default CandidateGovernanceSection;
