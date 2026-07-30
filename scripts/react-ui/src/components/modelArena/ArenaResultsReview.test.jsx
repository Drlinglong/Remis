import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ArenaResults from './ArenaResults';
import { openExternalUrl } from '../../utils/externalLinks';

vi.mock('../../utils/externalLinks', () => ({
  openExternalUrl: vi.fn(),
}));

const t = (key, values = {}) => {
  if (key === 'model_arena.output_count') return `${values.count} outputs`;
  if (key === 'model_arena.output_sample') return `Sample ${values.number}`;
  return key;
};

describe('ArenaResults output review', () => {
  it('groups every model output by sample and keeps the review collapsed by default', () => {
    render(
      <MantineProvider>
        <ArenaResults
          t={t}
          run={{
            run_id: 'run-results',
            status: 'completed',
            results: {
              contestants: [{
                contestant_id: 'deepseek-1',
                provider_id: 'deepseek',
                model_id: 'deepseek-v4-pro',
                selected_count: 1,
                preference_rate: 1,
              }],
              tie_count: 0,
              reject_all_count: 0,
            },
            samples: [{
              sample_id: 'sample-1',
              ordinal: 0,
              source_text: 'Original source',
              outputs: [{
                output_id: 'output-1',
                contestant_id: 'deepseek-1',
                translated_text: 'Translated output',
              }],
            }],
          }}
          onPreviewExport={vi.fn()}
          onRetryFailures={vi.fn()}
          retrying={false}
        />
      </MantineProvider>,
    );

    expect(screen.getAllByText('deepseek').length).toBeGreaterThan(0);
    expect(screen.getAllByText('deepseek-v4-pro').length).toBeGreaterThan(0);
    expect(screen.queryByText('model_arena.output_review_description')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'model_arena.share_invite' }));
    expect(openExternalUrl).toHaveBeenCalledWith(
      'https://github.com/Drlinglong/Remis/issues/153',
    );
    const outputReviewControl = screen.getByRole('button', {
      name: /sample 1 original source/i,
    });
    expect(outputReviewControl).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(outputReviewControl);

    expect(outputReviewControl).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getAllByText('Original source')).toHaveLength(2);
    expect(screen.getAllByText('deepseek-v4-pro').length).toBeGreaterThan(1);
    expect(screen.getByText('Translated output')).toBeInTheDocument();
  });
});
