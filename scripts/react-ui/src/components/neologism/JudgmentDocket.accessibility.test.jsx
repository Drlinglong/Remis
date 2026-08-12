import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import JudgmentDocket from './JudgmentDocket';

const candidates = [
  { id: 1, original: 'Alpha Relay', suggestion: '阿尔法中继', duplicate_matches: [] },
  { id: 2, original: 'Beta Anchor', suggestion: '贝塔锚点', duplicate_matches: [] },
  { id: 3, original: 'Gamma Beacon', suggestion: '伽马信标', duplicate_matches: [] },
];

const baseProps = {
  batchProcessing: false,
  batchSelectedIds: [],
  candidates,
  docketView: 'pending',
  focusRequest: 0,
  loading: false,
  onBatchConfirm: vi.fn(),
  onDocketViewChange: vi.fn(),
  onSelectCandidate: vi.fn(),
  onToggleAll: vi.fn(),
  onToggleCandidate: vi.fn(),
  processing: false,
  selectedId: 1,
  t: (key) => key,
};

const renderDocket = (props = {}) => render(
  <MantineProvider>
    <JudgmentDocket {...baseProps} {...props} />
  </MantineProvider>,
);

describe('JudgmentDocket keyboard accessibility', () => {
  it('uses one candidate tab stop and moves through the docket with arrow keys', () => {
    const onSelectCandidate = vi.fn();
    renderDocket({ onSelectCandidate });

    const alpha = screen.getByRole('button', { name: /Alpha Relay/ });
    const beta = screen.getByRole('button', { name: /Beta Anchor/ });

    expect(alpha).toHaveAttribute('tabindex', '0');
    expect(beta).toHaveAttribute('tabindex', '-1');

    alpha.focus();
    fireEvent.keyDown(alpha, { key: 'ArrowDown' });

    expect(onSelectCandidate).toHaveBeenCalledWith(2);
    expect(beta).toHaveFocus();
  });

  it('restores focus to the selected adjacent case after a successful action', () => {
    const { rerender } = renderDocket();

    rerender(
      <MantineProvider>
        <JudgmentDocket
          {...baseProps}
          candidates={candidates.slice(1)}
          selectedId={2}
          focusRequest={1}
        />
      </MantineProvider>,
    );

    expect(screen.getByRole('button', { name: /Beta Anchor/ })).toHaveFocus();
  });
});

