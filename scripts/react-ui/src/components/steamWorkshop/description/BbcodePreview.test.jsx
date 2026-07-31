import React from 'react';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it } from 'vitest';
import { BbcodePreview } from './BbcodePreview';

describe('BbcodePreview', () => {
  it('renders an allowlisted BBCode subset as React elements', () => {
    render(
      <MantineProvider>
        <BbcodePreview bbcode="[h1]标题[/h1][b]正文[/b]" />
      </MantineProvider>,
    );

    expect(screen.getByRole('heading', { name: '标题' })).toBeInTheDocument();
    expect(screen.getByText('正文')).toBeInTheDocument();
  });

  it('never interprets untrusted HTML as DOM', () => {
    const { container } = render(
      <MantineProvider>
        <BbcodePreview bbcode={'[b]安全[/b]<img src=x onerror="alert(1)"><script>bad()</script>'} />
      </MantineProvider>,
    );

    expect(screen.getByText(/<img src=x/)).toBeInTheDocument();
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('script')).toBeNull();
  });

  it('declares a paper semantic surface and wraps unbroken content', () => {
    render(
      <MantineProvider>
        <BbcodePreview bbcode={'A'.repeat(300)} />
      </MantineProvider>,
    );

    const preview = screen.getByLabelText('BBCode 预览');
    expect(preview).toHaveAttribute('data-remis-surface', 'paper');
    expect(preview).toHaveStyle({ overflowWrap: 'anywhere' });
  });
});
