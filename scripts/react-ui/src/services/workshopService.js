import api from '../utils/api';

/**
 * Service for Agent Workshop-related API operations.
 */
export const workshopService = {
    /**
     * Scan a project for translation and format errors.
     * @param {string} projectId Project ID
     * @returns {Promise} Axios response promise
     */
    scanProject: (projectId) => api.get(`/api/agent-workshop/scan?project_id=${projectId}`),

    /**
     * Request a targeted fix for a single localized issue.
     * @param {Object} payload Payload containing project_id, api_provider, api_model, and issue details
     * @returns {Promise} Axios response promise
     */
    fixIssue: (payload) => api.post('/api/agent-workshop/fix', payload),

    /**
     * Request a batch fix for multiple localized issues in one API request.
     * @param {Object} payload Payload containing project_id, api_provider, api_model, and list of issues
     * @returns {Promise} Axios response promise
     */
    fixBatch: (payload) => api.post('/api/agent-workshop/fix-batch', payload),

    /**
     * Start a backend-managed run for multiple localized issues.
     * @param {Object} payload Payload containing project_id, provider/model, limits, and issues
     * @returns {Promise} Axios response promise containing a task_id
     */
    startFixRun: (payload) => api.post('/api/agent-workshop/fix-run', payload),
};

export default workshopService;
