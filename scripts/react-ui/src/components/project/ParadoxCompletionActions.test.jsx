import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ParadoxCompletionActions from './ParadoxCompletionActions';

const renderActions = (gameId, callbacks = {}) => render(
  <MantineProvider>
    <ParadoxCompletionActions
      deployStatus="idle"
      gameId={gameId}
      handleOpenCleanModal={callbacks.clean || vi.fn()}
      handleOpenDeployModal={callbacks.deploy || vi.fn()}
      t={(key) => key}
    />
  </MantineProvider>,
);

describe('ParadoxCompletionActions', () => {
  it.each(['project_zomboid', 'rimworld', 'surviving_mars'])(
    'does not expose Paradox actions for %s',
    (gameId) => {
      renderActions(gameId);
      expect(screen.queryByRole('button', { name: 'button_auto_deploy' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'button_clean_fake_loc' })).not.toBeInTheDocument();
    },
  );

  it('keeps deploy and cleanup available for Paradox projects', () => {
    const callbacks = { deploy: vi.fn(), clean: vi.fn() };
    renderActions('stellaris', callbacks);

    fireEvent.click(screen.getByRole('button', { name: 'button_auto_deploy' }));
    fireEvent.click(screen.getByRole('button', { name: 'button_clean_fake_loc' }));

    expect(callbacks.deploy).toHaveBeenCalledOnce();
    expect(callbacks.clean).toHaveBeenCalledOnce();
  });
});
