import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../utils/api';
import { useModArchiveDraft } from './useModArchiveDraft';

vi.mock('react-i18next', () => ({
    useTranslation: () => ({ t: (key) => key }),
}));

vi.mock('../../utils/api', () => ({
    default: { post: vi.fn(), put: vi.fn() },
}));

const contextEntries = [
    {
        key: 'entity:republic',
        label: 'republic',
        value: { summary: 'A state', preferred_name: '共和国' },
    },
];

const draft = {
    draft_id: 'draft-1',
    project_id: 'project-1',
    base_release_id: 'release-1',
    status: 'draft',
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
    overrides: [{
        target_key: 'entity:republic',
        value: { preferred_name: '共和国', unknown_field: 'preserved' },
        note: 'Inherited note',
    }],
};

const childRelease = {
    release_id: 'release-2',
    project_id: 'project-1',
    metadata: { parent_release_id: 'release-1' },
};

const renderDraft = (onPublished = vi.fn()) => renderHook(() => useModArchiveDraft({
    selectedProject: 'project-1',
    baseReleaseId: 'release-1',
    contextEntries,
    onPublished,
}));

describe('useModArchiveDraft', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('starts from the displayed release and exposes inherited values without an edit API call', async () => {
        api.post.mockResolvedValue({ data: draft });
        const { result } = renderDraft();

        await act(async () => {
            await result.current.startDraft();
        });

        expect(api.post).toHaveBeenCalledWith(
            '/api/context/projects/project-1/releases/release-1/drafts',
        );
        expect(result.current.phase).toBe('ready');
        expect(result.current.draft.draft_id).toBe('draft-1');
        expect(result.current.inheritedOverrides[0].target_key).toBe('entity:republic');
        expect(result.current.fieldValues.preferred_name).toBe('共和国');
        expect(result.current.fieldValues.unknown_field).toBeUndefined();
    });

    it('saves only changed supported fields and keeps the note separate from structured values', async () => {
        api.post.mockResolvedValue({ data: draft });
        api.put.mockResolvedValue({ data: draft });
        const { result } = renderDraft();
        await act(async () => result.current.startDraft());

        act(() => {
            result.current.updateField('preferred_name', 'The Republic');
            result.current.setNote('Confirmed by the project glossary.');
        });
        await act(async () => {
            await result.current.saveOverride();
        });

        expect(api.put).toHaveBeenCalledWith(
            '/api/context/projects/project-1/drafts/draft-1/overrides',
            {
                context_key: 'entity:republic',
                value: { preferred_name: 'The Republic', unknown_field: 'preserved' },
                note: 'Confirmed by the project glossary.',
            },
        );
        expect(result.current.notice).toEqual({ type: 'saved' });
    });

    it('surfaces a structured error code without echoing backend input', async () => {
        api.post.mockRejectedValue({
            response: {
                data: {
                    detail: {
                        code: 'context_key_not_found',
                        message: 'missing key=secret-user-input',
                    },
                },
            },
        });
        const { result } = renderDraft();

        await act(async () => {
            await result.current.startDraft();
        });

        expect(result.current.error).toEqual({
            code: 'context_key_not_found',
            message: 'mod_archive.release.draft.errors.context_key_not_found',
        });
        expect(JSON.stringify(result.current.error)).not.toContain('secret-user-input');
        expect(result.current.phase).toBe('idle');
    });

    it('keeps a draft open and maps a bounded save error without echoing the rejected value', async () => {
        api.post.mockResolvedValue({ data: draft });
        api.put.mockRejectedValue({
            response: {
                data: {
                    detail: {
                        code: 'context_override_invalid',
                        message: 'value=secret-user-input',
                    },
                },
            },
        });
        const { result } = renderDraft();
        await act(async () => result.current.startDraft());
        act(() => result.current.updateField('summary', 'Human correction'));

        await act(async () => {
            await result.current.saveOverride();
        });

        expect(result.current.phase).toBe('ready');
        expect(result.current.error.code).toBe('context_override_invalid');
        expect(JSON.stringify(result.current.error)).not.toContain('secret-user-input');
    });

    it('publishes through the draft endpoint and hands the child release to the refresh controller', async () => {
        const onPublished = vi.fn().mockResolvedValue(undefined);
        api.put.mockResolvedValue({ data: draft });
        api.post
            .mockResolvedValueOnce({ data: draft })
            .mockResolvedValueOnce({ data: childRelease });
        const { result } = renderDraft(onPublished);
        await act(async () => result.current.startDraft());
        act(() => result.current.updateField('summary', 'Human correction'));
        await act(async () => result.current.saveOverride());

        await act(async () => {
            await result.current.publishDraft();
        });

        expect(api.post).toHaveBeenNthCalledWith(
            2,
            '/api/context/projects/project-1/drafts/draft-1/publish',
        );
        expect(onPublished).toHaveBeenCalledWith(childRelease);
        expect(result.current.phase).toBe('published');
        expect(result.current.draft).toBeNull();
        expect(result.current.publishedRelease.release_id).toBe('release-2');
    });

    it('does not send an empty override when a user attempts to clear a value', async () => {
        api.post.mockResolvedValue({ data: draft });
        const { result } = renderDraft();
        await act(async () => result.current.startDraft());

        act(() => result.current.updateField('preferred_name', ''));
        await act(async () => {
            await result.current.saveOverride();
        });

        expect(api.put).not.toHaveBeenCalled();
        expect(result.current.error.code).toBe('no_changes');
    });

    it('does not send a note without a structured override value', async () => {
        api.post.mockResolvedValue({ data: { ...draft, overrides: [] } });
        const { result } = renderDraft();
        await act(async () => result.current.startDraft());

        act(() => result.current.setNote('A note cannot stand alone.'));
        await act(async () => result.current.saveOverride());

        expect(api.put).not.toHaveBeenCalled();
        expect(result.current.error.code).toBe('no_changes');
    });

    it('preserves earlier and unknown override fields across repeated saves', async () => {
        api.post.mockResolvedValue({ data: draft });
        api.put.mockImplementation((_url, payload) => Promise.resolve({
            data: {
                ...draft,
                overrides: [{
                    target_key: payload.context_key,
                    value: payload.value,
                    note: payload.note,
                }],
            },
        }));
        const { result } = renderDraft();
        await act(async () => result.current.startDraft());

        act(() => result.current.updateField('preferred_name', 'The Republic'));
        await act(async () => result.current.saveOverride());
        act(() => result.current.updateField('summary', 'A revised state summary'));
        await act(async () => result.current.saveOverride());

        expect(api.put).toHaveBeenLastCalledWith(
            '/api/context/projects/project-1/drafts/draft-1/overrides',
            {
                context_key: 'entity:republic',
                value: {
                    preferred_name: 'The Republic',
                    unknown_field: 'preserved',
                    summary: 'A revised state summary',
                },
                note: 'Inherited note',
            },
        );
    });
});
