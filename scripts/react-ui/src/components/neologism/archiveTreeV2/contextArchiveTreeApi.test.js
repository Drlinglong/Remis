import { describe, expect, it, vi } from 'vitest';

import { createContextArchiveTreeApi } from './contextArchiveTreeApi';

describe('context archive tree API adapter', () => {
    it('keeps endpoint selection injectable for future v2 backend integration', async () => {
        const client = {
            get: vi.fn().mockResolvedValue({ data: { tree: { schema_version: 'context-tree-v2' } } }),
            put: vi.fn().mockResolvedValue({ data: { tree: { schema_version: 'context-tree-v2' } } }),
        };
        const adapter = createContextArchiveTreeApi({
            client,
            endpoints: {
                load: ({ releaseId }) => `/v2/releases/${releaseId}/tree`,
                save: ({ draftId }) => `/v2/drafts/${draftId}/tree`,
            },
        });

        await adapter.load({ releaseId: 'release-1' });
        await adapter.save({ draftId: 'draft-1', tree: { stories: [] } });

        expect(client.get).toHaveBeenCalledWith('/v2/releases/release-1/tree');
        expect(client.put).toHaveBeenCalledWith('/v2/drafts/draft-1/tree', { tree: { stories: [] } });
    });
});
