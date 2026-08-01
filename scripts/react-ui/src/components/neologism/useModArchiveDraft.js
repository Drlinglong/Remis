import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import api from '../../utils/api';
import {
    buildOverrideDelta,
    getContextErrorCode,
    getDraftOverride,
    getEditorValues,
} from './modArchiveModel';

const API_BASE_URL = '/api';

const ERROR_TRANSLATION_KEYS = Object.freeze({
    context_release_not_found: 'mod_archive.release.draft.errors.context_release_not_found',
    context_draft_not_found: 'mod_archive.release.draft.errors.context_draft_not_found',
    context_ownership_not_found: 'mod_archive.release.draft.errors.context_ownership_not_found',
    context_key_not_found: 'mod_archive.release.draft.errors.context_key_not_found',
    context_override_invalid: 'mod_archive.release.draft.errors.context_override_invalid',
    context_draft_closed: 'mod_archive.release.draft.errors.context_draft_closed',
    context_request_failed: 'mod_archive.release.draft.errors.context_request_failed',
});

const unwrap = (data, key) => data?.[key] || data;

const emptyError = Object.freeze({ code: null, message: null });

const getContextError = (error, translate) => {
    const code = getContextErrorCode(error);
    const translationKey = ERROR_TRANSLATION_KEYS[code]
        || ERROR_TRANSLATION_KEYS.context_request_failed;
    return { code, message: translate(translationKey) };
};

const getFirstContextKey = (contextEntries, draft) => (
    contextEntries[0]?.key
    || draft?.overrides?.[0]?.target_key
    || ''
);

export const useModArchiveDraft = ({
    selectedProject,
    baseReleaseId,
    contextEntries = [],
    onPublished,
}) => {
    const { t } = useTranslation();
    const translationRef = useRef(t);
    translationRef.current = t;
    const translate = useCallback((key, options) => translationRef.current(key, options), []);
    const onPublishedRef = useRef(onPublished);
    onPublishedRef.current = onPublished;
    const [phase, setPhase] = useState('idle');
    const [draft, setDraft] = useState(null);
    const [selectedKey, setSelectedKey] = useState('');
    const [fieldValues, setFieldValues] = useState({});
    const [initialValues, setInitialValues] = useState({});
    const [note, setNote] = useState('');
    const [error, setError] = useState(emptyError);
    const [notice, setNotice] = useState(null);
    const [publishedRelease, setPublishedRelease] = useState(null);

    const buildEditorSnapshot = useCallback((draftData, requestedKey) => {
        const key = requestedKey || getFirstContextKey(contextEntries, draftData);
        const entry = contextEntries.find((item) => item.key === key);
        const override = getDraftOverride(draftData, key);
        const values = getEditorValues(entry, override);
        return { key, values, note: override?.note || '' };
    }, [contextEntries]);

    const applyEditorSnapshot = useCallback((draftData, requestedKey) => {
        const snapshot = buildEditorSnapshot(draftData, requestedKey);
        setSelectedKey(snapshot.key);
        setFieldValues(snapshot.values);
        setInitialValues(snapshot.values);
        setNote(snapshot.note);
    }, [buildEditorSnapshot]);

    useEffect(() => {
        setPhase('idle');
        setDraft(null);
        setSelectedKey('');
        setFieldValues({});
        setInitialValues({});
        setNote('');
        setError(emptyError);
        setNotice(null);
        setPublishedRelease(null);
    }, [baseReleaseId, selectedProject]);

    const startDraft = useCallback(async () => {
        if (!selectedProject || !baseReleaseId || phase === 'starting') return null;
        setPhase('starting');
        setError(emptyError);
        setNotice(null);
        try {
            const response = await api.post(
                `${API_BASE_URL}/context/projects/${encodeURIComponent(selectedProject)}/releases/${encodeURIComponent(baseReleaseId)}/drafts`,
            );
            const nextDraft = unwrap(response.data, 'draft');
            if (!nextDraft?.draft_id) throw new Error('draft_response_incomplete');
            setDraft(nextDraft);
            applyEditorSnapshot(nextDraft);
            setPhase('ready');
            return nextDraft;
        } catch (requestError) {
            setPhase('idle');
            setError(getContextError(requestError, translate));
            return null;
        }
    }, [applyEditorSnapshot, baseReleaseId, phase, selectedProject, translate]);

    const selectContextKey = useCallback((nextKey) => {
        if (!draft || !nextKey) return;
        applyEditorSnapshot(draft, nextKey);
        setError(emptyError);
        setNotice(null);
    }, [applyEditorSnapshot, draft]);

    const updateField = useCallback((fieldKey, value) => {
        setFieldValues((current) => ({ ...current, [fieldKey]: value }));
        setError(emptyError);
        setNotice(null);
    }, []);

    const updateNote = useCallback((value) => {
        setNote(value);
        setError(emptyError);
        setNotice(null);
    }, []);

    const saveOverride = useCallback(async () => {
        if (!selectedProject || !draft?.draft_id || !selectedKey || phase === 'saving') return false;
        const value = buildOverrideDelta(fieldValues, initialValues);
        if (Object.keys(value).length === 0) {
            setError({
                code: 'no_changes',
                message: translate('mod_archive.release.draft.errors.no_changes'),
            });
            return false;
        }
        setPhase('saving');
        setError(emptyError);
        setNotice(null);
        try {
            const response = await api.put(
                `${API_BASE_URL}/context/projects/${encodeURIComponent(selectedProject)}/drafts/${encodeURIComponent(draft.draft_id)}/overrides`,
                {
                    context_key: selectedKey,
                    value,
                    note: note.trim() || null,
                },
            );
            const nextDraft = unwrap(response.data, 'draft');
            if (!nextDraft?.draft_id) throw new Error('draft_response_incomplete');
            setDraft(nextDraft);
            applyEditorSnapshot(nextDraft, selectedKey);
            setPhase('ready');
            setNotice({ type: 'saved' });
            return true;
        } catch (requestError) {
            setPhase('ready');
            setError(getContextError(requestError, translate));
            return false;
        }
    }, [applyEditorSnapshot, draft, fieldValues, initialValues, note, phase, selectedKey, selectedProject, translate]);

    const publishDraft = useCallback(async () => {
        if (!selectedProject || !draft?.draft_id || phase === 'publishing') return null;
        setPhase('publishing');
        setError(emptyError);
        setNotice(null);
        try {
            const response = await api.post(
                `${API_BASE_URL}/context/projects/${encodeURIComponent(selectedProject)}/drafts/${encodeURIComponent(draft.draft_id)}/publish`,
            );
            const nextRelease = unwrap(response.data, 'release');
            if (!nextRelease?.release_id) throw new Error('release_response_incomplete');
            setPublishedRelease(nextRelease);
            setDraft(null);
            setSelectedKey('');
            setFieldValues({});
            setInitialValues({});
            setNote('');
            setPhase('published');
            setNotice({ type: 'published', releaseId: nextRelease.release_id });
            await onPublishedRef.current?.(nextRelease);
            return nextRelease;
        } catch (requestError) {
            setPhase('ready');
            setError(getContextError(requestError, translate));
            return null;
        }
    }, [draft, phase, selectedProject, translate]);

    return {
        phase,
        draft,
        selectedKey,
        fieldValues,
        note,
        error,
        notice,
        publishedRelease,
        inheritedOverrides: Array.isArray(draft?.overrides) ? draft.overrides : [],
        startDraft,
        selectContextKey,
        updateField,
        setNote: updateNote,
        saveOverride,
        publishDraft,
    };
};
