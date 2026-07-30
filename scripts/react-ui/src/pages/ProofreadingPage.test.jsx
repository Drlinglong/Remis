import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ProofreadingPage from './ProofreadingPage';

let closeHandler;
const closeWindow = vi.fn();
const discardCurrentDraft = vi.fn();
const requestSave = vi.fn(callback => callback?.());
const onCloseRequested = vi.fn(async (handler) => {
  closeHandler = handler;
  return vi.fn();
});

vi.mock('@tauri-apps/api/core', () => ({ isTauri: () => true }));
vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({ close: closeWindow, onCloseRequested }),
}));
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
    isDirty: true,
    fileInfo: null,
    projects: [],
    sourceFiles: [],
    targetFilesMap: {},
    rows: [],
    validationResults: [],
    stats: { error: 0, warning: 0 },
    variableWarnings: [],
    query: '',
    filter: 'all',
    scrollOffset: 0,
    translationChangeCount: 1,
    commentChangeCount: 0,
    discardCurrentDraft,
    requestSave,
  }),
}));
vi.mock('../components/proofreading/ProjectSelector', () => ({ default: () => <div /> }));
vi.mock('../components/proofreading/ProofreadingFileList', () => ({
  SourceFileSelector: () => <div />,
  AIFileSelector: () => <div />,
}));
vi.mock('../components/proofreading/ProofreadingWorkspace', () => ({ default: () => <div /> }));

describe('ProofreadingPage Tauri close guard', () => {
  beforeEach(() => {
    closeHandler = null;
    vi.clearAllMocks();
  });

  it('uses an in-app confirmation and closes only after an explicit choice', async () => {
    const router = createMemoryRouter([
      { path: '/proofreading', element: <ProofreadingPage /> },
    ], { initialEntries: ['/proofreading'] });
    render(<MantineProvider><RouterProvider router={router} /></MantineProvider>);

    await waitFor(() => expect(onCloseRequested).toHaveBeenCalled());
    const preventDefault = vi.fn();
    act(() => closeHandler({ preventDefault }));

    expect(preventDefault).toHaveBeenCalled();
    expect(await screen.findByText('Close with unsaved changes?')).toBeInTheDocument();
    expect(closeWindow).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Discard and close' }));
    expect(discardCurrentDraft).toHaveBeenCalled();
    expect(closeWindow).toHaveBeenCalled();
  });
});
