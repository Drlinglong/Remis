import { useEffect, useMemo, useState } from 'react';

import api from '../../utils/api';
import { normalizeGlossaryContentPayload } from '../../utils/glossaryPayload';
import { normalizeArrayPayload } from '../../utils/payload';
import { buildTerminologyIndex } from './modArchiveModel';

const PAGE_SIZE = 250;

const loadGlossaryEntries = async (glossaryId) => {
    if (!glossaryId) return [];
    const entries = [];
    let page = 1;
    let totalCount = 0;
    do {
        const previousLength = entries.length;
        const response = await api.get(
            `/api/glossary/content?glossary_id=${encodeURIComponent(glossaryId)}&page=${page}&pageSize=${PAGE_SIZE}`,
        );
        const content = normalizeGlossaryContentPayload(response.data);
        entries.push(...content.entries);
        totalCount = content.totalCount;
        page += 1;
        if (entries.length === previousLength) break;
    } while (entries.length < totalCount);
    return entries;
};

export const useArchiveProjectContext = ({
    selectedProject,
    onSelectedProjectChange,
    targetLanguage,
}) => {
    const [projects, setProjects] = useState([]);
    const [projectGlossary, setProjectGlossary] = useState(null);
    const [glossaryEntries, setGlossaryEntries] = useState([]);
    const [candidates, setCandidates] = useState([]);

    useEffect(() => {
        let cancelled = false;
        const loadProjects = async () => {
            try {
                const response = await api.get('/api/projects');
                if (cancelled) return;
                const nextProjects = normalizeArrayPayload(
                    response.data,
                    ['projects', 'items', 'data', 'results'],
                );
                setProjects(nextProjects);
                if (!selectedProject && nextProjects.length > 0) {
                    onSelectedProjectChange?.(nextProjects[0].project_id);
                }
            } catch {
                if (!cancelled) setProjects([]);
            }
        };
        loadProjects();
        return () => { cancelled = true; };
    }, [onSelectedProjectChange, selectedProject]);

    useEffect(() => {
        let cancelled = false;
        setProjectGlossary(null);
        setGlossaryEntries([]);
        setCandidates([]);
        if (!selectedProject) return () => { cancelled = true; };

        const load = async () => {
            const request = (url) => Promise.resolve().then(() => api.get(url));
            const [glossaryResult, candidateResult] = await Promise.allSettled([
                request(`/api/neologisms/project-glossary/${encodeURIComponent(selectedProject)}`),
                request(`/api/neologisms?project_id=${encodeURIComponent(selectedProject)}`),
            ]);
            if (cancelled) return;
            const glossary = glossaryResult.status === 'fulfilled'
                ? glossaryResult.value.data
                : null;
            setProjectGlossary(glossary);
            setCandidates(candidateResult.status === 'fulfilled'
                ? normalizeArrayPayload(candidateResult.value.data, ['candidates', 'items', 'data', 'results'])
                : []);
            if (glossary?.glossary_id) {
                try {
                    const entries = await loadGlossaryEntries(glossary.glossary_id);
                    if (!cancelled) setGlossaryEntries(entries);
                } catch {
                    if (!cancelled) setGlossaryEntries([]);
                }
            }
        };
        load();
        return () => { cancelled = true; };
    }, [selectedProject]);

    const terminologyIndex = useMemo(() => buildTerminologyIndex({
        glossaryEntries,
        candidates,
        targetLanguage,
    }), [candidates, glossaryEntries, targetLanguage]);
    const currentProject = projects.find((project) => project.project_id === selectedProject) || null;

    return { projects, currentProject, projectGlossary, terminologyIndex };
};
