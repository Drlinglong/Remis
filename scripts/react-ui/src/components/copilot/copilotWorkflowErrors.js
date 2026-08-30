const INVALID_APPROVAL_CODES = new Set([
  'approval_plan_stale',
  'plan_stale',
  'workflow_plan_stale',
  'approval_plan_expired',
  'plan_expired',
  'workflow_plan_expired',
  'approval_plan_restarted',
  'plan_restarted',
  'workflow_plan_restarted',
  'plan_not_found',
  'workflow_plan_not_found',
  'plan_already_used',
  'workflow_plan_already_used',
]);

const INVALID_APPROVAL_STATUSES = new Set([404, 409, 410]);

function detailFrom(error) {
  const responseData = error?.response?.data;
  const detail = responseData?.detail;
  if (detail && typeof detail === 'object') return detail;
  if (responseData && typeof responseData === 'object' && responseData.code) return responseData;
  return { message: typeof detail === 'string' ? detail : error?.message };
}

export function getCopilotWorkflowError(error) {
  const detail = detailFrom(error);
  const code = typeof detail.code === 'string' ? detail.code : '';
  const status = error?.response?.status;
  const invalidApproval = Boolean(
    (code && INVALID_APPROVAL_CODES.has(code))
      || (!code && INVALID_APPROVAL_STATUSES.has(status)),
  );
  return {
    code,
    invalidApproval,
    message: detail.message || error?.message || String(error),
    status,
  };
}

export function isInvalidCopilotApprovalError(error) {
  return getCopilotWorkflowError(error).invalidApproval;
}
