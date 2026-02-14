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

    // WebSocket for real-time status updates
    useEffect(() => {
        let socket;
        if (taskId && isProcessing) {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            // Note: In a production Tauri environment, we point directly to localhost:8081.
            // In dev, we also point to the backend port.
            const host = import.meta.env.DEV ? '127.0.0.1:8081' : '127.0.0.1:8081';
            const wsUrl = `${protocol}//${host}/api/ws/status/${taskId}`;

            console.log(`[WebSocket] Connecting to ${wsUrl}`);
            socket = new WebSocket(wsUrl);

            socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    setTaskStatus(data);
                    if (data.status === 'completed' || data.status === 'failed') {
                        setIsProcessing(false);
                        if (data.status === 'completed') {
                            setActiveStep(3);
                        }
                    }
                } catch (err) {
                    console.error("[WebSocket] Failed to parse message:", err);
                }
            };

            socket.onerror = (error) => {
                console.error("[WebSocket] Error:", error);
            };

            socket.onclose = (event) => {
                console.log(`[WebSocket] Connection closed for task ${taskId}: ${event.reason}`);
                // If it closed while still processing, it might be a temporary loss of connection
                // but we'll let the user manually retry or just wait for now to keep it simple.
            };
        }
        return () => {
            if (socket) {
                console.log(`[WebSocket] Cleaning up connection for task ${taskId}`);
                socket.close();
            }
        };
    }, [taskId, isProcessing, setActiveStep]);

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
