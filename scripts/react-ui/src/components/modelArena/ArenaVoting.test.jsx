import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ArenaVoting from './ArenaVoting';

const t = (key) => key;
const run = {
  run_id: 'run-1',
  status: 'voting',
  samples: [
    {
      sample_id: 'sample-1',
      source_text: 'A quiet evening.',
      outputs: [
        {
          output_id: 'output-a',
          candidate_id: 'candidate-1',
          translated_text: '宁静的夜晚。',
        },
        {
          output_id: 'output-b',
          candidate_id: 'candidate-2',
          translated_text: '一个安静的晚上。',
        },
      ],
    },
    {
      sample_id: 'sample-2',
      source_text: 'Hold the line.',
      outputs: [
        { output_id: 'output-c', candidate_id: 'candidate-1', translated_text: '守住阵线。' },
        { output_id: 'output-d', candidate_id: 'candidate-2', translated_text: '坚持住。' },
      ],
    },
  ],
};

describe('ArenaVoting', () => {
  it('submits an opaque winner and preference reasons without model identity', async () => {
    const onSaveVote = vi.fn().mockResolvedValue({});
    render(
      <MantineProvider>
        <ArenaVoting
          t={t}
          run={run}
          votes={{}}
          saving={false}
          onSaveVote={onSaveVote}
          onComplete={vi.fn()}
          onRetryFailures={vi.fn()}
          retrying={false}
        />
      </MantineProvider>,
    );

    expect(screen.queryByText(/openai|gemini|gpt/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByLabelText('model_arena.choose_candidate')[0]);
    fireEvent.click(screen.getByLabelText('model_arena.reason_concise'));
    fireEvent.click(screen.getByRole('button', { name: 'model_arena.save_and_next' }));

    await waitFor(() => expect(onSaveVote).toHaveBeenCalledWith('sample-1', {
      verdict: 'winner',
      winner_output_id: 'output-a',
      reason_codes: ['concise'],
      note: null,
    }));
    expect(screen.getByText('Hold the line.')).toBeInTheDocument();
  });

  it('supports a tie without attaching model-specific reasons', async () => {
    const onSaveVote = vi.fn().mockResolvedValue({});
    render(
      <MantineProvider>
        <ArenaVoting
          t={t}
          run={{ ...run, samples: [run.samples[0]] }}
          votes={{}}
          saving={false}
          onSaveVote={onSaveVote}
          onComplete={vi.fn()}
          onRetryFailures={vi.fn()}
          retrying={false}
        />
      </MantineProvider>,
    );

    fireEvent.click(screen.getByLabelText('model_arena.tie'));
    expect(screen.queryByText('model_arena.reasons')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'model_arena.save_vote' }));
    await waitFor(() => expect(onSaveVote).toHaveBeenCalledWith(
      'sample-1',
      expect.objectContaining({
        verdict: 'tie',
        winner_output_id: null,
        reason_codes: [],
      }),
    ));
  });
});
