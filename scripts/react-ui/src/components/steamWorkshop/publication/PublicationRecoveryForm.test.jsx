import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import PublicationRecoveryForm from './PublicationRecoveryForm';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key) => key }) }));

describe('manual remote verification', () => {
  it('records explicit inspection without calling upload', async () => {
    const verify = vi.fn().mockResolvedValue(true);
    const recovered = vi.fn();
    render(<MantineProvider><PublicationRecoveryForm
      plan={{ plan_id: 'one', result: { published_file_id: '12345' } }} busy={false} onVerify={verify} onRecovered={recovered}
    /></MantineProvider>);
    const button = screen.getByRole('button', { name: 'workshop_publication.record_verification' });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(button);
    await waitFor(() => expect(recovered).toHaveBeenCalledWith({ verified: true, resolution: 'item_present', published_file_id: '12345' }));
    expect(verify).toHaveBeenCalledWith('one', { verified: true, resolution: 'item_present', published_file_id: '12345' });
  });

  it('does not proceed when verification was rejected by the backend', async () => {
    const verify = vi.fn().mockResolvedValue(false);
    const recovered = vi.fn();
    render(<MantineProvider><PublicationRecoveryForm
      plan={{ plan_id: 'one', result: { published_file_id: '12345' } }} busy={false} onVerify={verify} onRecovered={recovered}
    /></MantineProvider>);
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'workshop_publication.record_verification' }));
    await waitFor(() => expect(verify).toHaveBeenCalled());
    expect(recovered).not.toHaveBeenCalled();
  });
});
