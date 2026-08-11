import React, { useCallback, useEffect, useState } from 'react';
import { notifications } from '@mantine/notifications';
import { IconAlertTriangle, IconCheck, IconRestore, IconX } from '@tabler/icons-react';

import api from '../../utils/api';
import { useTermVariantSelection } from './useTermVariantSelection';
import {
    candidateDraftKey,
    candidateEvidence,
    partitionSettledCandidateIds,
    settleWithConcurrency,
} from './judgmentCourtWorkflow';

const API_BASE_URL = '/api';
const notificationIcon = (Icon) => React.createElement(Icon, { size: 18 });

const notifyBatchResult = ({ action, failedIds, succeededIds, t }) => {
    const partial = failedIds.length > 0;
    const config = {
        approve: { complete: 'approved', color: 'green', icon: IconCheck },
        reject: { complete: 'rejected', color: 'gray', icon: IconX },
        restore: { complete: 'restored', color: 'blue', icon: IconRestore },
    }[action];
    notifications.show({
        title: t(partial
            ? 'neologism_review.court.batch_partial_title'
            : `neologism_review.court.batch_${config.complete}_title`),
        message: t(partial
            ? 'neologism_review.court.batch_partial_message'
            : `neologism_review.court.batch_${config.complete}_message`, {
            succeeded: succeededIds.length,
            failed: failedIds.length,
            count: succeededIds.length,
        }),
        color: partial ? (succeededIds.length > 0 ? 'orange' : 'red') : config.color,
        icon: notificationIcon(partial ? IconAlertTriangle : config.icon),
        withBorder: true,
        autoClose: partial ? 6000 : 4000,
    });
};

export const useJudgmentCourtWorkflow = ({
    batchSelectedIds,
    candidates,
    currentProject,
    docketView,
    projectGlossary,
    removeCandidates,
    selectedCandidate,
    selectedProject,
    setCandidates,
    setProjectGlossary,
    t,
    updateBatchSelectedIds,
}) => {
    const [processing, setProcessing] = useState(false);
    const [batchProcessing, setBatchProcessing] = useState(false);
    const [batchConfirmOpen, setBatchConfirmOpen] = useState(null);
    const [draftSuggestions, setDraftSuggestions] = useState({});
    const [resolution, setResolution] = useState('approve_project');
    const selectedDraftKey = selectedCandidate
        ? candidateDraftKey(selectedProject, selectedCandidate.id)
        : null;
    const editSuggestion = selectedCandidate
        ? (Object.prototype.hasOwnProperty.call(draftSuggestions, selectedDraftKey)
            ? draftSuggestions[selectedDraftKey]
            : selectedCandidate.suggestion || '')
        : '';

    useEffect(() => {
        if (!selectedCandidate) return;
        setResolution((selectedCandidate.duplicate_matches || []).length > 0
            ? 'duplicate'
            : 'approve_project');
    }, [selectedCandidate]);

    useEffect(() => {
        setBatchConfirmOpen(null);
    }, [docketView, selectedProject]);

    const removeCompletedCandidates = useCallback((ids) => {
        const removedIds = new Set(ids);
        setDraftSuggestions((current) => {
            const next = { ...current };
            removedIds.forEach((id) => delete next[candidateDraftKey(selectedProject, id)]);
            return next;
        });
        removeCandidates(ids);
    }, [removeCandidates, selectedProject]);

    const updateEditSuggestion = useCallback((value) => {
        if (!selectedDraftKey) return;
        setDraftSuggestions((current) => ({ ...current, [selectedDraftKey]: value }));
    }, [selectedDraftKey]);

    const handleSelectVariant = useTermVariantSelection({
        candidate: selectedCandidate,
        projectId: selectedProject,
        setCandidates,
        setProcessing,
        updateEditSuggestion,
        t,
    });

    const handleApprove = async () => {
        if (!selectedCandidate || !selectedProject) return;
        setProcessing(true);
        try {
            const response = await api.post(
                `${API_BASE_URL}/neologisms/${selectedCandidate.id}/approve`,
                {
                    project_id: selectedProject,
                    resolution,
                    final_translation: editSuggestion,
                    glossary_id: projectGlossary?.glossary_id || null,
                    source_lang: selectedCandidate.source_lang || currentProject?.source_language || 'en',
                    target_lang: selectedCandidate.target_lang || 'zh-CN',
                },
            );
            const confirmedGlossary = response.data?.glossary || projectGlossary;
            if (response.data?.glossary) setProjectGlossary(response.data.glossary);
            const duplicate = resolution === 'duplicate';
            notifications.show({
                title: t(duplicate
                    ? 'neologism_review.court.duplicate_confirmed_title'
                    : 'neologism_review.court.approved_title'),
                message: t(duplicate
                    ? 'neologism_review.court.duplicate_confirmed_message'
                    : 'neologism_review.court.approved_message', {
                    term: selectedCandidate.original,
                    glossary: confirmedGlossary?.name || t('neologism_review.court.project_glossary'),
                }),
                color: duplicate ? 'blue' : 'green',
                icon: notificationIcon(IconCheck),
                withBorder: true,
                autoClose: 3200,
            });
            removeCompletedCandidates([selectedCandidate.id]);
        } catch {
            notifications.show({
                title: t('neologism_review.common.error'),
                message: t('neologism_review.court.approve_failed'),
                color: 'red',
            });
        } finally {
            setProcessing(false);
        }
    };

    const runSingleAction = async ({ action, successMessage, successTitle }) => {
        if (!selectedCandidate || !selectedProject) return;
        setProcessing(true);
        try {
            const response = await api.post(
                `${API_BASE_URL}/neologisms/${selectedCandidate.id}/${action}`,
                { project_id: selectedProject },
            );
            const preserved = action === 'restore' && response.data?.glossary_entry_preserved;
            notifications.show({
                title: t(successTitle),
                message: t(preserved
                    ? 'neologism_review.court.restored_glossary_preserved'
                    : successMessage, { term: selectedCandidate.original }),
                color: action === 'reject' ? 'gray' : 'blue',
                icon: notificationIcon(action === 'reject' ? IconX : IconRestore),
                withBorder: true,
                autoClose: action === 'reject' ? 3200 : 4200,
            });
            removeCompletedCandidates([selectedCandidate.id]);
        } catch {
            notifications.show({
                title: t('neologism_review.common.error'),
                message: t(`neologism_review.court.${action}_failed`),
                color: 'red',
            });
        } finally {
            setProcessing(false);
        }
    };

    const candidateDraft = (candidate) => {
        const key = candidateDraftKey(selectedProject, candidate.id);
        return Object.prototype.hasOwnProperty.call(draftSuggestions, key)
            ? draftSuggestions[key]
            : candidate.suggestion || '';
    };

    const runBatch = async (action) => {
        if (!selectedProject || batchSelectedIds.length === 0) return;
        const selectedCandidates = candidates.filter(
            (candidate) => batchSelectedIds.includes(candidate.id),
        );
        if (selectedCandidates.length === 0) {
            setBatchConfirmOpen(null);
            return;
        }
        setBatchProcessing(true);
        const results = await settleWithConcurrency(selectedCandidates, (candidate) => {
            if (action !== 'approve') {
                return api.post(`${API_BASE_URL}/neologisms/${candidate.id}/${action}`, {
                    project_id: selectedProject,
                });
            }
            const duplicate = (candidate.duplicate_matches || []).length > 0;
            const finalTranslation = candidateDraft(candidate).trim();
            if (!duplicate && !finalTranslation) throw new Error('Candidate has no suggested translation');
            return api.post(`${API_BASE_URL}/neologisms/${candidate.id}/approve`, {
                project_id: selectedProject,
                resolution: duplicate ? 'duplicate' : 'approve_project',
                final_translation: finalTranslation,
                glossary_id: projectGlossary?.glossary_id || null,
                source_lang: candidate.source_lang || currentProject?.source_language || 'en',
                target_lang: candidate.target_lang || 'zh-CN',
            });
        });
        if (action === 'approve') {
            results.forEach((result) => {
                if (result.status === 'fulfilled' && result.value?.data?.glossary) {
                    setProjectGlossary(result.value.data.glossary);
                }
            });
        }
        const { succeededIds, failedIds } = partitionSettledCandidateIds(selectedCandidates, results);
        if (succeededIds.length > 0) removeCompletedCandidates(succeededIds);
        updateBatchSelectedIds(failedIds);
        setBatchConfirmOpen(null);
        setBatchProcessing(false);
        notifyBatchResult({ action, failedIds, succeededIds, t });
    };

    return {
        batchConfirmOpen,
        batchProcessing,
        editSuggestion,
        handleApprove,
        handleBatchApprove: () => runBatch('approve'),
        handleBatchReject: () => runBatch('reject'),
        handleBatchRestore: () => runBatch('restore'),
        handleReject: () => runSingleAction({
            action: 'reject',
            successMessage: 'neologism_review.court.rejected_message',
            successTitle: 'neologism_review.court.rejected_title',
        }),
        handleRestore: () => runSingleAction({
            action: 'restore',
            successMessage: 'neologism_review.court.restored_message',
            successTitle: 'neologism_review.court.restored_title',
        }),
        handleSelectVariant,
        processing,
        resolution,
        selectedEvidence: candidateEvidence(selectedCandidate),
        setBatchConfirmOpen,
        setResolution,
        updateEditSuggestion,
    };
};
