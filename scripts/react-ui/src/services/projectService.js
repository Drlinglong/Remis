import api from '../utils/api';

/**
 * Service for project-related API operations.
 */
export const projectService = {
    /**
     * Fetch all active projects.
     * @returns {Promise} Axios response promise
     */
    getActiveProjects: () => api.get('/api/projects?status=active'),

    /**
     * Fetch projects filtered by status (active | archived | deleted).
     * @param {string} status Project status
     * @returns {Promise} Axios response promise
     */
    getProjectsByStatus: (status) => api.get(`/api/projects?status=${status}`),

    /**
     * Fetch all files belonging to a specific project.
     * @param {string} projectId Project ID
     * @returns {Promise} Axios response promise
     */
    getProjectFiles: (projectId) => api.get(`/api/project/${projectId}/files`),

    /**
     * Fetch the configuration profile for a specific project.
     * @param {string} projectId Project ID
     * @returns {Promise} Axios response promise
     */
    getProjectConfig: (projectId) => api.get(`/api/project/${projectId}/config`),

    /**
     * Check if a project localization archive exists.
     * @param {string} projectId Project ID
     * @returns {Promise} Axios response promise
     */
    checkArchive: (projectId) => api.get(`/api/project/${projectId}/check-archive`),

    /**
     * Retrieve status and progress of a background task.
     * @param {string} taskId Task ID
     * @returns {Promise} Axios response promise
     */
    getTaskStatus: (taskId) => api.get(`/api/status/${taskId}`),

    /**
     * Fetch translation and update history logs for a project.
     * @param {string} projectId Project ID
     * @returns {Promise} Axios response promise
     */
    getProjectHistory: (projectId) => api.get(`/api/project/${projectId}/history`),

    /**
     * Create a new Mod project.
     * @param {Object} payload Project details (name, folder_path, game_id, source_language, import_mode)
     * @returns {Promise} Axios response promise
     */
    createProject: (payload) => api.post('/api/project/create', payload),

    /**
     * Update project notes text.
     * @param {string} projectId Project ID
     * @param {Object} payload Object containing { notes }
     * @returns {Promise} Axios response promise
     */
    updateProjectNotes: (projectId, payload) => api.post(`/api/project/${projectId}/notes`, payload),

    /**
     * Update the global status of a project (active | archived | deleted).
     * @param {string} projectId Project ID
     * @param {Object} payload Object containing { status }
     * @returns {Promise} Axios response promise
     */
    updateProjectStatus: (projectId, payload) => api.post(`/api/project/${projectId}/status`, payload),

    /**
     * Update status metadata for a specific file (todo | proofreading | done).
     * @param {string} projectId Project ID
     * @param {string} fileId File ID
     * @param {Object} payload Object containing { status }
     * @returns {Promise} Axios response promise
     */
    updateFileStatus: (projectId, fileId, payload) => api.put(`/api/project/${projectId}/file/${fileId}/status`, payload),

    /**
     * Update project metadata (game_id, source_language).
     * @param {string} projectId Project ID
     * @param {Object} payload Object containing { game_id, source_language }
     * @returns {Promise} Axios response promise
     */
    updateProjectMetadata: (projectId, payload) => api.post(`/api/project/${projectId}/metadata`, payload),

    /**
     * Permanently delete a project, optionally deleting its physical workspace.
     * @param {string} projectId Project ID
     * @param {boolean} deleteSourceFiles Whether to delete the project folder physically
     * @returns {Promise} Axios response promise
     */
    deleteProject: (projectId, deleteSourceFiles) => api.delete(`/api/project/${projectId}?delete_files=${deleteSourceFiles}`),

    /**
     * Trigger a refresh scanning on project directory to re-index localization files.
     * @param {string} projectId Project ID
     * @returns {Promise} Axios response promise
     */
    refreshProjectFiles: (projectId) => api.post(`/api/project/${projectId}/refresh`),
};

export default projectService;
