import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import { DeployModals } from './DeployModals';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

const createActions = (overrides = {}) => ({
  deployModalOpen: false,
  setDeployModalOpen: vi.fn(),
  cleanModalOpen: false,
  setCleanModalOpen: vi.fn(),
  confirmDeleteOpen: false,
  setConfirmDeleteOpen: vi.fn(),
  deployPath: '',
  setDeployPath: vi.fn(),
  workshopPath: 'J:/Steam/workshop/123',
  setWorkshopPath: vi.fn(),
  loading: false,
  infoLoading: false,
  handleExecuteDeploy: vi.fn(),
  handleDetectWorkshopPath: vi.fn(),
  handleBrowseWorkshopPath: vi.fn(),
  handleExecuteClean: vi.fn(),
  ...overrides,
});

const renderModals = (actions) => render(
  <MantineProvider>
    <DeployModals deployActions={actions} />
  </MantineProvider>
);

describe('DeployModals destructive action guard', () => {
  it('opens a second confirmation instead of cleaning immediately', () => {
    const actions = createActions({ cleanModalOpen: true });
    renderModals(actions);

    fireEvent.click(screen.getByRole('button', { name: 'deploy_btn_delete_fake_loc' }));

    expect(actions.setConfirmDeleteOpen).toHaveBeenCalledWith(true);
    expect(actions.handleExecuteClean).not.toHaveBeenCalled();
  });

  it('does not clean when the second confirmation is cancelled', () => {
    const actions = createActions({ confirmDeleteOpen: true });
    renderModals(actions);

    fireEvent.click(screen.getByRole('button', { name: 'cancel' }));

    expect(actions.setConfirmDeleteOpen).toHaveBeenCalledWith(false);
    expect(actions.handleExecuteClean).not.toHaveBeenCalled();
  });

  it('executes cleanup only from the explicit confirmation action', () => {
    const actions = createActions({ confirmDeleteOpen: true });
    renderModals(actions);

    expect(screen.getByText('J:/Steam/workshop/123')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'deploy_clean_confirm_btn' }));

    expect(actions.handleExecuteClean).toHaveBeenCalledOnce();
  });
});
