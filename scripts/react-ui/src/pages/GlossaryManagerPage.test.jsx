import React from 'react';
import { MantineProvider } from '@mantine/core';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GlossaryManagerPage from './GlossaryManagerPage';
import useGlossaryActions from '../hooks/useGlossaryActions';

const setSidebarWidth = vi.fn();
const setSidebarCollapsed = vi.fn();

vi.mock('../hooks/useGlossaryActions');
vi.mock('../context/SidebarContextCore', () => ({
  useSidebar: () => ({ setSidebarWidth, setSidebarCollapsed }),
}));
vi.mock('../context/TutorialContextCore', () => ({
  useTutorial: () => ({ setPageContext: vi.fn() }),
}));
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));
vi.mock('../components/glossary/GlossaryOverview', () => ({
  default: () => <div>overview</div>,
}));
vi.mock('../components/glossary/NewGlossaryModal', () => ({
  default: () => null,
}));
vi.mock('../components/glossary/GlossaryOperations', () => ({
  default: ({ toolbarMode, defaultIncludeAiAdvice }) => (
    <button type="button">
      {toolbarMode === 'health-only' && defaultIncludeAiAdvice
        ? 'glossary_ai_inspection_action'
        : 'other-operation'}
    </button>
  ),
}));
vi.mock('../components/glossary/EditTermForm', () => ({
  default: ({ selectedTerm }) => (
    <div data-testid="edit-term">{selectedTerm?.id || 'closed'}</div>
  ),
}));

const focusedEntry = {
  id: 'term-42',
  source: 'Army',
  translations: { en: 'Army' },
  notes: '',
};

const glossaryState = {
  focusedEntry,
  isSaving: false,
  isLoadingTree: false,
  isLoadingOverview: false,
  isLoadingContent: false,
  viewMode: 'overview',
  overview: { summary: {}, glossaries: [] },
  treeData: [],
  selectedGame: null,
  setSelectedGame: vi.fn(),
  selectedFile: { key: null, title: '', glossaryId: null },
  targetLanguages: [],
  apiProviders: [],
  projects: [],
  selectedTargetLang: '',
  setSelectedTargetLang: vi.fn(),
  searchScope: 'file',
  setSearchScope: vi.fn(),
  filtering: '',
  setFiltering: vi.fn(),
  pagination: { pageIndex: 0, pageSize: 25 },
  setPagination: vi.fn(),
  rowCount: 0,
  data: [],
  showOverview: vi.fn(),
  openGlossary: vi.fn(),
  handleSave: vi.fn(),
  handleDelete: vi.fn(),
  handleCreateGlossary: vi.fn(),
  handleDeleteGlossary: vi.fn(),
  glossaryOperation: null,
  previewGlossaryMerge: vi.fn(),
  startGlossaryMerge: vi.fn(),
  startGlossaryHealthCheck: vi.fn(),
  loadGlossaryHealthHistory: vi.fn(),
};

describe('GlossaryManagerPage deep-linked entry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useGlossaryActions.mockReturnValue(glossaryState);
  });

  it('opens the requested entry in the edit panel without a row click', async () => {
    render(<MantineProvider><GlossaryManagerPage /></MantineProvider>);

    await waitFor(() => {
      expect(screen.getByTestId('edit-term')).toHaveTextContent('term-42');
    });
    expect(setSidebarWidth).toHaveBeenCalledWith(450);
    expect(setSidebarCollapsed).toHaveBeenCalledWith(false);
  });

  it('shows an AI inspection entry for the selected glossary editor', () => {
    useGlossaryActions.mockReturnValue({
      ...glossaryState,
      focusedEntry: null,
      viewMode: 'editor',
      selectedGame: 'vic3',
      selectedFile: {
        key: 'vic3|7|Core terminology',
        title: 'Core terminology',
        gameId: 'vic3',
        glossaryId: 7,
      },
      overview: {
        summary: {},
        glossaries: [{ glossary_id: 7, game_id: 'vic3', name: 'Core terminology' }],
      },
    });

    render(<MantineProvider><GlossaryManagerPage /></MantineProvider>);

    expect(screen.getByRole('button', { name: 'glossary_ai_inspection_action' }))
      .toBeInTheDocument();
  });
});
