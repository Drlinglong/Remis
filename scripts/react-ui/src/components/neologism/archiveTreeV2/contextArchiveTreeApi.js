import api from '../../../utils/api';

const encode = (value) => encodeURIComponent(String(value || ''));

const defaultEndpoints = Object.freeze({
    load: ({ projectId, releaseId, mode = 'published' }) => {
        if (releaseId) return `/api/context/tree-v2/projects/${encode(projectId)}/releases/${encode(releaseId)}`;
        return `/api/context/tree-v2/projects/${encode(projectId)}/${mode === 'published' ? 'latest-release' : 'latest'}`;
    },
    createDraft: ({ projectId, treeId }) => `/api/context/tree-v2/projects/${encode(projectId)}/trees/${encode(treeId)}/drafts`,
    saveOperations: ({ projectId, draftId }) => `/api/context/tree-v2/projects/${encode(projectId)}/drafts/${encode(draftId)}/operations/batch`,
    readDraftTree: ({ projectId, treeId, draftId }) => `/api/context/tree-v2/projects/${encode(projectId)}/trees/${encode(treeId)}?draft_id=${encode(draftId)}`,
});

const unwrap = (response) => response?.data?.tree
    || response?.data?.context_tree_v2
    || response?.data?.context_tree
    || response?.data
    || response;

export const createContextArchiveTreeApi = ({ client = api, endpoints = {} } = {}) => {
    const paths = { ...defaultEndpoints, ...endpoints };
    let activeDraftId = null;
    return {
        async load(context) {
            const response = await client.get(paths.load(context));
            return unwrap(response);
        },
        async save({ tree, operations = [], ...context }) {
            const treeId = tree?.tree_id || tree?.treeId;
            let draftId = context.draftId || tree?.draft_id || activeDraftId;
            if (!draftId) {
                const created = await client.post(paths.createDraft({ ...context, treeId }));
                draftId = created?.data?.draft_id || created?.draft_id;
                activeDraftId = draftId;
            }
            if (operations.length > 0) {
                await client.post(paths.saveOperations({ ...context, draftId }), operations);
            }
            const response = await client.get(paths.readDraftTree({ ...context, treeId, draftId }));
            return unwrap(response);
        },
    };
};

export { defaultEndpoints as contextArchiveTreeEndpoints };
