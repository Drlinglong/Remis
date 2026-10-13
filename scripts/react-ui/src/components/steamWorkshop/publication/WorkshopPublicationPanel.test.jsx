import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WorkshopPublicationPanel from './WorkshopPublicationPanel';

const { controller } = vi.hoisted(() => ({ controller: {
  options: { outputs: [] }, history: [], preview: null, busy: false, error: '',
  createPreview: vi.fn(), invalidate: vi.fn(), submit: vi.fn(), refresh: vi.fn(),
} }));
vi.mock('./useWorkshopPublication', () => ({ useWorkshopPublication: () => controller }));
vi.mock('./PublicationPreview', () => ({ default: () => <div>Immutable preview</div>, PublicationOutcome: () => null }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key) => key }) }));

describe('publication GUI explicit approval', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    controller.options = { outputs: [] };
    controller.preview = { status: 'preview', allowed_actions: ['approve_publication'] };
  });
  const show = () => render(<MantineProvider><WorkshopPublicationPanel workspaceId="workspace" /></MantineProvider>);

  it('explains an empty output list instead of presenting a blank active dropdown', () => {
    show();
    expect(screen.getByRole('textbox', { name: 'workshop_publication.output' })).toBeDisabled();
    expect(screen.getByText('workshop_publication.output_empty')).toBeVisible();
    expect(screen.getByRole('button', { name: 'workshop_publication.preview' })).toBeDisabled();
  });

  it('requires a checked approval before upload', () => {
    show();
    const submit = screen.getByRole('button', { name: 'workshop_publication.submit' });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox'));
    expect(submit).toBeEnabled();
    fireEvent.click(submit);
    expect(controller.submit).toHaveBeenCalledTimes(1);
  });

  it('clears approval and preview identity when editing the title', () => {
    show();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.change(screen.getByRole('textbox', { name: 'workshop_publication.mod_title' }), { target: { value: 'Changed' } });
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(controller.invalidate).toHaveBeenCalled();
  });

  it('respects server allowed_actions even after checking approval', () => {
    controller.preview.allowed_actions = [];
    show();
    fireEvent.click(screen.getByRole('checkbox'));
    expect(screen.getByRole('button', { name: 'workshop_publication.submit' })).toBeDisabled();
  });

  it('does not offer repeat upload for an unknown terminal outcome', () => {
    controller.preview.status = 'unknown';
    show();
    expect(screen.queryByRole('button', { name: 'workshop_publication.submit' })).not.toBeInTheDocument();
    expect(controller.submit).not.toHaveBeenCalled();
  });

  it('only permits update previews with an ID within the server length limit', () => {
    controller.options = { outputs: [{ output_folder_name: 'translated' }], default_app_id: 3650 };
    show();
    fireEvent.click(screen.getByRole('textbox', { name: 'workshop_publication.output' }));
    fireEvent.click(screen.getByRole('option', { name: 'translated' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'workshop_publication.mod_title' }), { target: { value: 'Translation' } });
    fireEvent.click(screen.getByRole('textbox', { name: 'workshop_publication.mode_label' }));
    fireEvent.click(screen.getByRole('option', { name: 'workshop_publication.mode.update' }));
    const input = screen.getByRole('textbox', { name: 'workshop_publication.item_id' });
    const button = screen.getByRole('button', { name: 'workshop_publication.preview' });
    fireEvent.change(input, { target: { value: '12345678901234567890' } });
    expect(button).toBeEnabled();
    fireEvent.change(input, { target: { value: '123456789012345678901' } });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(controller.createPreview).not.toHaveBeenCalled();
  });
});
