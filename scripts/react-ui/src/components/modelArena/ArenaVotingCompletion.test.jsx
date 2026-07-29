import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ArenaVoting from './ArenaVoting';

const t = (key, values = {}) => (
  key === 'model_arena.feature_file'
    ? `file:${values.file}`
    : key
);

const run = {
  run_id: 'run-completion',
  status: 'voting',
  samples: [
    {
      sample_id: 'sample-1',
      source_text: 'First source',
      feature_tags: ['complex_punctuation', 'length:medium', 'file:demo.yml'],
      outputs: [
        { output_id: 'a-1', translated_text: 'First A' },
        { output_id: 'b-1', translated_text: 'First B' },
      ],
    },
    {
      sample_id: 'sample-2',
      source_text: 'Second source',
      outputs: [
        { output_id: 'a-2', translated_text: 'Second A' },
        { output_id: 'b-2', translated_text: 'Second B' },
      ],
    },
  ],
};

const renderVoting = (votes, onComplete = vi.fn()) => render(
  <MantineProvider>
    <ArenaVoting
      t={t}
      run={run}
      votes={votes}
      saving={false}
      onSaveVote={vi.fn().mockResolvedValue({})}
      onComplete={onComplete}
      onRetryFailures={vi.fn()}
      retrying={false}
    />
  </MantineProvider>,
);

describe('ArenaVoting completion step', () => {
  it('hides reveal until every vote exists, then shows a dedicated confirmation view', () => {
    const onComplete = vi.fn();
    const view = renderVoting({}, onComplete);

    expect(screen.queryByRole('button', { name: 'model_arena.complete_reveal' }))
      .not.toBeInTheDocument();
    expect(screen.getByText('model_arena.feature_complex_punctuation')).toBeInTheDocument();
    expect(screen.getByText('model_arena.feature_length_medium')).toBeInTheDocument();
    expect(screen.getByText('file:demo.yml')).toBeInTheDocument();

    view.rerender(
      <MantineProvider>
        <ArenaVoting
          t={t}
          run={run}
          votes={{
            'sample-1': { verdict: 'tie' },
            'sample-2': { verdict: 'reject_all' },
          }}
          saving={false}
          onSaveVote={vi.fn().mockResolvedValue({})}
          onComplete={onComplete}
          onRetryFailures={vi.fn()}
          retrying={false}
        />
      </MantineProvider>,
    );

    expect(screen.getByText('model_arena.votes_complete_title')).toBeInTheDocument();
    expect(screen.queryByText('First source')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'model_arena.complete_reveal' }));
    expect(onComplete).toHaveBeenCalledTimes(1);
  });
});
