import { describe, expect, it, vi } from 'vitest';

import { createContextArchiveTreeApi } from './contextArchiveTreeApi';

describe('context archive tree API adapter', () => {
    it('keeps endpoint selection injectable for future v2 backend integration', async () => {
        const client = {
            get: vi.fn().mockResolvedValue({ data: { tree: { schema_version: 'context-tree-v2' } } }),
            post: vi.fn()
                .mockResolvedValueOnce({ data: { draft_id: 'draft-1' } })
                .mockResolvedValueOnce({ data: { applied: 1 } }),
        };
        const adapter = createContextArchiveTreeApi({
            client,
            endpoints: {
                load: ({ releaseId }) => `/v2/releases/${releaseId}/tree`,
                createDraft: ({ treeId }) => `/v2/trees/${treeId}/drafts`,
                saveOperations: ({ draftId }) => `/v2/drafts/${draftId}/operations`,
                readDraftTree: ({ treeId, draftId }) => `/v2/trees/${treeId}?draft_id=${draftId}`,
            },
        });

        await adapter.load({ releaseId: 'release-1' });
        await adapter.save({
            projectId: 'project-1',
            tree: { tree_id: 'tree-1', stories: [] },
            operations: [{ operation: 'rename_story', story_id: 'story-1', new_name: 'Next' }],
        });

        expect(client.get).toHaveBeenCalledWith('/v2/releases/release-1/tree');
        expect(client.post).toHaveBeenNthCalledWith(1, '/v2/trees/tree-1/drafts');
        expect(client.post).toHaveBeenNthCalledWith(2, '/v2/drafts/draft-1/operations', [
            { operation: 'rename_story', story_id: 'story-1', new_name: 'Next' },
        ]);
        expect(client.get).toHaveBeenCalledWith('/v2/trees/tree-1?draft_id=draft-1');
    });
});
