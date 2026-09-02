import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ArchiveABReviewPanel from './ArchiveABReviewPanel';

const t = (key) => key;
const baseCase = {
  case_id: 'chain-1',
  manifest_id: 'run-1',
  case_kind: 'event_chain',
  chain_id: 'horizon_signal',
  source_entries: [{ source_id: 'event.1', text: 'The signal returns.' }],
  story_facts: ['The signal returns through a loop.'],
  anonymous_outputs: [
    { anonymous_label: 'left', entries: [{ source_id: 'event.1', text: '左译文' }] },
    { anonymous_label: 'right', entries: [{ source_id: 'event.1', text: '右译文' }] },
  ],
};

describe('ArchiveABReviewPanel', () => {
  it('keeps candidates blind and submits a case-level human judgment', async () => {
    const onSubmit = vi.fn().mockResolvedValue({});
    const onChangeCase = vi.fn();
    render(
      <MantineProvider>
        <ArchiveABReviewPanel
          t={t}
          cases={[baseCase, { ...baseCase, case_id: 'chain-2' }]}
          activeIndex={0}
          onChangeCase={onChangeCase}
          onSubmit={onSubmit}
          saving={false}
        />
      </MantineProvider>,
    );

    expect(screen.getByText(/The signal returns\./)).toBeInTheDocument();
    expect(screen.getByText(/The signal returns through a loop\./)).toBeInTheDocument();
    expect(screen.queryByText(/llm|arm|model/i)).not.toBeInTheDocument();
    expect(screen.getAllByTestId('archive-ab-wrapped-code')).toHaveLength(3);
    screen.getAllByTestId('archive-ab-wrapped-code').forEach((entry) => {
      expect(entry).toHaveStyle({
        whiteSpace: 'pre-wrap',
        overflowWrap: 'anywhere',
        wordBreak: 'break-word',
      });
    });
    fireEvent.click(screen.getAllByRole('button', { name: 'archive_ab_review.choose' })[0]);
    fireEvent.click(screen.getByRole('checkbox', { name: 'archive_ab_review.error_fluency_problem' }));
    fireEvent.click(screen.getByRole('button', { name: 'archive_ab_review.save_next' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      manifest_id: 'run-1',
      case_id: 'chain-1',
      selection: 'left',
      error_tags: ['fluency_problem'],
    })));
    expect(onChangeCase).toHaveBeenCalledWith(1);
  });

  it('keeps saved cases blind until the final case reveals the aggregate result', async () => {
    const onSubmit = vi.fn().mockResolvedValue({});
    const savedCase = {
      ...baseCase,
      review: { selection: 'skip', error_tags: [], confidence: 0, note: '' },
      revealed: true,
      reveal: { actual_order: ['A', 'B'], llm_winner: 'A', llm_evidence: ['evidence'] },
    };
    const { rerender } = render(
      <MantineProvider>
        <ArchiveABReviewPanel
          t={t}
          cases={[savedCase, { ...baseCase, case_id: 'chain-2' }]}
          activeIndex={0}
          onChangeCase={vi.fn()}
          onSubmit={onSubmit}
          saving={false}
        />
      </MantineProvider>,
    );

    expect(screen.queryByTestId('archive-ab-reveal')).not.toBeInTheDocument();
    rerender(
      <MantineProvider>
        <ArchiveABReviewPanel
          t={t}
          cases={[savedCase, {
            ...baseCase,
            case_id: 'chain-2',
            review: { selection: 'right', error_tags: [], confidence: 0.5, note: '' },
            revealed: true,
            reveal: {
              actual_order: ['B', 'A'],
              llm_winner: 'not_judged',
              semantic_identity: { right: { condition: 'control_without_archive', label: 'control' } },
            },
          }]}
          activeIndex={1}
          onChangeCase={vi.fn()}
          onSubmit={onSubmit}
          saving={false}
        />
      </MantineProvider>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'archive_ab_review.submit_all_reveal' }));
    expect(await screen.findByTestId('archive-ab-batch-result')).toHaveTextContent('archive_ab_review.control_votes: 1');
    expect(screen.getByTestId('archive-ab-reveal')).toBeInTheDocument();
  });

  it('persists the current judgment before moving to the next case', async () => {
    const onSubmit = vi.fn().mockResolvedValue({});
    const onChangeCase = vi.fn();
    const { rerender } = render(
      <MantineProvider>
        <ArchiveABReviewPanel
          t={t}
          cases={[baseCase, { ...baseCase, case_id: 'chain-2' }]}
          activeIndex={0}
          onChangeCase={onChangeCase}
          onSubmit={onSubmit}
          saving={false}
        />
      </MantineProvider>,
    );

    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId('archive-ab-case-title')));
    fireEvent.click(screen.getAllByRole('button', { name: 'archive_ab_review.choose' })[0]);
    fireEvent.click(screen.getByRole('button', { name: 'archive_ab_review.save_next' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ case_id: 'chain-1', selection: 'left' })));
    expect(onChangeCase).toHaveBeenCalledWith(1);
    expect(onSubmit.mock.invocationCallOrder[0]).toBeLessThan(onChangeCase.mock.invocationCallOrder[0]);
    rerender(
      <MantineProvider>
        <ArchiveABReviewPanel
          t={t}
          cases={[baseCase, { ...baseCase, case_id: 'chain-2' }]}
          activeIndex={1}
          onChangeCase={onChangeCase}
          onSubmit={onSubmit}
          saving={false}
        />
      </MantineProvider>,
    );
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId('archive-ab-case-title')));
  });
});
