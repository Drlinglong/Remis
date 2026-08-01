import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { pollAgentWorkshopRun } from './agentWorkshopRunMonitor';
import { useAgentWorkshopRunController } from './useAgentWorkshopRunController';
import { startAgentWorkshopFixRun } from '../services/agentWorkshopWorkflowService';

vi.mock('./agentWorkshopRunMonitor', () => ({
  pollAgentWorkshopRun: vi.fn(),
}));

vi.mock('../services/agentWorkshopWorkflowService', () => ({
  createAgentWorkshopIdempotencyKey: vi.fn(() => 'run-key'),
  getAgentWorkshopRunStatus: vi.fn(),
  isRepairableAgentWorkshopIssue: (issue) => (
    ![issue?.error_code, issue?.error_type].includes('validation_invalid_key_format')
  ),
  startAgentWorkshopFixRun: vi.fn(),
}));

const repairableIssue = {
  file_name: 'events.yml',
  key: 'repair_me',
  error_type: 'validation_error',
};
const manualIssue = {
  file_name: 'events.yml',
  key: 'invalid key',
  error_code: 'validation_invalid_key_format',
};

const createOptions = (overrides = {}) => ({
  baseSessionState: {
    active: 2,
    selectedProjectId: 'project-1',
    issues: [repairableIssue, manualIssue],
  },
  issues: [repairableIssue, manualIssue],
  restoredRef: { current: true },
  selectedModel: 'google/gemma-4-31b-qat',
  selectedProjectId: 'project-1',
  selectedProvider: 'lm_studio',
  setActive: vi.fn(),
  setFixedIssues: vi.fn(),
  setIssues: vi.fn(),
  setWorkflowError: vi.fn(),
  t: (_key, options) => options.defaultValue,
  ...overrides,
});

describe('useAgentWorkshopRunController', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it('requires approval before starting and sends only repairable issues', async () => {
    const options = createOptions();
    startAgentWorkshopFixRun.mockResolvedValue({ task_id: 'task-1' });
    pollAgentWorkshopRun.mockImplementation(async ({ onTask }) => {
      onTask({
        task_id: 'task-1',
        status: 'completed',
        progress: { percent: 100 },
        summary: {
          total: 1,
          completed: 1,
          successCount: 1,
          failedCount: 0,
          results: [{ ...repairableIssue, status: 'SUCCESS' }],
        },
      });
    });

    const { result } = renderHook(() => useAgentWorkshopRunController(options));

    act(() => result.current.requestFixRunApproval());
    expect(result.current.approvalOpen).toBe(true);
    expect(startAgentWorkshopFixRun).not.toHaveBeenCalled();

    await act(async () => {
      await result.current.executeFixRun();
    });

    expect(startAgentWorkshopFixRun).toHaveBeenCalledWith(expect.objectContaining({
      idempotencyKey: 'run-key',
      issues: [repairableIssue],
      projectId: 'project-1',
      selectedModel: 'google/gemma-4-31b-qat',
      selectedProvider: 'lm_studio',
    }));
    expect(options.setActive).toHaveBeenCalledWith(3);
    expect(options.setFixedIssues).toHaveBeenCalledWith(expect.any(Function));
    expect(options.setIssues).toHaveBeenCalledWith(expect.any(Function));
    const applyFixedIssues = options.setFixedIssues.mock.calls.at(-1)[0];
    const applyRemainingIssues = options.setIssues.mock.calls.at(-1)[0];
    expect(applyFixedIssues([])).toEqual([
      expect.objectContaining({ key: 'repair_me', status: 'SUCCESS' }),
    ]);
    expect(applyRemainingIssues([repairableIssue, manualIssue])).toEqual([manualIssue]);
    expect(result.current.executing).toBe(false);
    expect(result.current.progress).toBe(100);
  });

  it('restores a persisted run and resumes its task monitor', async () => {
    const options = createOptions();
    pollAgentWorkshopRun.mockResolvedValue(null);
    const { result } = renderHook(() => useAgentWorkshopRunController(options));

    act(() => {
      result.current.restoreRunState({
        batchSizeLimit: '3',
        concurrencyLimit: '2',
        rpmLimit: '120',
        executing: true,
        progress: 40,
        executionLogs: ['running'],
        currentRunTaskId: 'task-resume',
      }, '10');
    });

    await waitFor(() => {
      expect(pollAgentWorkshopRun).toHaveBeenCalledWith(expect.objectContaining({
        taskId: 'task-resume',
      }));
    });
    expect(result.current.batchSizeLimit).toBe('3');
    expect(result.current.concurrencyLimit).toBe('2');
    expect(result.current.rpmLimit).toBe('120');
    expect(result.current.progress).toBe(40);
  });
});
