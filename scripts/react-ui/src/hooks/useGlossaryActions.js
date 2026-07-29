import { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation } from 'react-router';
import { notifications } from '@mantine/notifications';
import { useTranslation } from 'react-i18next';
import { usePersistentState } from './usePersistentState';
import api from '../utils/api';
import {
    EMPTY_GLOSSARY_OVERVIEW,
    normalizeGlossaryContentPayload,
    normalizeGlossaryOverviewPayload,
    normalizeGlossaryProjectsPayload,
    normalizeGlossaryTaskHistoryPayload,
    normalizeGlossaryTreePayload,
} from '../utils/glossaryPayload';
import { isGlossaryTaskActive, pollGlossaryTask } from './glossaryTaskMonitor';

const localizeHealthTaskError = (t, message = '') => (
    /no models loaded/i.test(message)
        ? t('glossary_health_no_model_loaded')
        : t('glossary_health_model_request_failed')
);

/**
 * 词典管理的数据和操作 Hook
 * 集中管理 API 调用、状态管理和事件处理
 */
const useGlossaryActions = () => {
    const location = useLocation();
    const { t } = useTranslation();
    const translationRef = useRef(t);
    translationRef.current = t;
    const translate = useCallback(
        (key, options) => translationRef.current(key, options),
        []
    );
    // ==================== 状态 ====================
    const [treeData, setTreeData] = useState([]);
    const [overview, setOverview] = useState(EMPTY_GLOSSARY_OVERVIEW);
    const [viewMode, setViewMode] = useState('overview');
    const [data, setData] = useState([]);
    const [selectedGame, setSelectedGame] = usePersistentState('glossary_selected_game', null);
    const [selectedFile, setSelectedFile] = usePersistentState('glossary_selected_file', {
        key: null,
        title: 'No file selected',
        gameId: null,
        glossaryId: null
    });
    const [targetLanguages, setTargetLanguages] = useState([]);
    const [apiProviders, setApiProviders] = useState([]);
    const [projects, setProjects] = useState([]);
    const [glossaryOperation, setGlossaryOperation] = usePersistentState(
        'glossary_active_operation',
        null
    );
    const [selectedTargetLang, setSelectedTargetLang] = usePersistentState('glossary_target_lang', '');
    const [searchScope, setSearchScope] = usePersistentState('glossary_search_scope', 'file');
    const [filtering, setFiltering] = usePersistentState('glossary_filtering', '');
    const [pagination, setPagination] = usePersistentState('glossary_pagination', { pageIndex: 0, pageSize: 25 });
    const [rowCount, setRowCount] = useState(0);
    const [focusedEntry, setFocusedEntry] = useState(null);

    const [isLoadingTree, setIsLoadingTree] = useState(true);
    const [isLoadingOverview, setIsLoadingOverview] = useState(true);
    const [isLoadingContent, setIsLoadingContent] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const selectedGameRef = useRef(selectedGame);
    const selectedTargetLangRef = useRef(selectedTargetLang);
    const setSelectedGameRef = useRef(setSelectedGame);
    const setSelectedTargetLangRef = useRef(setSelectedTargetLang);
    const appliedDeepLinkRef = useRef(null);

    selectedGameRef.current = selectedGame;
    selectedTargetLangRef.current = selectedTargetLang;
    setSelectedGameRef.current = setSelectedGame;
    setSelectedTargetLangRef.current = setSelectedTargetLang;

    // ==================== 初始化数据获取 ====================
    useEffect(() => {
        const fetchInitialConfigs = async () => {
            setIsLoadingTree(true);
            try {
                const [treeResponse, configResponse, overviewResponse, projectsResponse] = await Promise.all([
                    api.get('/api/glossary/tree'),
                    api.get('/api/config'),
                    api.get('/api/glossaries/overview'),
                    api.get('/api/projects').catch(() => ({ data: [] })),
                ]);

                const normalizedTree = normalizeGlossaryTreePayload(treeResponse.data);
                setTreeData(normalizedTree);
                setOverview(normalizeGlossaryOverviewPayload(overviewResponse.data));
                setProjects(normalizeGlossaryProjectsPayload(projectsResponse.data));
                if (normalizedTree.length > 0 && !selectedGameRef.current) {
                    setSelectedGameRef.current(normalizedTree[0].key);
                }

                const languages = Object.values(configResponse.data.languages);
                setTargetLanguages(languages);
                setApiProviders(configResponse.data.api_providers || []);
                if (languages.length > 0 && !selectedTargetLangRef.current) {
                    setSelectedTargetLangRef.current(
                        languages.find(l => l.code === 'zh-CN')?.code || languages[0].code
                    );
                }
            } catch {
                notifications.show({
                    title: 'Error',
                    message: 'Failed to load initial configuration.',
                    color: 'red'
                });
            } finally {
                setIsLoadingTree(false);
                setIsLoadingOverview(false);
            }
        };

        fetchInitialConfigs();
    }, []);

    useEffect(() => {
        if (!treeData.length || appliedDeepLinkRef.current === location.search) {
            return;
        }

        const params = new URLSearchParams(location.search);
        const requestedGameId = params.get('game_id');
        const glossaryId = params.get('glossary_id');
        const focusEntryId = params.get('focus_entry_id');
        const targetLang = params.get('target_lang');
        if (!glossaryId) {
            return;
        }

        const gameNode = requestedGameId
            ? treeData.find((node) => node.key === requestedGameId)
            : treeData.find((node) => node.children?.some((child) => child.key.split('|')[1] === glossaryId));
        const glossaryNode = gameNode?.children?.find((node) => {
            const [, nodeGlossaryId] = node.key.split('|');
            return nodeGlossaryId === glossaryId;
        });
        if (!glossaryNode) {
            return;
        }

        const [, parsedGlossaryId, fileName] = glossaryNode.key.split('|');
        const gameId = gameNode.key;
        setSelectedGame(gameId);
        setSelectedFile({
            key: glossaryNode.key,
            title: fileName,
            gameId,
            glossaryId: parseInt(parsedGlossaryId, 10),
        });
        setSearchScope('file');
        setFiltering('');
        if (targetLang) setSelectedTargetLangRef.current(targetLang);
        setPagination({ pageIndex: 0, pageSize: 25 });
        setViewMode('editor');
        appliedDeepLinkRef.current = location.search;

        setFocusedEntry(null);
        if (focusEntryId) {
            let active = true;
            api.post('/api/glossary/search', {
                scope: 'file',
                query: focusEntryId,
                page: 1,
                pageSize: 25,
                game_id: null,
                file_name: glossaryNode.key,
            }).then((response) => {
                if (!active) return;
                const entry = normalizeGlossaryContentPayload(response.data).entries
                    .find((candidate) => candidate.id === focusEntryId);
                setFocusedEntry(entry || null);
            }).catch(() => {
                if (!active) return;
                notifications.show({
                    title: translate('neologism_review.common.error', { defaultValue: 'Error' }),
                    message: translate(
                        'glossary_health_entry_load_failed',
                        { defaultValue: 'Could not load the requested glossary entry.' }
                    ),
                    color: 'red',
                });
            });
            return () => { active = false; };
        }
    }, [
        location.search,
        setFiltering,
        setPagination,
        setSearchScope,
        setSelectedGame,
        setSelectedFile,
        translate,
        treeData,
    ]);

    // ==================== 词典内容获取 ====================
    const fetchGlossaryContent = useCallback(async () => {
        if (viewMode !== 'editor') {
            setIsLoadingContent(false);
            return;
        }

        const { pageIndex, pageSize } = pagination;
        setIsLoadingContent(true);

        try {
            let response;

            if (searchScope === 'file' && !filtering) {
                if (!selectedFile.glossaryId) {
                    setData([]);
                    setRowCount(0);
                    setIsLoadingContent(false);
                    return;
                }
                response = await api.get(
                    `/api/glossary/content?glossary_id=${selectedFile.glossaryId}&page=${pageIndex + 1}&pageSize=${pageSize}`
                );
            } else {
                const payload = {
                    scope: searchScope,
                    query: filtering,
                    page: pageIndex + 1,
                    pageSize: pageSize,
                    game_id: searchScope === 'game' ? (selectedFile.gameId || selectedGame) : null,
                    file_name: searchScope === 'file' ? selectedFile.key : null,
                };

                if ((payload.scope === 'file' && !payload.file_name) ||
                    (payload.scope === 'game' && !payload.game_id)) {
                    setData([]);
                    setRowCount(0);
                    setIsLoadingContent(false);
                    return;
                }

                response = await api.post('/api/glossary/search', payload);
            }

            const normalizedContent = normalizeGlossaryContentPayload(response.data);
            setData(normalizedContent.entries);
            setRowCount(normalizedContent.totalCount);
        } catch {
            notifications.show({
                title: 'Error',
                message: 'Failed to load content.',
                color: 'red'
            });
            setData([]);
            setRowCount(0);
        } finally {
            setIsLoadingContent(false);
        }
    }, [filtering, pagination, searchScope, selectedFile, selectedGame, viewMode]);

    useEffect(() => {
        fetchGlossaryContent();
    }, [fetchGlossaryContent]);

    // ==================== 事件处理器 ====================
    const refreshGlossaryOverview = useCallback(async () => {
        setIsLoadingOverview(true);
        try {
            const response = await api.get('/api/glossaries/overview');
            setOverview(normalizeGlossaryOverviewPayload(response.data));
            return true;
        } catch {
            notifications.show({
                title: 'Refresh failed',
                message: 'The glossary change was saved, but the overview could not be refreshed.',
                color: 'orange'
            });
            return false;
        } finally {
            setIsLoadingOverview(false);
        }
    }, []);

    const refreshGlossaryIndex = useCallback(async () => {
        setIsLoadingTree(true);
        setIsLoadingOverview(true);
        try {
            const [treeResponse, overviewResponse] = await Promise.all([
                api.get('/api/glossary/tree'),
                api.get('/api/glossaries/overview'),
            ]);
            setTreeData(normalizeGlossaryTreePayload(treeResponse.data));
            setOverview(normalizeGlossaryOverviewPayload(overviewResponse.data));
            return true;
        } catch {
            notifications.show({
                title: 'Refresh failed',
                message: 'The glossary change was saved, but the glossary list could not be refreshed.',
                color: 'orange'
            });
            return false;
        } finally {
            setIsLoadingTree(false);
            setIsLoadingOverview(false);
        }
    }, []);

    const monitorGlossaryTask = useCallback(async (taskId, kind, isCancelled) => {
        try {
            const task = await pollGlossaryTask({
                taskId,
                getTask: async (currentTaskId) => {
                    const response = await api.get(`/api/tasks/${currentTaskId}`);
                    return response.data;
                },
                onTask: (nextTask) => {
                    setGlossaryOperation((current) => (
                        current?.taskId === taskId
                            ? { ...current, status: nextTask.status, task: nextTask }
                            : current
                    ));
                },
                isCancelled,
            });

            if (!task) {
                if (!isCancelled()) {
                    notifications.show({
                        title: 'Task is still running',
                        message: 'Follow its progress in the task center.',
                        color: 'blue',
                    });
                }
                return null;
            }

            if (task.status === 'completed') {
                if (kind === 'merge') await refreshGlossaryIndex();
                if (isCancelled()) return task;
                const healthReport = task.result?.metadata || {};
                notifications.show({
                    title: kind === 'merge'
                        ? 'Glossary merge completed'
                        : translate('glossary_health_completed_title'),
                    message: kind === 'merge'
                        ? (task.result?.summary || 'The background task completed.')
                        : translate('glossary_health_completed_message', {
                            score: healthReport.score ?? 0,
                            count: healthReport.issue_count ?? 0,
                        }),
                    color: 'green',
                });
                return task;
            }

            notifications.show({
                title: kind === 'merge'
                    ? 'Glossary merge failed'
                    : translate('glossary_health_failed_title'),
                message: kind === 'merge'
                    ? (task.message || 'Open the task center for details.')
                    : localizeHealthTaskError(translate, task.message),
                color: 'red',
            });
            return task;
        } catch (error) {
            if (isCancelled()) return null;
            setGlossaryOperation((current) => (
                current?.taskId === taskId
                    ? { ...current, status: 'monitor_error', error: error.message }
                    : current
            ));
            notifications.show({
                title: 'Task monitoring interrupted',
                message: 'The task may still be running. Check the task center.',
                color: 'orange',
            });
        }
    }, [refreshGlossaryIndex, setGlossaryOperation, translate]);

    const shouldMonitorGlossaryOperation = isGlossaryTaskActive(glossaryOperation);
    useEffect(() => {
        if (!shouldMonitorGlossaryOperation) return undefined;

        let cancelled = false;
        void monitorGlossaryTask(
            glossaryOperation.taskId,
            glossaryOperation.kind,
            () => cancelled
        );
        return () => {
            cancelled = true;
        };
    }, [
        glossaryOperation?.kind,
        glossaryOperation?.taskId,
        monitorGlossaryTask,
        shouldMonitorGlossaryOperation,
    ]);

    const onSelectTree = (key, info) => {
        if (info.isLeaf) {
            const [gameId, glossaryId, fileName] = key.split('|');
            setSelectedFile({
                key,
                title: fileName,
                gameId,
                glossaryId: parseInt(glossaryId, 10)
            });
            setSearchScope('file');
            setFiltering('');
            setPagination({ pageIndex: 0, pageSize: 25 });
            setViewMode('editor');
            setFocusedEntry(null);
        } else {
            setSelectedGame(key);
        }
    };

    const openGlossary = (item) => {
        setSelectedGame(item.game_id);
        setSelectedFile({
            key: `${item.game_id}|${item.glossary_id}|${item.name}`,
            title: item.name,
            gameId: item.game_id,
            glossaryId: item.glossary_id,
        });
        setSearchScope('file');
        setFiltering('');
        setPagination({ pageIndex: 0, pageSize: 25 });
        setViewMode('editor');
        setFocusedEntry(null);
    };

    const showOverview = () => setViewMode('overview');

    const handleSave = async (payload) => {
        if (!selectedFile.glossaryId) return;

        setIsSaving(true);
        try {
            if (payload.id) {
                await api.put(`/api/glossary/entry/${payload.id}`, payload);
            } else {
                await api.post(
                    `/api/glossary/entry?glossary_id=${selectedFile.glossaryId}`,
                    payload
                );
            }

            notifications.show({
                title: translate('glossary_entry_saved_title'),
                message: translate('glossary_entry_saved_message'),
                color: 'green'
            });

            await Promise.all([
                fetchGlossaryContent(),
                refreshGlossaryOverview(),
            ]);
            return true;
        } catch {
            notifications.show({
                title: translate('neologism_review.common.error'),
                message: translate('glossary_entry_save_failed'),
                color: 'red'
            });
            return false;
        } finally {
            setIsSaving(false);
        }
    };

    const handleDelete = async (id) => {
        setIsSaving(true);
        try {
            await api.delete(`/api/glossary/entry/${id}`);

            notifications.show({
                title: 'Success',
                message: 'Entry deleted successfully!',
                color: 'green'
            });

            const newTotalCount = rowCount - 1;
            const newPageCount = Math.ceil(newTotalCount / pagination.pageSize);

            if (pagination.pageIndex >= newPageCount && newPageCount > 0) {
                setPagination(prev => ({ ...prev, pageIndex: newPageCount - 1 }));
            } else {
                await fetchGlossaryContent();
            }
            await refreshGlossaryOverview();

            return true;
        } catch {
            notifications.show({
                title: 'Error',
                message: 'Failed to delete entry.',
                color: 'red'
            });
            return false;
        } finally {
            setIsSaving(false);
        }
    };

    const handleCreateGlossary = async (name) => {
        if (!selectedGame) return false;

        setIsSaving(true);
        try {
            await api.post('/api/glossary', {
                game_id: selectedGame,
                name
            });

            notifications.show({
                title: translate('neologism_review.common.success', { defaultValue: 'Success' }),
                message: translate('glossary_create_success'),
                color: 'green'
            });

            await refreshGlossaryIndex();

            return true;
        } catch {
            notifications.show({
                title: translate('neologism_review.common.error', { defaultValue: 'Error' }),
                message: translate('glossary_create_failed'),
                color: 'red'
            });
            return false;
        } finally {
            setIsSaving(false);
        }
    };

    const handleDuplicateGlossary = async (sourceGlossary, targetName) => {
        if (!sourceGlossary?.glossary_id || !targetName?.trim()) return false;

        setIsSaving(true);
        try {
            const response = await api.post(
                `/api/glossary/file/${sourceGlossary.glossary_id}/duplicate`,
                { name: targetName.trim() }
            );

            notifications.show({
                title: 'Glossary duplicated',
                message: `${response.data.entry_count} entries copied to ${response.data.name}.`,
                color: 'green'
            });

            await refreshGlossaryIndex();
            return true;
        } catch (error) {
            notifications.show({
                title: 'Duplicate failed',
                message: error.response?.data?.detail || 'Could not duplicate this glossary.',
                color: 'red'
            });
            return false;
        } finally {
            setIsSaving(false);
        }
    };

    const handleUpdateGlossaryMetadata = async (glossary, values) => {
        if (!glossary?.glossary_id || !values?.name?.trim()) return false;

        setIsSaving(true);
        try {
            const response = await api.put(
                `/api/glossary/file/${glossary.glossary_id}`,
                {
                    name: values.name.trim(),
                    description: values.description?.trim() || '',
                    kind: values.kind,
                    project_ids: values.projectIds || [],
                }
            );

            if (selectedFile.glossaryId === glossary.glossary_id) {
                setSelectedFile((current) => ({
                    ...current,
                    title: response.data.name,
                }));
            }

            notifications.show({
                title: 'Glossary information updated',
                message: `${response.data.name} is now up to date.`,
                color: 'green'
            });

            await refreshGlossaryIndex();
            return true;
        } catch (error) {
            notifications.show({
                title: 'Update failed',
                message: error.response?.data?.detail || 'Could not update this glossary.',
                color: 'red'
            });
            return false;
        } finally {
            setIsSaving(false);
        }
    };

    const previewGlossaryBatchDelete = async (glossaryIds) => {
        if (!glossaryIds?.length) return null;

        setIsSaving(true);
        try {
            const response = await api.post('/api/glossaries/batch-delete/preview', {
                glossary_ids: glossaryIds,
            });
            return response.data;
        } catch (error) {
            notifications.show({
                title: 'Impact preview failed',
                message: error.response?.data?.detail || 'Could not calculate deletion impact.',
                color: 'red'
            });
            return null;
        } finally {
            setIsSaving(false);
        }
    };

    const handleBatchDeleteGlossaries = async (glossaryIds, confirmations) => {
        if (!glossaryIds?.length) return false;

        setIsSaving(true);
        try {
            const response = await api.post('/api/glossaries/batch-delete', {
                glossary_ids: glossaryIds,
                confirm_main_glossaries: Boolean(confirmations?.mainGlossaries),
                confirm_project_bindings: Boolean(confirmations?.projectBindings),
            });

            notifications.show({
                title: 'Glossaries deleted',
                message: `${response.data.deleted_glossary_count} glossaries and ${response.data.deleted_term_count} terms removed.`,
                color: 'green'
            });

            if (glossaryIds.includes(selectedFile.glossaryId)) {
                setSelectedFile({ key: null, title: 'No file selected', gameId: null, glossaryId: null });
                setData([]);
                setRowCount(0);
            }
            await refreshGlossaryIndex();
            setViewMode('overview');
            return true;
        } catch (error) {
            notifications.show({
                title: 'Delete failed',
                message: error.response?.data?.detail || 'Could not delete the selected glossaries.',
                color: 'red'
            });
            return false;
        } finally {
            setIsSaving(false);
        }
    };

    const previewGlossaryMerge = async (glossaryIds, options) => {
        if (!glossaryIds?.length || glossaryIds.length < 2) return null;
        setIsSaving(true);
        try {
            const response = await api.post('/api/glossaries/merge/preview', {
                glossary_ids: glossaryIds,
                ...options,
            });
            return response.data;
        } catch (error) {
            notifications.show({
                title: 'Merge preview failed',
                message: error.response?.data?.detail || 'Could not build the merge preview.',
                color: 'red',
            });
            return null;
        } finally {
            setIsSaving(false);
        }
    };

    const startGlossaryMerge = async (glossaryIds, options) => {
        if (!glossaryIds?.length || glossaryIds.length < 2) return null;
        setIsSaving(true);
        try {
            const response = await api.post('/api/glossaries/merge', {
                glossary_ids: glossaryIds,
                ...options,
            });
            const operation = {
                taskId: response.data.task_id,
                kind: 'merge',
                status: response.data.status,
                preview: response.data.preview,
            };
            setGlossaryOperation(operation);
            notifications.show({
                title: 'Glossary merge queued',
                message: `Task ${response.data.task_id} is available in the task center.`,
                color: 'blue',
            });
            return response.data;
        } catch (error) {
            const detail = error.response?.data?.detail;
            notifications.show({
                title: 'Glossary merge failed to start',
                message: typeof detail === 'string' ? detail : detail?.message || 'Could not start the merge.',
                color: 'red',
            });
            return null;
        } finally {
            setIsSaving(false);
        }
    };

    const startGlossaryHealthCheck = async (glossaryIds, options) => {
        if (!glossaryIds?.length) return null;
        setIsSaving(true);
        try {
            const response = await api.post('/api/glossaries/health-check', {
                glossary_ids: glossaryIds,
                ...options,
            });
            const operation = {
                taskId: response.data.task_id,
                kind: 'health',
                status: response.data.status,
                preview: response.data.deterministic_preview,
                aiReviewPlan: response.data.ai_review_plan,
            };
            setGlossaryOperation(operation);
            const aiPlan = response.data.ai_review_plan;
            notifications.show({
                title: translate('glossary_health_queued_title'),
                message: response.data.ai_advice_requested
                    ? (
                        aiPlan
                            ? translate('glossary_health_queued_ai_plan', {
                                count: aiPlan.case_count,
                                batches: aiPlan.batch_count,
                            })
                            : translate('glossary_health_queued_ai')
                    )
                    : translate('glossary_health_queued_script'),
                color: 'blue',
            });
            return response.data;
        } catch (error) {
            const detail = error.response?.data?.detail;
            if (error.response?.status === 409 && detail?.task_id) {
                const existingOperation = {
                    taskId: detail.task_id,
                    kind: 'health',
                    status: 'running',
                    preview: null,
                    aiReviewPlan: null,
                };
                setGlossaryOperation(existingOperation);
                notifications.show({
                    title: translate('glossary_health_queued_title'),
                    message: translate('glossary_health_queued_script'),
                    color: 'blue',
                });
                return {
                    task_id: detail.task_id,
                    status: 'running',
                    deterministic_preview: null,
                    ai_review_plan: null,
                    existing_task: true,
                };
            }
            notifications.show({
                title: translate('glossary_health_failed_title'),
                message: typeof detail === 'string'
                    ? localizeHealthTaskError(translate, detail)
                    : detail?.message || translate('glossary_health_model_request_failed'),
                color: 'red',
            });
            return null;
        } finally {
            setIsSaving(false);
        }
    };

    const loadGlossaryHealthHistory = async (glossaryId) => {
        if (!glossaryId) return [];
        const response = await api.get('/api/tasks', {
            params: {
                kind: 'glossary_health_check',
                glossary_id: glossaryId,
                include_archived: true,
                limit: 50,
            },
        });
        return normalizeGlossaryTaskHistoryPayload(response.data);
    };

    const handleDeleteGlossary = async () => {
        if (!selectedFile.glossaryId) return false;

        setIsSaving(true);
        try {
            await api.delete(`/api/glossary/file/${selectedFile.glossaryId}`);

            notifications.show({
                title: 'Success',
                message: 'Glossary deleted successfully!',
                color: 'green'
            });

            // Reset selection and reload tree
            setSelectedFile({ key: null, title: 'No file selected', gameId: null, glossaryId: null });
            setData([]);
            setRowCount(0);

            await refreshGlossaryIndex();
            setViewMode('overview');

            return true;
        } catch {
            notifications.show({
                title: 'Error',
                message: 'Failed to delete glossary.',
                color: 'red'
            });
            return false;
        } finally {
            setIsSaving(false);
        }
    };

    // ==================== 返回接口 ====================
    return {
        // 状态
        treeData,
        overview,
        viewMode,
        data,
        selectedGame,
        setSelectedGame,
        selectedFile,
        targetLanguages,
        apiProviders,
        projects,
        glossaryOperation,
        selectedTargetLang,
        setSelectedTargetLang,
        searchScope,
        setSearchScope,
        filtering,
        setFiltering,
        pagination,
        setPagination,
        rowCount,
        focusedEntry,

        // 加载状态
        isLoadingTree,
        isLoadingOverview,
        isLoadingContent,
        isSaving,

        // 事件处理器
        onSelectTree,
        openGlossary,
        showOverview,
        handleSave,
        handleDelete,
        handleCreateGlossary,
        handleDuplicateGlossary,
        handleUpdateGlossaryMetadata,
        previewGlossaryBatchDelete,
        handleBatchDeleteGlossaries,
        previewGlossaryMerge,
        startGlossaryMerge,
        startGlossaryHealthCheck,
        loadGlossaryHealthHistory,
        clearGlossaryOperation: () => setGlossaryOperation(null),
        handleDeleteGlossary,
        fetchGlossaryContent,
    };
};

export default useGlossaryActions;
