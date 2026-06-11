import api from '../utils/api';

const projectWatchService = {
  listWatches: () => api.get('/api/project-watches'),
  createWatch: (payload) => api.post('/api/project-watches', payload),
  updateWatch: (watchId, payload) => api.put(`/api/project-watches/${watchId}`, payload),
  deleteWatch: (watchId) => api.delete(`/api/project-watches/${watchId}`),
  scanWatch: (watchId) => api.post(`/api/project-watches/${watchId}/scan`),
  scanWatches: (watchIds) => api.post('/api/project-watches/scan', { watch_ids: watchIds }),
  scanDueWatches: () => api.post('/api/project-watches/scan-due'),
};

export default projectWatchService;
