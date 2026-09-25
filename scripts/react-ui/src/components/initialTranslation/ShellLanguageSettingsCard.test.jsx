import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { useForm } from '@mantine/form';
import { describe, expect, it } from 'vitest';
import ShellLanguageSettingsCard from './ShellLanguageSettingsCard';
import ShellLanguageNotice from '../shared/ShellLanguageNotice';

const t = (key) => key;

function Harness() {
  const form = useForm({ initialValues: {
    english_disguise: false, target_lang_codes: ['fr'], custom_name: 'Italian',
    custom_key: 'l_english', custom_prefix: 'it-', disguise_target_key: 'l_english',
  } });
  return <>
    <ShellLanguageSettingsCard form={form} disguiseOptions={[]} t={t}
      renderNativeSelect={() => <span>shell selector</span>} />
    <output data-testid="values">{JSON.stringify(form.values)}</output>
    <button type="button">Continue</button>
  </>;
}

describe('Shell language guidance', () => {
  it('appears on selection without blocking continuation or changing shell values', () => {
    render(<MantineProvider><Harness /></MantineProvider>);
    expect(screen.queryByText('shell_language_notice.recommendation')).toBeNull();
    fireEvent.click(screen.getByRole('switch'));
    expect(screen.getByText('shell_language_notice.recommendation')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled();
    expect(JSON.parse(screen.getByTestId('values').textContent)).toMatchObject({
      target_lang_codes: [], custom_name: 'Italian', custom_key: 'l_english',
    });
    fireEvent.click(screen.getByRole('switch'));
    expect(screen.queryByText('shell_language_notice.recommendation')).toBeNull();
  });

  it('keeps the compact project explanation collapsed until requested', () => {
    render(<MantineProvider><ShellLanguageNotice t={t} compact /></MantineProvider>);
    const summary = screen.getByText('shell_language_notice.detected');
    expect(summary.parentElement).not.toHaveAttribute('open');
    fireEvent.click(summary);
    expect(summary.parentElement).toHaveAttribute('open');
  });
});
