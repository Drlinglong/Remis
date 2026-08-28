import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ReferenceLibraryAvailabilityNotice from './ReferenceLibraryAvailabilityNotice';
import translationService from '../../services/translationService';

vi.mock('../../services/translationService', () => ({
  default: { getReferenceLibraryStatus: vi.fn() },
}));

const t = (key) => key;

describe('ReferenceLibraryAvailabilityNotice', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows a non-blocking hint as soon as the selected game has no corpus', async () => {
    translationService.getReferenceLibraryStatus.mockResolvedValue({
      data: { libraries: [{ game_id: 'eu5', available: false }] },
    });

    render(
      <MantineProvider>
        <ReferenceLibraryAvailabilityNotice enabled gameId="eu5" onOpenSettings={vi.fn()} t={t} />
      </MantineProvider>,
    );

    expect(await screen.findByText('reference_prompt_title')).toBeInTheDocument();
    expect(screen.getByText('reference_prompt_desc')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'reference_prompt_settings' })).toBeInTheDocument();
  });

  it('stays hidden when the selected game already has an active corpus', async () => {
    translationService.getReferenceLibraryStatus.mockResolvedValue({
      data: { libraries: [{ game_id: 'eu5', available: true }] },
    });

    render(
      <MantineProvider>
        <ReferenceLibraryAvailabilityNotice enabled gameId="eu5" onOpenSettings={vi.fn()} t={t} />
      </MantineProvider>,
    );

    await waitFor(() => expect(translationService.getReferenceLibraryStatus).toHaveBeenCalled());
    expect(screen.queryByText('reference_prompt_title')).not.toBeInTheDocument();
  });
});
