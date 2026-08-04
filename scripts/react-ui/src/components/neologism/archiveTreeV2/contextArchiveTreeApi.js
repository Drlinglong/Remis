import api from '../../../utils/api';

const encode = (value) => encodeURIComponent(String(value || ''));

const defaultEndpoints = Object.freeze({
    load: ({ projectId, releaseId, draftId, mode = 'published' }) => {
        if (draftId) return `/api/context/projects/${encode(projectId)}/drafts/${encode(draftId)}/tree`;
        if (releaseId) return `/api/context/releases/${encode(releaseId)}/tree`;
        return `/api/context/projects/${encode(projectId)}/tree?mode=${encode(mode)}`;
    },
    save: ({ projectId, releaseId, draftId }) => {
        if (draftId) return `/api/context/projects/${encode(projectId)}/drafts/${encode(draftId)}/tree`;
        return `/api/context/projects/${encode(projectId)}/releases/${encode(releaseId)}/tree-draft`;
    },
});

const unwrap = (response) => response?.data?.tree
    || response?.data?.context_tree_v2
    || response?.data?.context_tree
    || response?.data
    || response;

export const createContextArchiveTreeApi = ({ client = api, endpoints = {} } = {}) => {
    const paths = { ...defaultEndpoints, ...endpoints };
    return {
        async load(context) {
            const response = await client.get(paths.load(context));
            return unwrap(response);
        },
        async save({ tree, ...context }) {
            const response = await client.put(paths.save(context), { tree });
            return unwrap(response);
        },
    };
};

export { defaultEndpoints as contextArchiveTreeEndpoints };
