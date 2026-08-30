import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import api from '../../utils/api';
import { getErrorMessage } from './modArchiveModel';

export const useContextAnalysisPreview = (selectedProject) => {
    const { t } = useTranslation();
    const translationRef = useRef(t);
    translationRef.current = t;
    const requestVersionRef = useRef(0);
    const [state, setState] = useState({ phase: 'loading', preview: null, error: null });

    const load = useCallback(async () => {
        if (!selectedProject) {
            setState({ phase: 'empty', preview: null, error: null });
            return;
        }
        const requestVersion = requestVersionRef.current + 1;
        requestVersionRef.current = requestVersion;
        setState({ phase: 'loading', preview: null, error: null });
        try {
            const response = await api.get(
                `/api/context/projects/${encodeURIComponent(selectedProject)}/analysis-preview?optional=true`,
            );
            if (response.data?.preview === null) {
                setState({ phase: 'empty', preview: null, error: null });
                return;
            }
            if (requestVersionRef.current === requestVersion) {
                setState({ phase: 'ready', preview: response.data, error: null });
            }
        } catch (error) {
            if (requestVersionRef.current !== requestVersion) return;
            if (error?.response?.status === 404) {
                setState({ phase: 'empty', preview: null, error: null });
                return;
            }
            setState({
                phase: 'error',
                preview: null,
                error: getErrorMessage(
                    error,
                    translationRef.current('mod_archive.release.preview.error_desc'),
                ),
            });
        }
    }, [selectedProject]);

    useEffect(() => {
        load();
    }, [load]);

    return { ...state, refresh: load };
};
