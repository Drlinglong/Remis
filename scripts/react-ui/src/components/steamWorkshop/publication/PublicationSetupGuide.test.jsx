import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import PublicationSetupGuide from './PublicationSetupGuide';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key) => key }) }));

it('automatically explains a missing upload runtime and offers the official SDK link', () => {
  render(<MantineProvider><PublicationSetupGuide runtime={{ ready: false }} /></MantineProvider>);
  expect(screen.getByText('workshop_publication.setup_missing')).toBeVisible();
  expect(screen.getByRole('link')).toHaveAttribute('href', 'https://partner.steamgames.com/doc/sdk');
});

it('lets configured users open the walkthrough without changing publication state', () => {
  render(<MantineProvider><PublicationSetupGuide runtime={{ ready: true }} /></MantineProvider>);
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button'));
  expect(screen.getByText('workshop_publication.setup_upload')).toBeVisible();
});
