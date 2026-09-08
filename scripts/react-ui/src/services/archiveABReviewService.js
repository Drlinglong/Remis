import api from '../utils/api';

const cleanParams = (params = {}) => Object.fromEntries(
  Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined),
);

const archiveABReviewService = {
  async getStatus() {
    const response = await api.get('/api/archive-ab-review/status');
    return response.data;
  },

  async loadCases(params = {}, { signal } = {}) {
    const response = await api.get('/api/archive-ab-review/cases', { params: cleanParams(params), signal });
    return response.data;
  },

  async submitReview(payload) {
    const response = await api.post('/api/archive-ab-review/reviews', payload);
    return response.data;
  },

  async loadHistory(params = {}) {
    const response = await api.get('/api/archive-ab-review/reviews', { params: cleanParams(params) });
    return response.data;
  },

  async loadSummary(params = {}) {
    const response = await api.get('/api/archive-ab-review/summary', { params: cleanParams(params) });
    return response.data;
  },
};

export default archiveABReviewService;
