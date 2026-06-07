import api from '../utils/api';

/**
 * Service for translation and incremental update API operations.
 */
export const translationService = {
    /**
     * Check current checkpoint status for a project and given languages to support resume.
     * @param {Object} payload Payload containing project_id, mod_name, target_lang_codes
     * @returns {Promise} Axios response promise
     */
    getCheckpointStatus: (payload) => api.post('/api/translation/checkpoint-status', payload),

    /**
     * Trigger an incremental translation update or Dry Run pre-scan.
     * @param {string} projectId Project ID
     * @param {Object} payload Configuration options including providers, concurrency, dry_run, resume, etc.
     * @returns {Promise} Axios response promise
     */
    startIncrementalUpdate: (projectId, payload) => api.post(`/api/project/${projectId}/incremental-update`, payload),

    /**
     * Request backend system to open a local folder directory.
     * @param {string} folderPath Local directory path
     * @returns {Promise} Axios response promise
     */
    openFolder: (folderPath) => api.post('/api/system/open_folder', { path: folderPath }),
};

export default translationService;
