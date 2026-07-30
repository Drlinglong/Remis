import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createAgentWorkshopIdempotencyKey,
  getAgentWorkshopRunStatus,
  loadAgentWorkshopBootstrap,
  requestAgentWorkshopIssueFix,
  scanAgentWorkshopProject,
  selectAgentWorkshopProvider,
  startAgentWorkshopFixRun,
} from './agentWorkshopWorkflowService';
import configService from './configService';
import projectService from './projectService';
import workshopService from './workshopService';

vi.mock('./configService', () => ({
  default: {
    getConfig: vi.fn(),
  },
}));

vi.mock('./projectService', () => ({
  default: {
    getTaskStatus: vi.fn(),
    getActiveProjects: vi.fn(),
  },
}));

vi.mock('./workshopService', () => ({
  default: {
    fixBatch: vi.fn(),
    fixIssue: vi.fn(),
    scanProject: vi.fn(),
    startFixRun: vi.fn(),
  },
}));

describe('agentWorkshopWorkflowService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('normalizes bootstrap project and provider payloads', async () => {
    projectService.getActiveProjects.mockResolvedValue({
      data: { projects: [{ project_id: 'project-1' }] },
    });
    configService.getConfig.mockResolvedValue({
      data: { api_providers: { items: [{ value: 'gemini' }] } },
    });

    await expect(loadAgentWorkshopBootstrap()).resolves.toEqual({
      projects: [{ project_id: 'project-1' }],
      providers: [{ value: 'gemini' }],
    });
  });

  it('selects a local provider with conservative batch defaults', () => {
    expect(selectAgentWorkshopProvider({
      providers: [
        { value: 'gemini', selected_model: 'gemini-pro', available_models: ['gemini-pro'] },
        { value: 'ollama', selected_model: 'llama3', available_models: ['llama3'] },
      ],
      providerValue: 'ollama',
    })).toEqual({
      selectedProvider: 'ollama',
      selectedModel: 'llama3',
      batchSizeLimit: '3',
    });
  });

  it('normalizes scan result wrappers into issue arrays', async () => {
    workshopService.scanProject.mockResolvedValue({
      data: { issues: [{ key: 'issue-1' }] },
      headers: { 'x-remis-task-id': 'scan-task-1' },
    });

    await expect(scanAgentWorkshopProject('project-1')).resolves.toEqual({
      issues: [{ key: 'issue-1' }],
      taskId: 'scan-task-1',
    });
    expect(workshopService.scanProject).toHaveBeenCalledWith('project-1', null);
  });

  it('passes selected validation sidecar through scan requests', async () => {
    workshopService.scanProject.mockResolvedValue({
      data: [{ key: 'issue-1' }],
    });

    await expect(scanAgentWorkshopProject('project-1', 'C:/mods/out/workshop_issues.json')).resolves.toEqual({
      issues: [{ key: 'issue-1' }],
      taskId: null,
    });
    expect(workshopService.scanProject).toHaveBeenCalledWith('project-1', 'C:/mods/out/workshop_issues.json');
  });

  it('starts backend-managed fix runs instead of running frontend workers', async () => {
    workshopService.startFixRun.mockResolvedValue({
      data: { task_id: 'task-1', status: 'started' },
    });

    await expect(startAgentWorkshopFixRun({
      batchSizeLimit: '10',
      concurrencyLimit: '1',
      issues: [{ file_name: 'a.yml', key: 'k1' }],
      projectId: 'project-1',
      rpmLimit: '60',
      selectedModel: 'gemini-pro',
      selectedProvider: 'gemini',
      idempotencyKey: 'agent-workshop:project-1:test',
    })).resolves.toEqual({ task_id: 'task-1', status: 'started' });

    expect(workshopService.startFixRun).toHaveBeenCalledWith(expect.objectContaining({
      api_model: 'gemini-pro',
      api_provider: 'gemini',
      batch_size_limit: 10,
      concurrency_limit: 1,
      project_id: 'project-1',
      rpm_limit: 60,
      approval: {
        approved: true,
        issue_count: 1,
        api_provider: 'gemini',
        api_model: 'gemini-pro',
      },
      idempotency_key: 'agent-workshop:project-1:test',
      created_by: { type: 'user' },
    }));
    expect(workshopService.fixBatch).not.toHaveBeenCalled();
  });

  it('excludes invalid keys from model-backed batch repair', async () => {
    workshopService.startFixRun.mockResolvedValue({
      data: { task_id: 'task-1', status: 'started' },
    });

    await startAgentWorkshopFixRun({
      batchSizeLimit: '10',
      concurrencyLimit: '1',
      issues: [
        { file_name: 'a.yml', key: 'broken key', error_code: 'validation_invalid_key_format' },
        { file_name: 'a.yml', key: 'valid.key', error_code: 'validation_variable_parity_mismatch' },
      ],
      projectId: 'project-1',
      rpmLimit: '60',
      selectedModel: 'gemini-pro',
      selectedProvider: 'gemini',
      idempotencyKey: 'agent-workshop:project-1:test',
    });

    expect(workshopService.startFixRun).toHaveBeenCalledWith(expect.objectContaining({
      issues: [expect.objectContaining({ key: 'valid.key' })],
      approval: expect.objectContaining({ issue_count: 1 }),
    }));
  });

  it('binds single-issue model repair to the selected approval scope', async () => {
    workshopService.fixIssue.mockResolvedValue({
      data: { status: 'SUCCESS', suggested_fix: 'fixed' },
    });

    await requestAgentWorkshopIssueFix({
      issue: { file_name: 'a.yml', key: 'k1' },
      projectId: 'project-1',
      selectedModel: 'gemini-pro',
      selectedProvider: 'gemini',
    });

    expect(workshopService.fixIssue).toHaveBeenCalledWith(expect.objectContaining({
      project_id: 'project-1',
      approval: {
        approved: true,
        issue_count: 1,
        api_provider: 'gemini',
        api_model: 'gemini-pro',
      },
    }));
  });

  it('rejects invalid-key single repair before calling the API', async () => {
    await expect(requestAgentWorkshopIssueFix({
      issue: {
        file_name: 'a.yml',
        key: 'broken key',
        error_code: 'validation_invalid_key_format',
      },
      projectId: 'project-1',
      selectedModel: 'gemini-pro',
      selectedProvider: 'gemini',
    })).rejects.toThrow('Invalid localization keys require manual file repair.');

    expect(workshopService.fixIssue).not.toHaveBeenCalled();
  });

  it('creates project-scoped idempotency keys for safe retries', () => {
    expect(createAgentWorkshopIdempotencyKey('project-1')).toMatch(/^agent-workshop:project-1:/);
  });

  it('reads backend task status for Agent Workshop runs', async () => {
    projectService.getTaskStatus.mockResolvedValue({
      data: { task_id: 'task-1', status: 'completed' },
    });

    await expect(getAgentWorkshopRunStatus('task-1')).resolves.toEqual({
      task_id: 'task-1',
      status: 'completed',
    });
  });
});
