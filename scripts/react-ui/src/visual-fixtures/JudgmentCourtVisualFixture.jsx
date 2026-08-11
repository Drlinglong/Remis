import React, { useEffect, useState } from 'react';
import { Box } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import JudgmentCaseWorkspace from '../components/neologism/JudgmentCaseWorkspace';
import JudgmentDocket from '../components/neologism/JudgmentDocket';
import ProjectGlossaryToolbar from '../components/neologism/ProjectGlossaryToolbar';
import courtStyles from '../components/neologism/JudgmentCourt.module.css';
import styles from './JudgmentCourtVisualFixture.module.css';

const sourcePath = String.raw`C:\Users\Drlin\AppData\Roaming\RemisModFactoryDev\stellaris-remis-expedition\localisation\english\events\remis_exceptionally_long_narrative_event_chain_l_english.yml`;

const candidates = [
    {
        id: 1,
        original: 'Hyperlane Resonance Cartographer',
        suggestion: '超空间航道共振测绘师',
        reasoning: '该术语反复出现在调查事件链中，指负责记录超空间航道共振模式的专业人员。',
        review_language: 'zh-CN',
        tier: 'A',
        source_file: sourcePath,
        source_lang: 'en',
        target_lang: 'zh-CN',
        context_evidence: [
            {
                snippet: 'The Hyperlane Resonance Cartographer compared the signal against the lost expedition records.',
                source_file: sourcePath,
                line: 184,
            },
            {
                snippet: 'Appoint a Hyperlane Resonance Cartographer before entering the unstable corridor.',
                source_file: String.raw`events\remis_expedition_events.txt`,
                line: 912,
            },
        ],
        duplicate_matches: [],
    },
    {
        id: 2,
        original: 'Galactic Republic',
        suggestion: '银河共和国',
        reasoning: '与现有词典中的核心政体名称相同。',
        tier: 'A',
        duplicate_matches: [{ entry_id: 31, source_term: 'Galactic Republic', glossary_name: '星港远征术语' }],
        context_evidence: [{ snippet: 'The Galactic Republic recalls the expedition.', source_file: sourcePath, line: 241 }],
    },
    { id: 3, original: 'Quiet Star Watch', suggestion: '寂星守望者', tier: 'B', context_snippets: ['The Quiet Star Watch records every transmission.'] },
    { id: 4, original: 'Signal Reliquary', suggestion: '信号圣龛', tier: 'B', context_snippets: ['Open the Signal Reliquary.'] },
    { id: 5, original: 'The Exceptionally Long Unbroken Candidate Identifier For Overflow Verification', suggestion: '用于溢出验证的超长候选术语', tier: 'C', context_snippets: ['Overflow evidence remains readable.'] },
    { id: 6, original: 'Void Beacon', suggestion: '虚空信标', tier: 'C', context_snippets: ['The Void Beacon is silent.'] },
];

const JudgmentCourtVisualFixture = ({ themeId }) => {
    const { i18n, t } = useTranslation();
    const [selectedId, setSelectedId] = useState(candidates[0].id);
    const [batchSelectedIds, setBatchSelectedIds] = useState([]);
    const [docketView, setDocketView] = useState('pending');
    const [editSuggestion, setEditSuggestion] = useState(candidates[0].suggestion);
    const selectedCandidate = candidates.find((candidate) => candidate.id === selectedId);
    const localeReady = (i18n.resolvedLanguage || i18n.language || '').toLowerCase().startsWith('zh');

    useEffect(() => {
        if (!localeReady) void i18n.changeLanguage('zh');
    }, [i18n, localeReady]);

    useEffect(() => {
        setEditSuggestion(selectedCandidate?.suggestion || '');
    }, [selectedCandidate]);

    const toggleCandidate = (candidateId) => setBatchSelectedIds((current) => (
        current.includes(candidateId)
            ? current.filter((id) => id !== candidateId)
            : [...current, candidateId]
    ));

    return (
        <Box
            className={`${styles.page} ${courtStyles.courtRoot}`}
            data-remis-surface="canvas"
            data-testid="judgment-court-visual-fixture"
            data-theme-id={themeId}
            data-visual-ready={localeReady ? 'true' : 'loading'}
        >
            <div className={courtStyles.projectToolbarSlot}>
                <ProjectGlossaryToolbar
                    projects={[{ project_id: 'remis-expedition', name: '蕾姆丝远征：失落航道与银河共和国余波' }]}
                    selectedProject="remis-expedition"
                    onSelectedProjectChange={() => {}}
                    projectGlossary={{ glossary_id: 7, game_id: 'stellaris', name: '星港远征项目词典' }}
                    onOpenGlossary={() => {}}
                    contextBadge={t('neologism_review.court.pending_terms', { count: candidates.length })}
                />
            </div>
            <div
                className={courtStyles.courtWorkspace}
                data-remis-surface="surface"
                data-testid="neologism-court-workspace-grid"
            >
                <JudgmentDocket
                    batchProcessing={false}
                    batchSelectedIds={batchSelectedIds}
                    candidates={candidates}
                    docketView={docketView}
                    loading={false}
                    onBatchConfirm={() => {}}
                    onDocketViewChange={setDocketView}
                    onSelectCandidate={setSelectedId}
                    onToggleAll={() => setBatchSelectedIds(
                        batchSelectedIds.length === candidates.length ? [] : candidates.map((candidate) => candidate.id),
                    )}
                    onToggleCandidate={toggleCandidate}
                    processing={false}
                    selectedId={selectedId}
                    t={t}
                />
                <main className={courtStyles.reviewPanel} data-remis-surface="surface">
                    <JudgmentCaseWorkspace
                        batchProcessing={false}
                        candidate={selectedCandidate}
                        docketView={docketView}
                        editSuggestion={editSuggestion}
                        evidenceItems={selectedCandidate?.context_evidence || []}
                        hasCandidates
                        loading={false}
                        onApprove={() => {}}
                        onReject={() => {}}
                        onRestore={() => {}}
                        onSelectVariant={() => {}}
                        onSuggestionChange={setEditSuggestion}
                        processing={false}
                        projectSelected
                        resolution="approve_project"
                        setResolution={() => {}}
                        t={t}
                    />
                </main>
            </div>
        </Box>
    );
};

export default JudgmentCourtVisualFixture;
