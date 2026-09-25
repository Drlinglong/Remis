import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key, fallback, values) => (fallback || key).replace(
    /{{(\w+)}}/g, (_match, name) => values?.[name] ?? `{{${name}}}`,
  ) }),
}));
vi.mock('../hooks/useMarsPipelineImport', () => ({
  useMarsPipelineImport: vi.fn(),
}));
vi.mock('../hooks/useMarsPipelineDelivery', () => ({
  useMarsPipelineDelivery: vi.fn(),
}));
vi.mock('../hooks/useMarsPublicationIdentity', () => ({
  useMarsPublicationIdentity: vi.fn(),
}));

import { useMarsPipelineImport } from '../hooks/useMarsPipelineImport';
import { useMarsPipelineDelivery } from '../hooks/useMarsPipelineDelivery';
import { useMarsPublicationIdentity } from '../hooks/useMarsPublicationIdentity';
import MarsPipelineImport from '../components/project/MarsPipelineImport';
import MarsPipelineDelivery from '../components/project/MarsPipelineDelivery';
import { CreateProjectModal } from '../components/projectManagement/CreateProjectModal';

const renderWithMantine = (component) => render(
  <MantineProvider>{component}</MantineProvider>,
);

describe('Mars pipeline components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useMarsPublicationIdentity.mockReturnValue({ identity: { status: 'unbound' }, steamId: '', loading: false,
      saving: false, error: '', updateSteamId: vi.fn(), bind: vi.fn() });
  });

  it('keeps FPK preparation behind an explicit Surviving Mars action', async () => {
    useMarsPipelineImport.mockReturnValue({
      path: '', name: 'Example Mod', previousRun: '', deliveryMode: 'source_copy',
      plan: null, busy: false, error: '', approved: [],
      update: vi.fn(), preview: vi.fn(), execute: vi.fn(),
    });
    const props = {
      availableGames: [{ value: 'surviving_mars', label: 'Surviving Mars / Relaunched' }],
      availableLanguages: [], createProgressMessage: '', handleBrowseFolder: vi.fn(),
      handleCreateProject: vi.fn(), isCreatingProject: false, newProjectGame: 'surviving_mars',
      newProjectImportMode: 'copy', newProjectName: 'Example Mod', newProjectPath: '',
      newProjectSourceLang: 'en', opened: true, setNewProjectGame: vi.fn(),
      setNewProjectImportMode: vi.fn(), setNewProjectName: vi.fn(), setNewProjectPath: vi.fn(),
      setNewProjectSourceLang: vi.fn(), t: (key, fallback) => fallback || ({
        form_label_project_name: 'Project Name', form_label_folder_path: 'Folder path',
      }[key] || key), onClose: vi.fn(),
    };

    renderWithMantine(<CreateProjectModal {...props} />);
    expect(screen.getByRole('button', { name: 'Open FPK preparation' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reopen FPK preparation' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Folder path')).not.toBeInTheDocument();
    expect(screen.getAllByDisplayValue('Example Mod')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Open FPK preparation' }));
    expect(await screen.findByText('Remis extracts the complete FPK into an isolated project and reads English source text. It leaves the archive and installed Mods unchanged.')).toBeInTheDocument();
    expect(screen.getAllByDisplayValue('Example Mod')).toHaveLength(1);
  });

  it('shows a dedicated FPK modal with the two preparation outcomes and no duplicate name field', () => {
    useMarsPipelineImport.mockReturnValue({
      path: '', name: 'Example Mod', previousRun: '', deliveryMode: 'source_copy',
      plan: null, busy: false, error: '', approved: [],
      update: vi.fn(), preview: vi.fn(), execute: vi.fn(),
    });

    renderWithMantine(<MarsPipelineImport opened name="Example Mod" onClose={vi.fn()} />);

    expect(screen.getByText('Remis extracts the complete FPK into an isolated project and reads English source text. It leaves the archive and installed Mods unchanged.')).toBeInTheDocument();
    expect(screen.queryByLabelText('Translation text only')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Complete translated Mod copy')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Project Name')).not.toBeInTheDocument();
  });

  it('offers delivery choices only after inspection and replans automatically on a mode change', () => {
    const preview = vi.fn();
    useMarsPipelineImport.mockReturnValue({
      path: 'ModContent.fpk', name: 'Example Mod', previousRun: '', deliveryMode: 'source_copy',
      plan: { review_items: [] },
      inspection: { file_count: 57, entry_count: 88, selected_entry_count: 47,
        hardcoded_entry_count: 41, recommended_delivery_mode: 'source_copy' },
      approved: [], busy: false, error: '', update: vi.fn(), preview, execute: vi.fn(),
    });

    renderWithMantine(<MarsPipelineImport opened name="Example Mod" onClose={vi.fn()} />);

    expect(screen.getByLabelText('Translation text only')).toBeInTheDocument();
    expect(screen.getByLabelText('Complete translated Mod copy')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Translation text only'));
    expect(preview).toHaveBeenCalledWith([], 'text_only');
  });

  it('summarizes embedded Lua coverage and keeps review candidates folded until requested', () => {
    useMarsPipelineImport.mockReturnValue({
      path: 'ModContent.fpk', name: 'Example Mod', previousRun: '', deliveryMode: 'text_only',
      inspection: { file_count: 57, entry_count: 88, selected_entry_count: 47,
        hardcoded_entry_count: 41, recommended_delivery_mode: 'source_copy' },
      plan: {
        file_count: 57, entry_count: 88, selected_entry_count: 47,
        hardcoded_entry_count: 41, recommended_delivery_mode: 'source_copy',
        review_items: Array.from({ length: 41 }, (_, index) => ({
          id: `candidate-${index}`, text: `Hidden candidate ${index}`, reason: 'Ambiguous context', refs: [],
        })),
      },
      approved: [], busy: false, error: '', update: vi.fn(), preview: vi.fn(), execute: vi.fn(),
    });

    renderWithMantine(<MarsPipelineImport opened name="Example Mod" onClose={vi.fn()} />);

    expect(screen.getByText(/41 Lua-embedded text candidates unchanged/)).toBeInTheDocument();
    expect(screen.getByText('Recommended: Complete translated Mod copy')).toBeInTheDocument();
    expect(screen.getByText('47 entries selected for this preparation')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Review 41 remaining text candidates' })).toBeInTheDocument();
    expect(screen.getByText('Hidden candidate 0')).not.toBeVisible();
    expect(screen.getAllByRole('alert')).toHaveLength(1);
  });

  it('keeps export disabled when the source-copy preview has blockers', () => {
    useMarsPublicationIdentity.mockReturnValue({ identity: { status: 'unbound' }, steamId: '', loading: false,
      saving: false, error: '', updateSteamId: vi.fn(), bind: vi.fn() });
    const execute = vi.fn();
    useMarsPipelineDelivery.mockReturnValue({
      options: { supported: true, run_id: 'plan-run', translation_outputs: [] },
      mode: 'source_copy', selected: [], busy: false, error: '',
      plan: {
        uncovered_entry_count: 1, localized_entry_count: 46, file_count: 4, total_size_bytes: 11000,
        blockers: [{ id: '812345', reason: 'No approved source rewrite is available.' }],
        allowed_actions: [],
        installation_steps: ['Disable the Workshop copy first.'],
      },
      result: null, update: vi.fn(), preview: vi.fn(), execute, reload: vi.fn(),
    });

    const { container } = renderWithMantine(
      <MarsPipelineDelivery projectId="project-1" gameId="surviving_mars" />,
    );

    expect(container.querySelector('[data-remis-surface="paper"]')).toBeInTheDocument();
    expect(screen.getByText('1 entries are not covered by this delivery. Export stays blocked until the scope is reviewed.')).toBeInTheDocument();
    expect(screen.getByText('46 translated entries · 4 files · 0.01 MB')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Show affected text entries (1)' }));
    expect(screen.getByText('812345: No approved source rewrite is available.')).toBeInTheDocument();
    const exportButton = screen.getByRole('button', { name: 'Generate local package' });
    expect(exportButton).toBeDisabled();
    expect(screen.queryByText('Independent runtime overlay')).not.toBeInTheDocument();
    fireEvent.click(exportButton);
    expect(execute).not.toHaveBeenCalled();
  });

  it('shows unbound creation warning and only a local link action', () => {
    const bind = vi.fn();
    const updateSteamId = vi.fn();
    useMarsPublicationIdentity.mockReturnValue({ identity: { status: 'unbound' }, steamId: '', loading: false,
      saving: false, error: '', updateSteamId, bind });
    useMarsPipelineDelivery.mockReturnValue({ options: { supported: true, run_id: 'run', translation_outputs: [] },
      mode: 'source_copy', selected: [], busy: false, error: '', plan: null, result: null,
      update: vi.fn(), preview: vi.fn(), execute: vi.fn(), reload: vi.fn(), publicationChanged: vi.fn() });
    const { container } = renderWithMantine(<MarsPipelineDelivery projectId="project-1" gameId="surviving_mars" />);
    expect(screen.getByText(/will create a new Workshop item/)).toBeInTheDocument();
    expect(screen.getByText(/does not upload or change anything on Steam/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save Workshop item link' })).toBeDisabled();
    expect(Array.from(container.querySelectorAll('button')).some((button) => /upload|publish/i.test(button.textContent))).toBe(false);
  });

  it('shows the saved Workshop target as locked', () => {
    useMarsPublicationIdentity.mockReturnValue({
      identity: { status: 'bound', steam_id: '3807689989', url: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3807689989' },
      steamId: '3807689989', loading: false, saving: false, error: '', updateSteamId: vi.fn(), bind: vi.fn(),
    });
    useMarsPipelineDelivery.mockReturnValue({ options: { supported: true, run_id: 'run', translation_outputs: [] },
      mode: 'source_copy', selected: [], busy: false, error: '', plan: null, result: null,
      update: vi.fn(), preview: vi.fn(), execute: vi.fn(), reload: vi.fn(), publicationChanged: vi.fn() });
    renderWithMantine(<MarsPipelineDelivery projectId="project-1" gameId="surviving_mars" />);
    expect(screen.getByRole('link', { name: /3807689989/ })).toHaveAttribute('href',
      'https://steamcommunity.com/sharedfiles/filedetails/?id=3807689989');
    expect(screen.getByText('This Workshop link is locked in Remis.')).toBeInTheDocument();
    expect(screen.getByText('Subsequent full-copy exports will target this Workshop item:')).toBeInTheDocument();
    expect(screen.getByText('Previously exported folders are unchanged.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Workshop item link/ })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Your Workshop item ID')).toBeDisabled();
  });

  it('does not infer unbound status when the identity request failed', () => {
    useMarsPublicationIdentity.mockReturnValue({ identity: null, steamId: '', loading: false,
      saving: false, error: 'offline', updateSteamId: vi.fn(), bind: vi.fn() });
    useMarsPipelineDelivery.mockReturnValue({ options: { supported: true, run_id: 'run', translation_outputs: [] },
      mode: 'source_copy', selected: [], busy: false, error: '', plan: null, result: null,
      update: vi.fn(), preview: vi.fn(), execute: vi.fn(), reload: vi.fn(), publicationChanged: vi.fn() });
    renderWithMantine(<MarsPipelineDelivery projectId="project-1" gameId="surviving_mars" />);
    expect(screen.getByText('offline')).toBeInTheDocument();
    expect(screen.getByText(/Workshop identity is unavailable/)).toBeInTheDocument();
    expect(screen.queryByText(/will create a new Workshop item/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save Workshop item link' })).toBeDisabled();
  });

  it('shows the reviewed plan binding even when the current identity panel differs', () => {
    useMarsPublicationIdentity.mockReturnValue({ identity: { status: 'unbound' }, steamId: '', loading: false,
      saving: false, error: '', updateSteamId: vi.fn(), bind: vi.fn() });
    useMarsPipelineDelivery.mockReturnValue({ options: { supported: true, run_id: 'run', translation_outputs: [] },
      mode: 'source_copy', selected: [], busy: false, error: '', result: null,
      plan: { publication_binding: { status: 'bound', steam_id: '76561198000000000',
        url: 'https://steamcommunity.com/sharedfiles/filedetails/?id=76561198000000000' },
      allowed_actions: ['approve_delivery'] },
      update: vi.fn(), preview: vi.fn(), execute: vi.fn(), reload: vi.fn(), publicationChanged: vi.fn() });
    renderWithMantine(<MarsPipelineDelivery projectId="project-1" gameId="surviving_mars" />);
    expect(screen.getByText(/This reviewed export targets Workshop item 76561198000000000/)).toBeInTheDocument();
    expect(screen.getByText(/No Workshop item is linked/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'https://steamcommunity.com/sharedfiles/filedetails/?id=76561198000000000' }))
      .toHaveAttribute('href', 'https://steamcommunity.com/sharedfiles/filedetails/?id=76561198000000000');
  });
});
