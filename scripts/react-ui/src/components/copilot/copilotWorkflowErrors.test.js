import { describe, expect, it } from 'vitest';

import { getCopilotWorkflowError, isInvalidCopilotApprovalError } from './copilotWorkflowErrors';

describe('Copilot workflow approval errors', () => {
  it('uses the server-owned machine code for stale approval plans', () => {
    const error = {
      response: {
        status: 409,
        data: { detail: { code: 'workflow_plan_stale', message: 'stale' } },
      },
    };

    expect(getCopilotWorkflowError(error)).toMatchObject({
      code: 'workflow_plan_stale',
      invalidApproval: true,
      message: 'stale',
    });
    expect(isInvalidCopilotApprovalError(error)).toBe(true);
  });

  it('keeps compatibility with lifecycle status responses while codes roll out', () => {
    expect(isInvalidCopilotApprovalError({ response: { status: 410, data: { detail: 'expired' } } })).toBe(true);
    expect(isInvalidCopilotApprovalError({ response: { status: 404, data: { detail: 'missing' } } })).toBe(true);
    expect(isInvalidCopilotApprovalError({ response: { status: 500, data: { detail: 'server error' } } })).toBe(false);
  });
});
