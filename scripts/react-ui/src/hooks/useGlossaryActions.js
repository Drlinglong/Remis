import { useState, useEffect } from 'react';
import { notifications } from '@mantine/notifications';
import { usePersistentState } from './usePersistentState';
import api from '../utils/api';

/**
 * 词典管理的数据和操作 Hook
 * 集中管理 API 调用、状态管理和事件处理
 */
const useGlossaryActions = () => {
    // ==================== 状态 ====================
    const [treeData, setTreeData] = useState([]);
    const [data, setData] = useState([]);
    const [selectedGame, setSelectedGame] = usePersistentState('glossary_selected_game', null);
    const [selectedFile, setSelectedFile] = usePersistentState('glossary_selected_file', {
        key: null,
        title: 'No file selected',
        gameId: null,
        glossaryId: null
    });
    const [targetLanguages, setTargetLanguages] = useState([]);
    const [selectedTargetLang, setSelectedTargetLang] = usePersistentState('glossary_target_lang', '');
    const [searchScope, setSearchScope] = usePersistentState('glossary_search_scope', 'file');
    const [filtering, setFiltering] = usePersistentState('glossary_filtering', '');
    const [pagination, setPagination] = usePersistentState('glossary_pagination', { pageIndex: 0, pageSize: 25 });
    const [rowCount, setRowCount] = useState(0);

    const [isLoadingTree, setIsLoadingTree] = useState(true);
    const [isLoadingContent, setIsLoadingContent] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    // ==================== 初始化数据获取 ====================
    useEffect(() => {
        const fetchInitialConfigs = async () => {
            setIsLoadingTree(true);
            try {
                const [treeResponse, configResponse] = await Promise.all([
                    api.get('/api/glossary/tree'),
                    api.get('/api/config')
                ]);

                setTreeData(treeResponse.data);
                if (treeResponse.data.length > 0 && !selectedGame) {
                    setSelectedGame(treeResponse.data[0].key);
                }

                const languages = Object.values(configResponse.data.languages);
                setTargetLanguages(languages);
                if (languages.length > 0 && !selectedTargetLang) {
                    setSelectedTargetLang(
                        languages.find(l => l.code === 'zh-CN')?.code || languages[0].code
                    );
                }
            } catch (error) {
                notifications.show({
                    title: 'Error',
                    message: 'Failed to load initial configuration.',
                    color: 'red'
                });
            } finally {
                setIsLoadingTree(false);
            }
        };
        fetchInitialConfigs();
    }, []);

    // ==================== 词典内容获取 ====================
    const fetchGlossaryContent = async () => {
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

            setData(response.data.entries);
            setRowCount(response.data.totalCount);
        } catch (error) {
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
    };

    useEffect(() => {
        fetchGlossaryContent();
    }, [selectedFile, pagination, filtering, searchScope]);

    // ==================== 事件处理器 ====================
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
        } else {
            setSelectedGame(key);
        }
    };

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
                title: 'Success',
                message: 'Glossary saved successfully!',
                color: 'green'
            });

            fetchGlossaryContent();
            return true;
        } catch (error) {
            notifications.show({
                title: 'Error',
                message: 'Failed to save glossary.',
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
                fetchGlossaryContent();
            }

            return true;
        } catch (error) {
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

    const handleCreateFile = async (fileName) => {
        if (!selectedGame) return false;

        setIsSaving(true);
        try {
            await api.post('/api/glossary/file', {
                game_id: selectedGame,
                file_name: fileName
            });

            notifications.show({
                title: 'Success',
                message: 'File created successfully!',
                color: 'green'
            });

            // Reload tree
            const treeResponse = await api.get('/api/glossary/tree');
            setTreeData(treeResponse.data);

            return true;
        } catch (error) {
            notifications.show({
                title: 'Error',
                message: 'Failed to create file.',
                color: 'red'
            });
            return false;
        } finally {
            setIsSaving(false);
        }
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

            const treeResponse = await api.get('/api/glossary/tree');
            setTreeData(treeResponse.data);

            return true;
        } catch (error) {
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
        data,
        selectedGame,
        setSelectedGame,
        selectedFile,
        targetLanguages,
        selectedTargetLang,
        setSelectedTargetLang,
        searchScope,
        setSearchScope,
        filtering,
        setFiltering,
        pagination,
        setPagination,
        rowCount,

        // 加载状态
        isLoadingTree,
        isLoadingContent,
        isSaving,

        // 事件处理器
        onSelectTree,
        handleSave,
        handleDelete,
        handleCreateFile,
        handleDeleteGlossary,
        fetchGlossaryContent,
    };
};

export default useGlossaryActions;
