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

    // Polling Logic - Global to the application
    useEffect(() => {
        let interval;
        if (taskId && isProcessing) {
            interval = setInterval(async () => {
                try {
                    const response = await api.get(`/api/status/${taskId}`);
                    if (response.status === 200) {
                        setTaskStatus(response.data);
                        if (response.data.status === 'completed' || response.data.status === 'failed') {
                            setIsProcessing(false);
                            clearInterval(interval);
                            if (response.data.status === 'completed') {
                                setActiveStep(3);
                            }
                        }
                    }
                } catch (error) {
                    console.error("Error polling status in context:", error);
                    // Check if task doesn't exist anymore?
                    if (error.response && error.response.status === 404) {
                        setIsProcessing(false);
                        clearInterval(interval);
                    }
                }
            }, 3000);
        }
        return () => clearInterval(interval);
    }, [taskId, isProcessing]);

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
