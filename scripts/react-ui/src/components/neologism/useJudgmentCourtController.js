import { useJudgmentCourtData } from './useJudgmentCourtData';
import { useJudgmentCourtPresentation } from './useJudgmentCourtPresentation';
import { useJudgmentCourtWorkflow } from './useJudgmentCourtWorkflow';

export const useJudgmentCourtController = ({
    onSelectedProjectChange,
    refreshToken,
    selectedProject,
    t,
}) => {
    const data = useJudgmentCourtData({
        onSelectedProjectChange,
        refreshToken,
        selectedProject,
        t,
    });
    const presentation = useJudgmentCourtPresentation({
        batchSelectedIds: data.batchSelectedIds,
        candidates: data.candidates,
        onSelectCandidate: data.setSelectedId,
        selectedId: data.selectedId,
        updateBatchSelectedIds: data.updateBatchSelectedIds,
    });
    const workflow = useJudgmentCourtWorkflow({
        batchSelectedIds: data.batchSelectedIds,
        candidates: data.candidates,
        currentProject: data.currentProject,
        docketView: data.docketView,
        projectGlossary: data.projectGlossary,
        removeCandidates: data.removeCandidates,
        selectedCandidate: data.selectedCandidate,
        selectedProject,
        setCandidates: data.setCandidates,
        setProjectGlossary: data.setProjectGlossary,
        t,
        updateBatchSelectedIds: data.updateBatchSelectedIds,
    });

    return { ...data, ...workflow, ...presentation };
};
