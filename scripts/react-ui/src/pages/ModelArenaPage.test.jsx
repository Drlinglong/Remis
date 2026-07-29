import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ModelArenaPage from './ModelArenaPage';
import modelArenaService from '../services/modelArenaService';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values = {}) => Object.entries(values).reduce(
      (text, [name, value]) => text.replace(`{{${name}}}`, String(value)),
      key,
    ),
  }),
}));

vi.mock('../services/modelArenaService', () => ({
  default: {
    completeRun: vi.fn(),
    createRun: vi.fn(),
    deleteRun: vi.fn(),
    exportRun: vi.fn(),
    getExportPreview: vi.fn(),
    getRun: vi.fn(),
    listRuns: vi.fn(),
    loadBootstrap: vi.fn(),
    resample: vi.fn(),
    retryFailures: vi.fn(),
    saveVote: vi.fn(),
    startRun: vi.fn(),
  },
}));

vi.mock('../components/modelArena/ArenaSetup', () => ({
  default: ({ draft, onCreateDraft, onRequestStart }) => (
    <div>
      <span>{draft ? `draft:${draft.run_id}` : 'setup'}</span>
      <button type="button" onClick={draft ? onRequestStart : onCreateDraft}>
        {draft ? 'request-start' : 'create-draft'}
      </button>
    </div>
  ),
}));
vi.mock('../components/modelArena/ArenaRunStatus', () => ({
  default: ({ run, onRefresh }) => (
    <div>
      <span>{`run-status:${run.status}`}</span>
      <button type="button" onClick={onRefresh}>refresh-run</button>
    </div>
  ),
}));
vi.mock('../components/modelArena/ArenaVoting', () => ({
  default: ({ run, onSaveVote, onComplete }) => (
    <div>
      <span>{`voting:${run.run_id}`}</span>
      <button
        type="button"
        onClick={async () => {
          await onSaveVote('sample-1', {
            verdict: 'tie',
            winner_output_id: null,
            reason_codes: [],
            note: null,
          });
          await onComplete();
        }}
      >
        vote-and-complete
      </button>
    </div>
  ),
}));
vi.mock('../components/modelArena/ArenaResults', () => ({
  default: ({ run }) => <div>{`results:${run.status}`}</div>,
}));
vi.mock('../components/modelArena/ArenaHistory', () => ({
  default: ({ runs }) => <div>{`history:${runs.length}`}</div>,
}));

const draftRun = {
  run_id: 'run-1',
  status: 'draft',
  sample_size: 6,
  samples: [],
};
const runningRun = { ...draftRun, status: 'running' };
const votingRun = {
  ...draftRun,
  status: 'voting',
  samples: [{ sample_id: 'sample-1', source_text: 'Hello', outputs: [] }],
};
const completedRun = {
  ...votingRun,
  status: 'completed',
  results: { contestants: [] },
};

describe('ModelArenaPage workflow state', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    modelArenaService.loadBootstrap.mockResolvedValue({
      projects: [{ project_id: 'project-1', name: 'Project' }],
      providers: [{ value: 'openai', selected_model: 'model-a' }],
      languages: { zh: 'Chinese' },
    });
    modelArenaService.listRuns.mockResolvedValue({ runs: [], totalCount: 0 });
    modelArenaService.createRun.mockResolvedValue(draftRun);
    modelArenaService.startRun.mockResolvedValue(runningRun);
    modelArenaService.getRun.mockResolvedValue(votingRun);
    modelArenaService.saveVote.mockResolvedValue({ verdict: 'tie' });
    modelArenaService.completeRun.mockResolvedValue(completedRun);
  });

  it('moves from draft through explicit approval, running, voting, and reveal', async () => {
    render(
      <MemoryRouter>
        <MantineProvider><ModelArenaPage /></MantineProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('setup')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'create-draft' }));
    expect(await screen.findByText('draft:run-1')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'request-start' }));
    expect(await screen.findByText('model_arena.cost_title')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('model_arena.cost_confirm'));
    fireEvent.click(screen.getByRole('button', { name: 'model_arena.confirm_start' }));
    expect(await screen.findByText('run-status:running')).toBeInTheDocument();
    expect(modelArenaService.startRun).toHaveBeenCalledWith('run-1');

    fireEvent.click(screen.getByRole('button', { name: 'refresh-run' }));
    expect(await screen.findByText('voting:run-1')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'vote-and-complete' }));

    await waitFor(() => expect(modelArenaService.saveVote).toHaveBeenCalled());
    expect(await screen.findByText('results:completed')).toBeInTheDocument();
  });

  it('loads the independent history tab', async () => {
    modelArenaService.listRuns.mockResolvedValue({
      runs: [{ run_id: 'historic-1', status: 'completed' }],
      totalCount: 1,
    });
    render(
      <MemoryRouter>
        <MantineProvider><ModelArenaPage /></MantineProvider>
      </MemoryRouter>,
    );
    await screen.findByText('setup');
    fireEvent.click(screen.getByRole('tab', { name: 'model_arena.tab_history' }));
    expect(await screen.findByText('history:1')).toBeInTheDocument();
  });

  it('does not let an in-flight refresh resurrect the previous run after New arena', async () => {
    let resolveRefresh;
    modelArenaService.getRun
      .mockResolvedValueOnce(runningRun)
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolveRefresh = resolve;
      }));

    render(
      <MemoryRouter initialEntries={['/model-arena?run=run-1']}>
        <MantineProvider><ModelArenaPage /></MantineProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('run-status:running')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'refresh-run' }));
    fireEvent.click(screen.getByRole('button', { name: 'model_arena.new_arena' }));
    expect(await screen.findByText('setup')).toBeInTheDocument();

    resolveRefresh(votingRun);
    await waitFor(() => expect(screen.getByText('setup')).toBeInTheDocument());
    expect(screen.queryByText('voting:run-1')).not.toBeInTheDocument();
  });
});
