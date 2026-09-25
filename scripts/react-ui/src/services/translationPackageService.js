import api from '../utils/api';

const projectUrl = (projectId) => `/api/projects/${encodeURIComponent(projectId)}/translation-package`;

const translationPackageService = {
  getOptions: (projectId, config = {}) => api.get(`${projectUrl(projectId)}/options`, config),
  createPlan: (projectId, payload) => api.post(`${projectUrl(projectId)}/plan`, payload),
  createPackage: (projectId, payload) => api.post(projectUrl(projectId), payload),
};

export default translationPackageService;
