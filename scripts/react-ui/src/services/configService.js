import api from '../utils/api';

/**
 * Service for system and model configuration API operations.
 */
export const configService = {
    /**
     * Fetch global configuration including API providers, default model, and system limits.
     * @returns {Promise} Axios response promise
     */
    getConfig: () => api.get('/api/config'),
};

export default configService;
