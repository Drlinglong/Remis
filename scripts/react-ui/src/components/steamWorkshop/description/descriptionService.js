import api from '../../../utils/api';

const BASE_URL = '/api/steam-workshop';

const unwrap = (response) => response.data;

export const listPublishingWorkspaces = async ({ projectId } = {}) => unwrap(
  await api.get(`${BASE_URL}/workspaces`, {
    params: projectId ? { project_id: projectId } : undefined,
  }),
);

export const getPublishingWorkspace = async (workspaceId) => unwrap(
  await api.get(`${BASE_URL}/workspaces/${workspaceId}`),
);

export const createPublishingWorkspace = async (payload) => unwrap(
  await api.post(`${BASE_URL}/workspaces`, payload),
);

export const updatePublishingWorkspace = async (workspaceId, payload) => unwrap(
  await api.patch(`${BASE_URL}/workspaces/${workspaceId}`, payload),
);

export const listDescriptionVersions = async (workspaceId) => unwrap(
  await api.get(`${BASE_URL}/workspaces/${workspaceId}/versions`, {
    params: { asset_type: 'description' },
  }),
);

export const createDescriptionVersion = async (workspaceId, payload) => unwrap(
  await api.post(`${BASE_URL}/workspaces/${workspaceId}/versions/description`, payload),
);

export const selectDescriptionVersion = async (workspaceId, versionId) => unwrap(
  await api.post(`${BASE_URL}/workspaces/${workspaceId}/selections/description`, {
    version_id: versionId,
  }),
);

export const generateDescriptionCandidate = async (workspaceId, payload) => unwrap(
  await api.post(`${BASE_URL}/workspaces/${workspaceId}/generate-description`, payload),
);
