import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { createMemoryRouter, RouterProvider, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import ProofreadingPage from './ProofreadingPage';

const requestFocusEntry = vi.fn();
const requestSave = vi.fn((callback) => callback?.());

vi.mock('@tauri-apps/api/core', () => ({ isTauri: () => false }));
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key, options) => options?.defaultValue || key }),
}));
vi.mock('../context/TutorialContextCore', () => ({
  useTutorial: () => ({ setPageContext: vi.fn() }),
}));
vi.mock('../hooks/usePersistentState', () => ({
  usePersistentState: () => ['1', vi.fn()],
}));
vi.mock('../hooks/useProofreadingState', () => ({
  default: () => ({
    isDirty: false,
    fileInfo: null,
    projects: [],
    sourceFiles: [],
    targetFilesMap: {},
    rows: [
      { entry_id: 'entry-1', row_type: 'translation', key: 'FIRST' },
      { entry_id: 'entry-2', row_type: 'translation', key: 'SECOND' },
    ],
    focusedEntryKey: 'FIRST',
    validationResults: [],
    stats: { error: 0, warning: 0 },
    variableWarnings: [],
    query: '',
    filter: 'all',
    scrollOffset: 0,
    translationChangeCount: 0,
    commentChangeCount: 0,
    searchParams: new URLSearchParams('projectId=project-1&taskId=task-origin'),
    requestSave,
    requestFocusEntry,
  }),
}));
vi.mock('../components/proofreading/ProjectSelector', () => ({ default: () => <div /> }));
vi.mock('../components/proofreading/ProofreadingFileList', () => ({
  SourceFileSelector: () => <div />,
  AIFileSelector: () => <div />,
}));
vi.mock('../components/proofreading/ProofreadingWorkspace', () => ({
  default: ({ onSaveAndNext }) => (
    <button type="button" onClick={onSaveAndNext}>save-next-probe</button>
  ),
}));

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

describe('proofreading task recovery', () => {
  it('saves before focusing the next entry and can return to the exact source task', () => {
    const router = createMemoryRouter([
      {
        path: '*',
        element: (
          <>
            <ProofreadingPage />
            <LocationProbe />
          </>
        ),
      },
    ], {
      initialEntries: ['/proofreading?projectId=project-1&taskId=task-origin'],
    });

    render(<MantineProvider><RouterProvider router={router} /></MantineProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'save-next-probe' }));
    expect(requestSave).toHaveBeenCalledOnce();
    expect(requestFocusEntry).toHaveBeenCalledWith('SECOND');

    fireEvent.click(screen.getByRole('button', { name: 'Return to source task' }));
    expect(screen.getByTestId('location')).toHaveTextContent('/tasks/task-origin');
  });
});
