import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getAgentWorkshopRunStatus,
  loadAgentWorkshopBootstrap,
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
    });

    await expect(scanAgentWorkshopProject('project-1')).resolves.toEqual([{ key: 'issue-1' }]);
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
    })).resolves.toEqual({ task_id: 'task-1', status: 'started' });

    expect(workshopService.startFixRun).toHaveBeenCalledWith(expect.objectContaining({
      api_model: 'gemini-pro',
      api_provider: 'gemini',
      batch_size_limit: 10,
      concurrency_limit: 1,
      project_id: 'project-1',
      rpm_limit: 60,
    }));
    expect(workshopService.fixBatch).not.toHaveBeenCalled();
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
