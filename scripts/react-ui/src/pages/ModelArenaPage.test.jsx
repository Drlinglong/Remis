import React from 'react';
import { MantineProvider } from '@mantine/core';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ModelArenaPage from './ModelArenaPage';
import modelArenaService from '../services/modelArenaService';

const translate = vi.hoisted(() => (key, values = {}) => Object.entries(values).reduce(
  (text, [name, value]) => text.replace(`{{${name}}}`, String(value)),
  key,
));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: translate }) }));

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
  default: ({ run, votes, onSaveVote, onComplete }) => (
    <div>
      <span>{`voting:${run.run_id}`}</span>
      <span>{`votes:${Object.keys(votes).length}`}</span>
      <input aria-label="vote-notes" />
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
  default: ({ runs, onPreviewExport }) => (
    <div>
      {`history:${runs.length}`}
      {runs.map((run) => (
        <button key={run.run_id} type="button" onClick={() => onPreviewExport(run)}>
          {`preview:${run.run_id}`}
        </button>
      ))}
    </div>
  ),
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

const artifact = (runId, mode) => ({ export_mode: mode, arena_run: { run_id: runId } });
const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

const renderArena = (path = '/model-arena') => render(
  <MemoryRouter initialEntries={[path]}>
    <MantineProvider><ModelArenaPage /></MantineProvider>
  </MemoryRouter>,
);

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

  afterEach(() => vi.restoreAllMocks());

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

    await act(async () => resolveRefresh(votingRun));
    expect(screen.getByText('setup')).toBeInTheDocument();
    expect(screen.queryByText('voting:run-1')).not.toBeInTheDocument();
  });

  it('keeps the voting view, saved votes, and local input when an old poll returns running', async () => {
    const interval = vi.spyOn(window, 'setInterval');
    const oldPoll = deferred();
    modelArenaService.getRun.mockResolvedValueOnce(runningRun)
      .mockReturnValueOnce(oldPoll.promise)
      .mockResolvedValueOnce({ ...votingRun, samples: [{ ...votingRun.samples[0], vote: { verdict: 'tie' } }] });
    renderArena('/model-arena?run=run-1');
    await screen.findByText('run-status:running');
    const [poll] = interval.mock.calls.find(([, delay]) => delay === 1500);
    act(() => { poll(); poll(); });
    expect(modelArenaService.getRun).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByRole('button', { name: 'refresh-run' }));
    await screen.findByText('votes:1');
    fireEvent.change(screen.getByLabelText('vote-notes'), { target: { value: 'unsaved' } });

    await act(async () => oldPoll.resolve(runningRun));

    expect(screen.getByText('voting:run-1')).toBeInTheDocument();
    expect(screen.getByText('votes:1')).toBeInTheDocument();
    expect(screen.getByLabelText('vote-notes')).toHaveValue('unsaved');
  });

  it.each(['older first', 'newer first'])('confirms only the selected preview mode when %s returns', async (order) => {
    const evidence = deferred();
    const summary = deferred();
    modelArenaService.getExportPreview.mockReturnValueOnce(evidence.promise).mockReturnValueOnce(summary.promise);
    modelArenaService.listRuns.mockResolvedValue({ runs: [completedRun] });
    modelArenaService.exportRun.mockResolvedValue({ data: {} });
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    renderArena();
    await screen.findByText('setup');
    fireEvent.click(screen.getByRole('tab', { name: 'model_arena.tab_history' }));
    fireEvent.click(await screen.findByRole('button', { name: 'preview:run-1' }));
    fireEvent.click(await screen.findByRole('radio', { name: 'model_arena.summary_only' }));

    const confirm = screen.getByRole('button', { name: 'model_arena.export_confirmed' });
    expect(confirm).toBeDisabled();
    if (order === 'older first') {
      await act(async () => evidence.resolve(artifact('run-1', 'evidence')));
      expect(confirm).toBeDisabled();
    }
    await act(async () => summary.resolve(artifact('run-1', 'summary-only')));
    if (order === 'newer first') {
      await act(async () => evidence.resolve(artifact('run-1', 'evidence')));
    }

    expect(screen.getByText(/"export_mode": "summary-only"/)).toBeInTheDocument();
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);
    await waitFor(() => expect(modelArenaService.exportRun).toHaveBeenCalledWith('run-1', 'summary-only'));
  });

  it('drops a closed preview failure after opening another run', async () => {
    const oldPreview = deferred();
    modelArenaService.getExportPreview.mockReturnValueOnce(oldPreview.promise)
      .mockResolvedValueOnce(artifact('run-2', 'evidence'));
    modelArenaService.listRuns.mockResolvedValue({ runs: [completedRun, { ...completedRun, run_id: 'run-2' }] });
    renderArena();
    await screen.findByText('setup');
    fireEvent.click(screen.getByRole('tab', { name: 'model_arena.tab_history' }));
    fireEvent.click(await screen.findByRole('button', { name: 'preview:run-1' }));
    fireEvent.click(await screen.findByRole('button', { name: 'model_arena.close' }));
    fireEvent.click(screen.getByRole('button', { name: 'preview:run-2' }));
    expect(await screen.findByText(/"run_id": "run-2"/)).toBeInTheDocument();

    await act(async () => oldPreview.reject(new Error('old preview error')));

    expect(screen.queryByText('old preview error')).not.toBeInTheDocument();
    expect(screen.getByText(/"run_id": "run-2"/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'model_arena.export_confirmed' })).toBeEnabled();
  });
});
