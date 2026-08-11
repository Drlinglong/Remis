import { useJudgmentCourtData } from './useJudgmentCourtData';
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

    return { ...data, ...workflow };
};
