import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  loadAgentWorkshopBootstrap,
  runAgentWorkshopFixBatches,
  scanAgentWorkshopProject,
  selectAgentWorkshopProvider,
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
    getActiveProjects: vi.fn(),
  },
}));

vi.mock('./workshopService', () => ({
  default: {
    fixBatch: vi.fn(),
    scanProject: vi.fn(),
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

  it('runs batch fixes through the workflow service boundary', async () => {
    workshopService.fixBatch.mockResolvedValue({
      data: {
        results: [
          { file_name: 'a.yml', key: 'k1', status: 'SUCCESS', suggested_fix: 'fixed' },
        ],
        attempts: [
          {
            active_count: 1,
            attempt: 1,
            fixed_count: 1,
            max_retries: 3,
            remaining_count: 0,
            status: 'completed',
          },
        ],
      },
    });
    const addExecutionLog = vi.fn();
    const onIssueFixed = vi.fn();
    const onProgress = vi.fn();

    await expect(runAgentWorkshopFixBatches({
      addExecutionLog,
      batchSizeLimit: '10',
      concurrencyLimit: '1',
      issues: [{ file_name: 'a.yml', key: 'k1' }],
      onIssueFixed,
      onProgress,
      projectId: 'project-1',
      rpmLimit: '60',
      selectedModel: 'gemini-pro',
      selectedProvider: 'gemini',
    })).resolves.toMatchObject({
      completed: 1,
      failedCount: 0,
      successCount: 1,
      total: 1,
    });

    expect(workshopService.fixBatch).toHaveBeenCalledWith(expect.objectContaining({
      api_model: 'gemini-pro',
      api_provider: 'gemini',
      project_id: 'project-1',
    }));
    expect(onIssueFixed).toHaveBeenCalledWith(
      { file_name: 'a.yml', key: 'k1' },
      expect.objectContaining({ suggested_fix: 'fixed' })
    );
    expect(onProgress).toHaveBeenCalledWith(expect.objectContaining({ percent: 100 }));
    expect(addExecutionLog).toHaveBeenCalledWith(expect.stringContaining('Starting fix run'));
  });
});
