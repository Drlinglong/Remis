import { describe, expect, it } from 'vitest';
import {
    coverDraftStorageKey,
    readCoverDraft,
    serializeCoverCanvas,
    writeCoverDraft,
} from './coverCanvasState';

describe('cover canvas persistence', () => {
    it('serializes editable image sources without retaining DOM image objects', () => {
        const canvas = serializeCoverCanvas({
            backgroundColor: '#123456',
            backgroundImage: {
                image: { src: 'data:image/png;base64,background' },
                x: 1,
                y: 2,
                width: 100,
                height: 80,
            },
            elements: [{
                id: 'logo',
                type: 'image',
                image: { src: 'data:image/png;base64,logo' },
                x: 20,
                y: 30,
                width: 40,
                height: 50,
            }],
        });

        expect(canvas).toMatchObject({
            schema_version: 1,
            width: 512,
            height: 512,
            backgroundColor: '#123456',
            backgroundImage: { src: 'data:image/png;base64,background' },
            elements: [{ id: 'logo', src: 'data:image/png;base64,logo' }],
        });
        expect(canvas.backgroundImage).not.toHaveProperty('image');
        expect(canvas.elements[0]).not.toHaveProperty('image');
    });

    it('isolates local drafts by workspace before project context', () => {
        const values = new Map();
        const storage = {
            getItem: (key) => values.get(key) ?? null,
            setItem: (key, value) => values.set(key, value),
        };
        const context = { workspaceId: 'workspace-7', projectId: 'project-4' };
        const canvas = { schema_version: 1, elements: [] };

        writeCoverDraft(storage, context, canvas);

        expect(coverDraftStorageKey(context)).toContain('workspace:workspace-7');
        expect(readCoverDraft(storage, context)).toEqual(canvas);
        expect(readCoverDraft(storage, { projectId: 'project-4' })).toBeNull();
    });
});
