import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '../utils/api';
import { usePersistentState } from '../hooks/usePersistentState';

const TranslationContext = createContext();

export const useTranslationContext = () => {
    const context = useContext(TranslationContext);
    if (!context) {
        throw new Error('useTranslationContext must be used within a TranslationProvider');
    }
    return context;
};

export const TranslationProvider = ({ children }) => {
    const [activeStep, setActiveStep] = usePersistentState('trans_active_step', 0);
    const [taskId, setTaskId] = useState(null);
    const [taskStatus, setTaskStatus] = useState(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const [translationDetails, setTranslationDetails] = useState(null);
    const [selectedProjectId, setSelectedProjectId] = usePersistentState('trans_selected_project_id', null);

    // Reset translation state
    const resetTranslation = useCallback(() => {
        setTaskId(null);
        setTaskStatus(null);
        setIsProcessing(false);
        setActiveStep(0);
        setTranslationDetails(null);
    }, []);

    const applyTaskUpdate = useCallback((data) => {
        setTaskStatus(data);
        if (data?.status === 'completed' || data?.status === 'partial_failed' || data?.status === 'failed') {
            setIsProcessing(false);
            if (data.status === 'completed' || data.status === 'partial_failed') {
                setActiveStep(3);
            }
        }
    }, [setActiveStep]);

    // WebSocket for real-time status updates
    useEffect(() => {
        let socket;
        let pollingTimer;
        let retryTimer;
        let cancelled = false;

        const fetchTaskStatus = async () => {
            if (!taskId) return;
            try {
                const response = await api.get(`/api/status/${taskId}`);
                if (!cancelled) {
                    applyTaskUpdate(response.data);
                }
            } catch (error) {
                console.error("[Status Poll] Failed to fetch task status:", error);
            }
        };

        const startPolling = () => {
            if (pollingTimer || !taskId) return;
            pollingTimer = window.setInterval(() => {
                fetchTaskStatus();
            }, 1500);
        };

        const stopPolling = () => {
            if (pollingTimer) {
                window.clearInterval(pollingTimer);
                pollingTimer = null;
            }
        };

        const connectSocket = () => {
            if (!taskId || cancelled) return;

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            // Note: In a production Tauri environment, we point directly to localhost:8081.
            // In dev, we also point to the backend port.
            const host = import.meta.env.DEV ? '127.0.0.1:8081' : '127.0.0.1:8081';
            const wsUrl = `${protocol}//${host}/api/ws/status/${taskId}`;

            console.log(`[WebSocket] Connecting to ${wsUrl}`);
            socket = new WebSocket(wsUrl);

            socket.onopen = () => {
                stopPolling();
                fetchTaskStatus();
            };

            socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    applyTaskUpdate(data);
                } catch (err) {
                    console.error("[WebSocket] Failed to parse message:", err);
                }
            };

            socket.onerror = (error) => {
                console.error("[WebSocket] Error:", error);
                startPolling();
            };

            socket.onclose = (event) => {
                console.log(`[WebSocket] Connection closed for task ${taskId}: ${event.reason}`);
                if (!cancelled) {
                    startPolling();
                    retryTimer = window.setTimeout(() => {
                        retryTimer = null;
                        connectSocket();
                    }, 1000);
                }
            };
        };

        if (taskId && isProcessing) {
            fetchTaskStatus();
            startPolling();
            connectSocket();
        }
        return () => {
            cancelled = true;
            stopPolling();
            if (retryTimer) {
                window.clearTimeout(retryTimer);
            }
            if (socket) {
                console.log(`[WebSocket] Cleaning up connection for task ${taskId}`);
                socket.close();
            }
        };
    }, [taskId, isProcessing, applyTaskUpdate]);

    const value = {
        activeStep,
        setActiveStep,
        taskId,
        setTaskId,
        taskStatus,
        setTaskStatus,
        isProcessing,
        setIsProcessing,
        translationDetails,
        setTranslationDetails,
        selectedProjectId,
        setSelectedProjectId,
        resetTranslation
    };

    return (
        <TranslationContext.Provider value={value}>
            {children}
        </TranslationContext.Provider>
    );
};
