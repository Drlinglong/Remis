import api from '../utils/api';

const base = '/api/mars-pipeline';
const project = (id) => `/api/projects/${encodeURIComponent(id)}/mars-pipeline`;
export default {
  planImport: (payload) => api.post(`${base}/prepare/plan`, payload),
  import: (planId) => api.post(`${base}/prepare`, { plan_id: planId, approved: true }),
  options: (id, config) => api.get(project(id), config),
  publication: (id, config) => api.get(`${project(id)}/publication`, config),
  bindPublication: (id, payload, config) => api.put(`${project(id)}/publication`, payload, config),
  planExport: (id, payload) => api.post(`${project(id)}/export/plan`, payload),
  export: (id, planId) => api.post(`${project(id)}/export`, { plan_id: planId, approved: true }),
};
