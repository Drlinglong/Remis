import { useState, useEffect, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { useTranslation } from 'react-i18next';
import api from '../utils/api';

const API_BASE = '/api';

export const useKanban = (projectId) => {
    const { t } = useTranslation();
    const [tasks, setTasks] = useState([]);
    const [columns, setColumns] = useState(['todo', 'in_progress', 'proofreading', 'paused', 'done']);
    const [isLoading, setIsLoading] = useState(true);

    // Load Data from Backend
    useEffect(() => {
        if (!projectId) return;

        const loadData = async () => {
            setIsLoading(true);
            try {
                const res = await api.get(`${API_BASE}/project/${projectId}/kanban`);
                const data = res.data;

                if (data.tasks) {
                    setTasks(Object.values(data.tasks));
                }
                if (data.column_order) {
                    setColumns(data.column_order);
                }
            } catch (error) {
                console.error("Failed to load Kanban data:", error);
            } finally {
                setIsLoading(false);
            }
        };

        loadData();
    }, [projectId]);

    // Save Data to Backend
    const saveBoard = useCallback(async (newTasks, newColumns) => {
        if (!projectId) return;

        // Convert array back to map for storage
        const tasksMap = {};
        newTasks.forEach(t => tasksMap[t.id] = t);

        try {
            await api.post(`${API_BASE}/project/${projectId}/kanban`, {
                tasks: tasksMap,
                columns: newColumns || columns, // Ensure we save columns even if not passed
                column_order: newColumns || columns
            });
        } catch (error) {
            console.error("Failed to save Kanban data:", error);
        }
    }, [projectId, columns]);

    // --- Actions ---

    const moveTask = useCallback((taskId, newStatus) => {
        setTasks((prev) => {
            const updatedTasks = prev.map(t =>
                t.id === taskId ? { ...t, status: newStatus } : t
            );
            // Move persistence out of the pure updater
            setTimeout(() => saveBoard(updatedTasks, columns), 0);
            return updatedTasks;
        });
    }, [saveBoard, columns]);

    const addNoteTask = useCallback((status = 'todo') => {
        const newTask = {
            id: uuidv4(),
            type: 'note',
            title: t('project_management.kanban.new_task'),
            status,
            comments: '',
            priority: 'medium'
        };
        setTasks(prev => {
            const updatedTasks = [newTask, ...prev];
            setTimeout(() => saveBoard(updatedTasks, columns), 0);
            return updatedTasks;
        });
        return newTask;
    }, [t, saveBoard, columns]);

    const updateTask = useCallback((taskId, updates) => {
        setTasks(prev => {
            const updatedTasks = prev.map(t =>
                t.id === taskId ? { ...t, ...updates } : t
            );
            setTimeout(() => saveBoard(updatedTasks, columns), 0);
            return updatedTasks;
        });
    }, [saveBoard, columns]);

    const deleteTask = useCallback((taskId) => {
        setTasks(prev => {
            const updatedTasks = prev.filter(t => t.id !== taskId);
            setTimeout(() => saveBoard(updatedTasks, columns), 0);
            return updatedTasks;
        });
    }, [saveBoard, columns]);

    const refreshBoard = useCallback(async () => {
        if (!projectId) return;
        setIsLoading(true);
        try {
            // Trigger backend refresh
            await api.post(`${API_BASE}/project/${projectId}/refresh`);
            // Reload data
            const res = await api.get(`${API_BASE}/project/${projectId}/kanban`);
            const data = res.data;
            if (data.tasks) setTasks(Object.values(data.tasks));
            if (data.column_order) setColumns(data.column_order);
        } catch (error) {
            console.error("Failed to refresh board:", error);
        } finally {
            setIsLoading(false);
        }
    }, [projectId]);

    return {
        tasks,
        isLoading,
        moveTask,
        addNoteTask,
        updateTask,
        deleteTask,
        refreshBoard,
        columns
    };
};
