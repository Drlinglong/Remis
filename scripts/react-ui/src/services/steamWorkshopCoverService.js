import api, { resolveApiUrl } from '../utils/api';

const base64Payload = (dataUrl) => dataUrl.includes(',') ? dataUrl.split(',', 2)[1] : dataUrl;

export const steamWorkshopCoverService = {
    getProjectThumbnailUrl: (workspaceId) => (
        resolveApiUrl(`/api/steam-workshop/workspaces/${workspaceId}/project-thumbnail`)
    ),

    resolveMediaUrl: resolveApiUrl,

    listVersions: async (workspaceId) => {
        const response = await api.get(
            `/api/steam-workshop/workspaces/${workspaceId}/versions`,
            { params: { asset_type: 'cover' } },
        );
        return response.data;
    },

    getVersion: async (versionId) => {
        const response = await api.get(`/api/steam-workshop/versions/${versionId}`);
        return response.data;
    },

    createVersion: async (workspaceId, { pngDataUrl, canvas, parentVersionId = null }) => {
        const response = await api.post(
            `/api/steam-workshop/workspaces/${workspaceId}/versions/cover`,
            {
                png_base64: base64Payload(pngDataUrl),
                canvas,
                source: 'manual',
                parent_version_id: parentVersionId,
                metadata: { editor: 'remis-cover-editor', canvas_schema_version: canvas.schema_version },
            },
        );
        return response.data;
    },

    selectVersion: async (workspaceId, versionId) => {
        const response = await api.post(
            `/api/steam-workshop/workspaces/${workspaceId}/selections/cover`,
            { version_id: versionId },
        );
        return response.data;
    },
};

export default steamWorkshopCoverService;
