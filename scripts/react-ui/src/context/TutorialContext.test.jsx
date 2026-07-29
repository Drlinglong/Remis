import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { TutorialProvider } from './TutorialContext';
import { useTutorial } from './TutorialContextCore';

const { driveMock, driverMock } = vi.hoisted(() => ({
  driveMock: vi.fn(),
  driverMock: vi.fn(),
}));

vi.mock('driver.js', () => ({
  driver: (options) => {
    driverMock(options);
    return { drive: driveMock };
  },
}));

vi.mock('../config/tutorialSteps', () => ({
  getTutorialSteps: () => ([
    { element: '#visible-tutorial-target', popover: { title: 'Visible' } },
    { element: '#removed-old-ui-target', popover: { title: 'Removed' } },
  ]),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

function TutorialStarter() {
  const { startTour } = useTutorial();
  return (
    <>
      <div id="visible-tutorial-target">Current UI</div>
      <button type="button" onClick={() => startTour('home')}>Start</button>
    </>
  );
}

describe('TutorialProvider', () => {
  it('skips stale selectors before starting a page tour', () => {
    render(
      <TutorialProvider>
        <TutorialStarter />
      </TutorialProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Start' }));

    expect(driverMock).toHaveBeenCalledWith(expect.objectContaining({
      steps: [
        expect.objectContaining({ element: '#visible-tutorial-target' }),
      ],
    }));
    expect(driveMock).toHaveBeenCalledOnce();
  });
});
