import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import NewGlossaryModal from './NewGlossaryModal';

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

describe('NewGlossaryModal', () => {
  const renderWithProvider = (ui) =>
    render(<MantineProvider>{ui}</MantineProvider>);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('requires a glossary name without imposing a file extension', async () => {
    renderWithProvider(
      <NewGlossaryModal opened onClose={vi.fn()} onSubmit={vi.fn()} isLoading={false} />
    );

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: '   ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'button_create' }));

    expect(await screen.findByText('glossary_name_required')).toBeInTheDocument();
  });

  it('submits a trimmed human-readable name and closes after success', async () => {
    const onSubmit = vi.fn().mockResolvedValue(true);
    const onClose = vi.fn();

    renderWithProvider(
      <NewGlossaryModal opened onClose={onClose} onSubmit={onSubmit} isLoading={false} />
    );

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: '  Core terminology  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'button_create' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith('Core terminology');
    });

    expect(onClose).toHaveBeenCalledOnce();
  });
});
