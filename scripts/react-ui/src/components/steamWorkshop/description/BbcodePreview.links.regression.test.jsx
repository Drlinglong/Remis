import React from 'react';
import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { BbcodePreview } from './BbcodePreview';

describe('BbcodePreview Steam BBCode link regressions', () => {
  // Regression: ISSUE-003 — Steam [url] links were rendered as literal BBCode.
  it('renders parameterized and inline Steam URL links as safe external anchors', () => {
    render(
      <MantineProvider>
        <BbcodePreview bbcode={'[url=https://github.com/Drlinglong/V3_Mod_Localization_Factory]项目主页[/url] [url]https://creativecommons.org/licenses/by-nc-sa/4.0/deed.en[/url]'} />
      </MantineProvider>,
    );

    expect(screen.getByRole('link', { name: '项目主页' })).toHaveAttribute(
      'href',
      'https://github.com/Drlinglong/V3_Mod_Localization_Factory',
    );
    expect(screen.getByRole('link', { name: 'https://creativecommons.org/licenses/by-nc-sa/4.0/deed.en' })).toHaveAttribute(
      'href',
      'https://creativecommons.org/licenses/by-nc-sa/4.0/deed.en',
    );
    screen.getAllByRole('link').forEach((link) => {
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });
  });

  it('does not turn unsafe URL protocols into links', () => {
    render(
      <MantineProvider>
        <BbcodePreview bbcode="[url=javascript:alert(1)]不安全链接[/url]" />
      </MantineProvider>,
    );

    expect(screen.getByText('不安全链接')).toBeInTheDocument();
    expect(screen.queryByRole('link')).toBeNull();
  });
});
