import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../utils/api';
import configService from './configService';
import projectService from './projectService';
import {
  buildModelArenaModelOptions,
  createModelArenaIdempotencyKey,
  loadModelArenaBootstrap,
  modelArenaService,
  normalizeModelArenaRun,
} from './modelArenaService';

vi.mock('../utils/api', () => ({
  default: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));
vi.mock('./configService', () => ({ default: { getConfig: vi.fn() } }));
vi.mock('./projectService', () => ({ default: { getActiveProjects: vi.fn() } }));

describe('modelArenaService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('normalizes bootstrap data and deduplicates configured models', async () => {
    projectService.getActiveProjects.mockResolvedValue({
      data: { projects: [{ project_id: 'project-1' }] },
    });
    configService.getConfig.mockResolvedValue({
      data: {
        api_providers: {
          items: [{ value: 'openai', selected_model: 'gpt-x' }],
        },
        languages: { en: 'English' },
      },
    });
    api.get.mockResolvedValueOnce({
      data: [{ id: 'openai', has_key: true, is_keyless: false }],
    });

    await expect(loadModelArenaBootstrap()).resolves.toEqual({
      projects: [{ project_id: 'project-1' }],
      providers: [{ value: 'openai', selected_model: 'gpt-x', configured: true }],
      languages: { en: 'English' },
    });
    expect(buildModelArenaModelOptions({
      available_models: ['a', 'b'],
      custom_models: ['b', 'c'],
      selected_model: 'a',
    })).toEqual(['a', 'b', 'c']);
  });

  it('uses the planned run, vote, complete, and export contracts', async () => {
    api.post
      .mockResolvedValueOnce({ data: { run: { run_id: 'run-1', status: 'draft' } } })
      .mockResolvedValueOnce({ data: { run: { run_id: 'run-1', status: 'running' } } })
      .mockResolvedValueOnce({ data: { run: { run_id: 'run-1', status: 'completed' } } })
      .mockResolvedValueOnce({ data: new Blob(['{}']) });
    api.put.mockResolvedValue({ data: { vote: { verdict: 'tie' } } });
    api.get.mockResolvedValue({ data: { schema_version: '1' } });
    api.delete.mockResolvedValue({ data: { deleted: true } });

    const created = await modelArenaService.createRun({ project_id: 'project-1' });
    const started = await modelArenaService.startRun('run-1', 'idem-1');
    const vote = await modelArenaService.saveVote('run-1', 'sample/1', {
      verdict: 'tie',
      winner_output_id: null,
      reason_codes: [],
      note: null,
    });
    const completed = await modelArenaService.completeRun('run-1');
    const preview = await modelArenaService.getExportPreview('run-1', 'evidence');
    await modelArenaService.exportRun('run-1', 'evidence');
    await modelArenaService.deleteRun('run-1');

    expect(created.status).toBe('draft');
    expect(started.status).toBe('running');
    expect(vote.verdict).toBe('tie');
    expect(completed.status).toBe('completed');
    expect(preview.schema_version).toBe('1');
    expect(api.post).toHaveBeenNthCalledWith(
      2,
      '/api/model-arena/runs/run-1/start',
      { confirmed_model_calls: true, idempotency_key: 'idem-1' },
    );
    expect(api.put).toHaveBeenCalledWith(
      '/api/model-arena/runs/run-1/samples/sample%2F1/vote',
      expect.objectContaining({ verdict: 'tie' }),
    );
    expect(api.post).toHaveBeenLastCalledWith(
      '/api/model-arena/runs/run-1/export',
      { approved: true, mode: 'evidence' },
      { responseType: 'blob' },
    );
    expect(api.delete).toHaveBeenCalledWith('/api/model-arena/runs/run-1', {
      params: { confirmed: true },
    });
  });

  it('creates a run-scoped idempotency key', () => {
    expect(createModelArenaIdempotencyKey('run-9')).toMatch(/^model-arena:run-9:/);
  });

  it('asks Remis to reveal the checked export in the system file browser', async () => {
    api.post.mockResolvedValue({ data: { status: 'success' } });

    await modelArenaService.openExportPath('J:\\exports\\arena.json');

    expect(api.post).toHaveBeenCalledWith('/api/system/open_folder', {
      path: 'J:\\exports\\arena.json',
    });
  });

  it('joins anonymous top-level outputs and votes into voting samples', () => {
    expect(normalizeModelArenaRun({
      run_id: 'run-1',
      samples: [{ sample_id: 'sample-1', source_text: 'Hello' }],
      outputs: [{ output_id: 'output-1', sample_id: 'sample-1', translated_text: '你好' }],
      votes: [{ sample_id: 'sample-1', verdict: 'tie' }],
    }).samples[0]).toEqual(expect.objectContaining({
      outputs: [expect.objectContaining({ output_id: 'output-1' })],
      vote: expect.objectContaining({ verdict: 'tie' }),
    }));
  });
});
