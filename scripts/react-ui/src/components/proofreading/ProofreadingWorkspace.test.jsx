import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MantineProvider } from '@mantine/core';
import ProofreadingWorkspace from './ProofreadingWorkspace';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key, options) => options?.defaultValue || key }),
}));

vi.mock('./ProofreadingEntryWorkspace', () => ({
  default: () => <div data-testid="entry-workspace">entries</div>,
}));

const baseProps = {
  rows: [],
  onFinalValueChange: vi.fn(),
  validationResults: [],
  stats: { error: 0, warning: 0 },
  loading: false,
  validating: false,
  saving: false,
  isDirty: false,
  translationChangeCount: 0,
  commentChangeCount: 0,
  saveModalOpen: false,
  variableWarnings: [],
  onValidate: vi.fn(),
  onSave: vi.fn(),
  onConfirmSave: vi.fn(),
  onDiscardCommentChanges: vi.fn(),
  onCancelSave: vi.fn(),
  sourceFileSelector: <div>source selector</div>,
  aiFileSelector: <div>target selector</div>,
  query: '',
  onQueryChange: vi.fn(),
  filter: 'all',
  onFilterChange: vi.fn(),
  onScrollOffsetChange: vi.fn(),
  onFocusedEntryChange: vi.fn(),
  onRequestFocusEntry: vi.fn(),
  onDismissDraftConflict: vi.fn(),
};

const renderWorkspace = props => render(
  <MantineProvider><ProofreadingWorkspace {...baseProps} {...props} /></MantineProvider>
);

describe('ProofreadingWorkspace', () => {
  it('renders only the entry workspace and no legacy raw editor tab', () => {
    renderWorkspace();
    expect(screen.getByTestId('entry-workspace')).toBeInTheDocument();
    expect(screen.queryByText('proofreading.tabs.raw')).not.toBeInTheDocument();
  });

  it('keeps variable safety findings advisory with an explicit save-anyway action', () => {
    renderWorkspace({
      rows: [{ entry_id: 'entry-0' }],
      isDirty: true,
      translationChangeCount: 1,
      saveModalOpen: true,
      variableWarnings: [{
        entry_id: 'entry-0',
        key: 'demo.key:0',
        changes: [{ token: '[ROOT]', before: 1, after: 0 }],
      }],
    });
    expect(screen.getByText('Save anyway')).toBeEnabled();
    expect(screen.getByText('[ROOT]')).toBeInTheDocument();
  });
});
