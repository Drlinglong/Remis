import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import PublicationGameSelect from './PublicationGameSelect';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key, fallback) => fallback || key }) }));

it('shows the project default and retains explicit manual entry', () => {
  const change = vi.fn();
  render(<MantineProvider><PublicationGameSelect value="529340" games={[
    { game_id: 'victoria3', app_id: 529340, name: 'Victoria 3' },
    { game_id: 'hoi4', app_id: 394360, name: 'Hearts of Iron IV' },
  ]} onChange={change} /></MantineProvider>);
  const selector = screen.getByRole('textbox', { name: 'workshop_publication.app_id' });
  expect(selector).toHaveValue('529340（Victoria 3）');
  fireEvent.click(selector);
  fireEvent.click(screen.getByRole('option', { name: 'Enter another App ID' }));
  expect(change).toHaveBeenLastCalledWith('');
  expect(screen.getByRole('textbox', { name: 'Enter another App ID' })).toBeVisible();
});
