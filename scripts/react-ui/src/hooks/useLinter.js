import { useState, useCallback } from 'react';
import api from '../utils/api';

/**
 * Hook for managing the localization linter (Free Mode).
 */
export const useLinter = () => {
    const [linterContent, setLinterContent] = useState('');
    const [linterGameId, setLinterGameId] = useState('1');
    const [linterResults, setLinterResults] = useState([]);
    const [linterLoading, setLinterLoading] = useState(false);
    const [linterError, setLinterError] = useState(null);

    const handleLinterValidate = useCallback(async () => {
        if (!linterContent.trim()) return;
        setLinterLoading(true);
        setLinterError(null);
        setLinterResults([]);
        try {
            const response = await api.post('/api/validate/localization', {
                game_id: linterGameId,
                content: linterContent,
                source_lang_code: 'en_US'
            });
            setLinterResults(response.data);
        } catch (err) {
            setLinterError("Failed to validate.");
        } finally {
            setLinterLoading(false);
        }
    }, [linterContent, linterGameId]);

    return {
        linterContent,
        setLinterContent,
        linterGameId,
        setLinterGameId,
        linterResults,
        linterLoading,
        linterError,
        handleLinterValidate
    };
};
