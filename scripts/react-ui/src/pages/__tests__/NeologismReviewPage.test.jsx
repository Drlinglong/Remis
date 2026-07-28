import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import NeologismReviewPage from '../NeologismReviewPage';

const recordCompleteHandler = vi.hoisted(() => vi.fn());

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

vi.mock('../../components/neologism/MiningDashboard', () => ({
  default: ({ selectedProject, onSelectedProjectChange, onMiningComplete }) => {
    recordCompleteHandler(onMiningComplete);
    return (
      <div>
        <div data-testid="mining-project">{selectedProject || 'none'}</div>
        <button onClick={() => onSelectedProjectChange('demo-stellaris')}>select demo</button>
        <button onClick={onMiningComplete}>finish mining</button>
      </div>
    );
  },
}));

vi.mock('../../components/neologism/JudgmentCourt', () => ({
  default: ({ selectedProject, refreshToken }) => (
    <div data-testid="court-state">{selectedProject || 'none'}:{refreshToken}</div>
  ),
}));


describe('NeologismReviewPage', () => {
  it('carries project context from mining into the refreshed judgment court', () => {
    render(
      <MemoryRouter>
        <MantineProvider>
          <NeologismReviewPage />
        </MantineProvider>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByText('select demo'));
    expect(screen.getByTestId('mining-project')).toHaveTextContent('demo-stellaris');
    expect(recordCompleteHandler.mock.calls[0][0]).toBe(recordCompleteHandler.mock.calls.at(-1)[0]);

    fireEvent.click(screen.getByText('finish mining'));
    expect(screen.getByTestId('court-state')).toHaveTextContent('demo-stellaris:1');
    expect(recordCompleteHandler.mock.calls[0][0]).toBe(recordCompleteHandler.mock.calls.at(-1)[0]);
  });
});
