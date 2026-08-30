import { useCallback, useEffect, useMemo, useState } from 'react';
import { notifications } from '@mantine/notifications';

import api from '../../utils/api';
import { normalizeArrayPayload } from '../../utils/payload';
import { sortTermCandidates } from './termCandidatePresentation';

const API_BASE_URL = '/api';

export const useJudgmentCourtData = ({
    onSelectedProjectChange,
    refreshToken,
    selectedProject,
    t,
}) => {
    const [projects, setProjects] = useState([]);
    const [candidates, setCandidates] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [loading, setLoading] = useState(false);
    const [projectGlossary, setProjectGlossary] = useState(null);
    const [batchSelectedIds, setBatchSelectedIds] = useState([]);
    const [docketView, setDocketView] = useState('pending');

    const selectedCandidate = useMemo(
        () => candidates.find((candidate) => candidate.id === selectedId),
        [candidates, selectedId],
    );
    const currentProject = useMemo(
        () => projects.find((project) => project.project_id === selectedProject),
        [projects, selectedProject],
    );

    const fetchProjects = useCallback(async () => {
        try {
            const response = await api.get(`${API_BASE_URL}/projects`);
            const projectList = normalizeArrayPayload(
                response.data,
                ['projects', 'items', 'data', 'results'],
            );
            setProjects(projectList);
            if (!selectedProject && projectList.length > 0) {
                onSelectedProjectChange(projectList[0].project_id);
            }
        } catch (error) {
            console.error('Failed to fetch projects', error);
        }
    }, [onSelectedProjectChange, selectedProject]);

    const fetchCandidates = useCallback(async (projectId, view = 'pending') => {
        setLoading(true);
        try {
            const viewQuery = view === 'pending' ? '' : `&view=${encodeURIComponent(view)}`;
            const response = await api.get(
                `${API_BASE_URL}/neologisms?project_id=${encodeURIComponent(projectId)}${viewQuery}`,
            );
            const candidateList = normalizeArrayPayload(
                response.data,
                ['candidates', 'neologisms', 'items', 'data', 'results'],
            );
            const sortedCandidates = sortTermCandidates(candidateList);
            setCandidates(sortedCandidates);
            setSelectedId(sortedCandidates[0]?.id || null);
            setBatchSelectedIds((current) => current.filter(
                (candidateId) => candidateList.some((candidate) => candidate.id === candidateId),
            ));
        } catch {
            notifications.show({ title: 'Error', message: 'Failed to load candidates', color: 'red' });
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchProjectGlossary = useCallback(async (projectId) => {
        if (!projectId) {
            setProjectGlossary(null);
            return;
        }
        try {
            const response = await api.get(
                `${API_BASE_URL}/neologisms/project-glossary/${encodeURIComponent(projectId)}`,
            );
            setProjectGlossary(response.data);
        } catch {
            setProjectGlossary(null);
            notifications.show({
                title: t('neologism_review.common.error'),
                message: t('neologism_review.court.glossary_load_failed'),
                color: 'red',
            });
        }
    }, [t]);

    useEffect(() => {
        fetchProjects();
    }, [fetchProjects]);

    useEffect(() => {
        if (selectedProject) {
            fetchCandidates(selectedProject, docketView);
            fetchProjectGlossary(selectedProject);
        } else {
            setCandidates([]);
            setProjectGlossary(null);
        }
    }, [docketView, fetchCandidates, fetchProjectGlossary, refreshToken, selectedProject]);

    useEffect(() => {
        setBatchSelectedIds([]);
    }, [docketView, selectedProject]);

    const removeCandidates = useCallback((ids) => {
        const removedIds = new Set(ids);
        const currentIndex = candidates.findIndex((candidate) => candidate.id === selectedId);
        const newList = candidates.filter((candidate) => !removedIds.has(candidate.id));
        setBatchSelectedIds((current) => current.filter((id) => !removedIds.has(id)));
        setCandidates(newList);
        if (selectedId && !removedIds.has(selectedId)) return;
        const nextIndex = currentIndex >= 0 ? Math.min(currentIndex, newList.length - 1) : 0;
        setSelectedId(newList[nextIndex]?.id || null);
    }, [candidates, selectedId]);

    return {
        batchSelectedIds,
        candidates,
        currentProject,
        docketView,
        loading,
        projectGlossary,
        projects,
        removeCandidates,
        selectedCandidate,
        selectedId,
        setCandidates,
        setDocketView,
        setProjectGlossary,
        setSelectedId,
        toggleAllCandidates: () => setBatchSelectedIds((current) => (
            current.length === candidates.length ? [] : candidates.map((candidate) => candidate.id)
        )),
        toggleBatchCandidate: (candidateId) => setBatchSelectedIds((current) => (
            current.includes(candidateId)
                ? current.filter((id) => id !== candidateId)
                : [...current, candidateId]
        )),
        updateBatchSelectedIds: setBatchSelectedIds,
    };
};
