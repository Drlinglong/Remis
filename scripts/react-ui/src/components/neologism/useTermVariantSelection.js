import { useCallback } from 'react';
import { notifications } from '@mantine/notifications';

import api from '../../utils/api';

export const useTermVariantSelection = ({
    candidate,
    projectId,
    setCandidates,
    setProcessing,
    updateEditSuggestion,
    t,
}) => useCallback(async (variant) => {
    if (!candidate || !projectId || !variant?.variant_id) return;
    setProcessing(true);
    try {
        await api.patch(`/api/neologisms/${candidate.id}`, {
            project_id: projectId,
            variant_id: variant.variant_id,
        });
        setCandidates((current) => current.map((item) => (
            item.id === candidate.id
                ? {
                    ...item,
                    suggestion: variant.suggestion || '',
                    reasoning: variant.reasoning || '',
                }
                : item
        )));
        updateEditSuggestion(variant.suggestion || '');
    } catch {
        notifications.show({
            title: t('neologism_review.common.error'),
            message: t('neologism_review.court.variant_select_failed', {
                defaultValue: 'Failed to select this AI variant.',
            }),
            color: 'red',
        });
    } finally {
        setProcessing(false);
    }
}, [candidate, projectId, setCandidates, setProcessing, t, updateEditSuggestion]);

export default useTermVariantSelection;
