import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../utils/api';
import { groupFiles as performGrouping } from '../utils/fileGrouping';
import { usePersistentState } from './usePersistentState';

/**
 * Hook for managing project and file navigation in the Proofreading page.
 * Handles project selection, file list grouping, and URL sync.
 */
export const useFileNavigation = () => {
    const [searchParams, setSearchParams] = useSearchParams();

    // ==================== States ====================
    const [projects, setProjects] = useState([]);
    const [selectedProject, setSelectedProject] = useState(null);
    const [projectFilter, setProjectFilter] = usePersistentState('proofread_project_filter', '');

    const [sourceFiles, setSourceFiles] = useState([]);
    const [targetFilesMap, setTargetFilesMap] = useState({});
    const [currentSourceFile, setCurrentSourceFile] = useState(null);
    const [currentTargetFile, setCurrentTargetFile] = useState(null);

    // ==================== Actions ====================
    const fetchProjects = useCallback(async () => {
        try {
            const res = await api.get('/api/projects?status=active');
            setProjects(res.data);
        } catch (error) {
            console.error("Failed to load projects", error);
        }
    }, []);

    const groupFiles = useCallback((files, project) => {
        if (!project) return;
        const { sources, targetsMap } = performGrouping(files, project);
        setSourceFiles(sources);
        setTargetFilesMap(targetsMap);
    }, []);

    const fetchProjectFiles = useCallback(async (projectId, project) => {
        try {
            const res = await api.get(`/api/project/${projectId}/files`);
            if (res.data) {
                groupFiles(res.data, project);
            }
        } catch (error) {
            console.error("Failed to load project files", error);
        }
    }, [groupFiles]);

    const handleProjectSelect = useCallback((val) => {
        const proj = projects.find(p => p.project_id === val);
        if (proj) {
            setSelectedProject(proj);
            setSearchParams({ projectId: proj.project_id });
        }
    }, [projects, setSearchParams]);

    const handleSourceFileChange = useCallback((val) => {
        const source = sourceFiles.find(s => s.file_id === val);
        if (source) {
            setCurrentSourceFile(source);
            const targets = targetFilesMap[source.file_id];
            if (targets && targets.length > 0) {
                setCurrentTargetFile(targets[0]);
                setSearchParams({ projectId: selectedProject.project_id, fileId: targets[0].file_id });
            } else {
                setCurrentTargetFile(null);
                setSearchParams({ projectId: selectedProject.project_id, fileId: source.file_id });
            }
        }
    }, [sourceFiles, targetFilesMap, selectedProject, setSearchParams]);

    const handleTargetFileChange = useCallback((val) => {
        if (!currentSourceFile) return;
        const targets = targetFilesMap[currentSourceFile.file_id];
        const target = targets.find(t => t.file_id === val);
        if (target) {
            setCurrentTargetFile(target);
            setSearchParams({ projectId: selectedProject.project_id, fileId: target.file_id });
        }
    }, [currentSourceFile, targetFilesMap, selectedProject, setSearchParams]);

    // ==================== Effects ====================
    // Initialize: Fetch projects
    useEffect(() => {
        fetchProjects();
    }, [fetchProjects]);

    // URL Sync - Project
    useEffect(() => {
        const pId = searchParams.get('projectId');
        if (pId && projects.length > 0 && !selectedProject) {
            const proj = projects.find(p => p.project_id === pId);
            if (proj) setSelectedProject(proj);
        }
    }, [searchParams, projects, selectedProject]);

    // Fetch files when project changes
    useEffect(() => {
        if (selectedProject) {
            fetchProjectFiles(selectedProject.project_id, selectedProject);
        }
    }, [selectedProject, fetchProjectFiles]);

    // URL Sync - File (Enforce URL source of truth)
    useEffect(() => {
        if (sourceFiles.length > 0 && selectedProject) {
            const urlFileId = searchParams.get('fileId');

            let resolvedSource = null;
            let resolvedTarget = null;

            if (urlFileId) {
                resolvedSource = sourceFiles.find(s => String(s.file_id) === String(urlFileId));
                if (resolvedSource) {
                    if (targetFilesMap[resolvedSource.file_id]?.length > 0) {
                        resolvedTarget = targetFilesMap[resolvedSource.file_id][0];
                    }
                } else {
                    for (const sId in targetFilesMap) {
                        const foundT = targetFilesMap[sId].find(t => String(t.file_id) === String(urlFileId));
                        if (foundT) {
                            resolvedSource = sourceFiles.find(s => String(s.file_id) === sId);
                            resolvedTarget = foundT;
                            break;
                        }
                    }
                }
            }

            if (!resolvedSource) {
                resolvedSource = sourceFiles[0];
                if (targetFilesMap[resolvedSource.file_id]?.length > 0) {
                    resolvedTarget = targetFilesMap[resolvedSource.file_id][0];
                }
            }

            if (resolvedSource) {
                const isMismatch = !currentSourceFile ||
                    String(currentSourceFile.file_id) !== String(resolvedSource.file_id) ||
                    (resolvedTarget && (!currentTargetFile || String(currentTargetFile.file_id) !== String(resolvedTarget.file_id)));

                if (isMismatch) {
                    setCurrentSourceFile(resolvedSource);
                    setCurrentTargetFile(resolvedTarget);

                    const targetId = resolvedTarget ? resolvedTarget.file_id : resolvedSource.file_id;
                    if (String(urlFileId) !== String(targetId)) {
                        setSearchParams({ projectId: selectedProject.project_id, fileId: targetId }, { replace: true });
                    }
                }
            }
        }
    }, [searchParams, sourceFiles, targetFilesMap, selectedProject, currentSourceFile, currentTargetFile, setSearchParams]);

    return {
        projects,
        selectedProject,
        setSelectedProject,
        projectFilter,
        setProjectFilter,
        sourceFiles,
        targetFilesMap,
        currentSourceFile,
        currentTargetFile,
        setCurrentSourceFile,
        setCurrentTargetFile,
        handleProjectSelect,
        handleSourceFileChange,
        handleTargetFileChange,
        searchParams,
        setSearchParams
    };
};

