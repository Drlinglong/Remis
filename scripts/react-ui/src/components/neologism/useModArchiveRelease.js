import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import api from '../../utils/api';
import { getErrorMessage } from './modArchiveModel';

const API_BASE_URL = '/api';

const initialState = Object.freeze({
    phase: 'idle',
    release: null,
    effective: null,
    error: null,
    traceability: [],
    traceabilityState: 'idle',
    traceabilityError: null,
});

const isNotFound = (error) => error?.response?.status === 404;

const unwrap = (data, key) => data?.[key] || data;

export const useModArchiveRelease = (selectedProject) => {
    const { t } = useTranslation();
    const translationRef = useRef(t);
    translationRef.current = t;
    const translate = useCallback((key, options) => translationRef.current(key, options), []);
    const [state, setState] = useState(initialState);
    const requestVersionRef = useRef(0);

    const loadRelease = useCallback(async () => {
        if (!selectedProject) {
            setState(initialState);
            return;
        }

        const requestVersion = requestVersionRef.current + 1;
        requestVersionRef.current = requestVersion;
        setState({ ...initialState, phase: 'loading' });
        try {
            const releaseResponse = await api.get(
                `${API_BASE_URL}/context/releases/${encodeURIComponent(selectedProject)}/latest?optional=true`,
            );
            if (releaseResponse.data?.release === null) {
                setState({ ...initialState, phase: 'empty' });
                return;
            }
            const release = unwrap(releaseResponse.data, 'release');
            if (!release?.release_id) {
                throw new Error(translate('mod_archive.release.incomplete_error'));
            }
            setState((current) => (
                requestVersionRef.current === requestVersion
                    ? { ...current, release }
                    : current
            ));

            try {
                const effectiveResponse = await api.get(
                    `${API_BASE_URL}/context/releases/${encodeURIComponent(release.release_id)}/effective`,
                );
                const effective = unwrap(effectiveResponse.data, 'effective');
                const hasContext = Object.keys(effective?.effective_context || {}).length > 0;
                if (requestVersionRef.current === requestVersion) {
                    setState((current) => ({
                        ...current,
                        effective,
                        phase: hasContext ? 'ready' : 'partial',
                        error: hasContext ? null : translate('mod_archive.release.no_effective_error'),
                    }));
                }
            } catch (error) {
                if (requestVersionRef.current === requestVersion) {
                    setState((current) => ({
                        ...current,
                        phase: 'partial',
                        error: getErrorMessage(error, translate('mod_archive.release.summary_error')),
                    }));
                }
            }
        } catch (error) {
            if (requestVersionRef.current !== requestVersion) return;
            if (isNotFound(error)) {
                setState({ ...initialState, phase: 'empty' });
            } else {
                setState({
                    ...initialState,
                    phase: 'error',
                    error: getErrorMessage(error, translate('mod_archive.release.error_desc')),
                });
            }
        }
    }, [selectedProject, translate]);

    useEffect(() => {
        loadRelease();
    }, [loadRelease]);

    const loadTraceability = useCallback(async () => {
        const releaseId = state.release?.release_id;
        if (!releaseId || state.traceabilityState === 'loading') return;
        setState((current) => ({
            ...current,
            traceabilityState: 'loading',
            traceabilityError: null,
        }));
        try {
            const response = await api.get(
                `${API_BASE_URL}/context/releases/${encodeURIComponent(releaseId)}/traceability`,
            );
            const traceability = Array.isArray(response.data)
                ? response.data
                : Array.isArray(response.data?.items)
                    ? response.data.items
                    : Array.isArray(response.data?.traceability)
                        ? response.data.traceability
                        : [];
            setState((current) => ({
                ...current,
                phase: current.phase === 'ready' ? 'ready' : 'partial',
                traceability,
                traceabilityState: 'ready',
                traceabilityError: null,
            }));
        } catch (error) {
            setState((current) => ({
                ...current,
                phase: 'partial',
                traceabilityState: 'error',
                traceabilityError: getErrorMessage(
                    error,
                    translate('mod_archive.release.traceability_error'),
                ),
            }));
        }
    }, [state.release?.release_id, state.traceabilityState, translate]);

    return {
        ...state,
        refresh: loadRelease,
        loadTraceability,
    };
};
