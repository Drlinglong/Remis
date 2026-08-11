import React from 'react';
import { Box } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import JudgmentCaseWorkspace from './JudgmentCaseWorkspace';
import JudgmentCourtBatchModals from './JudgmentCourtBatchModals';
import JudgmentDocket from './JudgmentDocket';
import ProjectGlossaryToolbar from './ProjectGlossaryToolbar';
import { useJudgmentCourtController } from './useJudgmentCourtController';
import styles from './JudgmentCourt.module.css';

const JudgmentCourt = ({
    selectedProject,
    onSelectedProjectChange,
    refreshToken = 0,
    onOpenMining,
    onOpenGlossary,
}) => {
    const { t } = useTranslation();
    const controller = useJudgmentCourtController({
        onSelectedProjectChange,
        refreshToken,
        selectedProject,
        t,
    });

    const handleOpenProjectGlossary = () => {
        if (!controller.projectGlossary?.glossary_id || !onOpenGlossary) return;
        onOpenGlossary({
            glossaryId: controller.projectGlossary.glossary_id,
            gameId: controller.projectGlossary.game_id || controller.currentProject?.game_id,
        });
    };

    const batchConfirmHandlers = {
        approve: controller.handleBatchApprove,
        reject: controller.handleBatchReject,
        restore: controller.handleBatchRestore,
    };

    return (
        <Box
            data-testid="judgment-court"
            data-remis-surface="canvas"
            className={styles.courtRoot}
        >
            <JudgmentCourtBatchModals
                count={controller.batchSelectedIds.length}
                onClose={() => controller.setBatchConfirmOpen(null)}
                onConfirm={batchConfirmHandlers[controller.batchConfirmOpen]}
                opened={controller.batchConfirmOpen}
                processing={controller.batchProcessing}
                t={t}
            />

            <div className={styles.projectToolbarSlot}>
                <ProjectGlossaryToolbar
                    projects={controller.projects}
                    selectedProject={selectedProject}
                    onSelectedProjectChange={onSelectedProjectChange}
                    projectGlossary={controller.projectGlossary}
                    onOpenGlossary={handleOpenProjectGlossary}
                    contextBadge={controller.currentProject ? t(
                        controller.docketView === 'pending'
                            ? 'neologism_review.court.pending_terms'
                            : 'neologism_review.court.processed_terms',
                        { count: controller.candidates.length },
                    ) : null}
                />
            </div>

            <div
                className={styles.courtWorkspace}
                data-remis-surface="surface"
                data-testid="neologism-court-workspace-grid"
            >
                <JudgmentDocket
                    batchProcessing={controller.batchProcessing}
                    batchSelectedIds={controller.batchSelectedIds}
                    candidates={controller.candidates}
                    docketView={controller.docketView}
                    loading={controller.loading}
                    onBatchConfirm={controller.setBatchConfirmOpen}
                    onDocketViewChange={controller.setDocketView}
                    onSelectCandidate={controller.setSelectedId}
                    onToggleAll={controller.toggleAllCandidates}
                    onToggleCandidate={controller.toggleBatchCandidate}
                    processing={controller.processing}
                    selectedId={controller.selectedId}
                    t={t}
                />
                <main className={styles.reviewPanel} data-remis-surface="surface">
                    <JudgmentCaseWorkspace
                        batchProcessing={controller.batchProcessing}
                        candidate={controller.selectedCandidate}
                        docketView={controller.docketView}
                        editSuggestion={controller.editSuggestion}
                        evidenceItems={controller.selectedEvidence}
                        hasCandidates={controller.candidates.length > 0}
                        loading={controller.loading}
                        onApprove={controller.handleApprove}
                        onOpenMining={onOpenMining}
                        onReject={controller.handleReject}
                        onRestore={controller.handleRestore}
                        onSelectVariant={controller.handleSelectVariant}
                        onSuggestionChange={controller.updateEditSuggestion}
                        processing={controller.processing}
                        projectSelected={Boolean(selectedProject)}
                        resolution={controller.resolution}
                        setResolution={controller.setResolution}
                        t={t}
                    />
                </main>
            </div>
        </Box>
    );
};

export default JudgmentCourt;
