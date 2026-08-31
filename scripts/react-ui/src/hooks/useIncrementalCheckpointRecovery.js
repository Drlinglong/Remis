import { useEffect, useState } from 'react';

import { FEATURES } from '../config/features';
import { useTranslationRecovery } from './useTranslationRecovery';

export const useIncrementalCheckpointRecovery = (projectId) => {
    const [checkpointFound, setCheckpointFound] = useState(false);
    const [checkpointInfo, setCheckpointInfo] = useState(null);
    const [useResume, setUseResume] = useState(false);
    const [showResumeDetails, setShowResumeDetails] = useState(false);
    const translationRecovery = useTranslationRecovery(projectId, {
        autoLoad: FEATURES.ENABLE_CHECKPOINT_RESUME,
    });

    useEffect(() => {
        if (!FEATURES.ENABLE_CHECKPOINT_RESUME) {
            setCheckpointFound(false);
            setCheckpointInfo(null);
            setUseResume(false);
            setShowResumeDetails(false);
            return;
        }
        const recovery = translationRecovery.recovery;
        if (translationRecovery.canResume && recovery) {
            setCheckpointFound(true);
            setCheckpointInfo(recovery);
            return;
        }
        setCheckpointFound(false);
        setCheckpointInfo(null);
        setUseResume(false);
    }, [translationRecovery.canResume, translationRecovery.recovery]);

    return {
        checkpointFound,
        checkpointInfo,
        effectiveUseResume: FEATURES.ENABLE_CHECKPOINT_RESUME && useResume,
        setCheckpointFound,
        setCheckpointInfo,
        setShowResumeDetails,
        setUseResume,
        showResumeDetails,
        useResume,
    };
};

export default useIncrementalCheckpointRecovery;
