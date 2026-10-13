import api from '../utils/api';

const base = (workspaceId) => `/api/steam-workshop/workspaces/${encodeURIComponent(workspaceId)}/publication`;
const unwrap = async (request) => (await request).data;

export const workshopPublicationService = {
  options: (workspaceId) => unwrap(api.get(`${base(workspaceId)}/options`)),
  history: (workspaceId) => unwrap(api.get(`${base(workspaceId)}/plans`)),
  plan: (workspaceId, request) => unwrap(api.post(`${base(workspaceId)}/plans`, request)),
  inspect: (workspaceId, planId) => unwrap(api.get(`${base(workspaceId)}/plans/${encodeURIComponent(planId)}`)),
  submit: (workspaceId, plan) => unwrap(api.post(`${base(workspaceId)}/plans/${encodeURIComponent(plan.plan_id)}/submit`, {
    approved: true,
    fingerprint: plan.fingerprint,
  })),
  verify: (workspaceId, planId, request) => unwrap(api.post(`${base(workspaceId)}/plans/${encodeURIComponent(planId)}/verify`, request)),
};
