import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import NewFileModal from './NewFileModal';

vi.mock('@mantine/core', async () => {
  const actual = await vi.importActual('@mantine/core');
  return {
    ...actual,
    Modal: ({ opened, children, title }) =>
      opened ? (
        <div>
          <div>{title}</div>
          {children}
        </div>
      ) : null,
  };
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
  }),
}));

describe('NewFileModal', () => {
  const renderWithProvider = (ui) =>
    render(<MantineProvider>{ui}</MantineProvider>);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows validation error for an invalid glossary filename', async () => {
    renderWithProvider(
      <NewFileModal opened onClose={vi.fn()} onSubmit={vi.fn()} isLoading={false} />
    );

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'bad name.txt' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'button_create' }));

    expect(await screen.findByText('glossary_filename_invalid')).toBeInTheDocument();
  });

  it('submits a valid filename and closes after success', async () => {
    const onSubmit = vi.fn().mockResolvedValue(true);
    const onClose = vi.fn();

    renderWithProvider(
      <NewFileModal opened onClose={onClose} onSubmit={onSubmit} isLoading={false} />
    );

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'units.json' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'button_create' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith('units.json');
    });

    expect(onClose).toHaveBeenCalledOnce();
  });
});
