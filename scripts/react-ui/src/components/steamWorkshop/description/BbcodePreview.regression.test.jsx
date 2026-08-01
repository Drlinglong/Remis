import React from 'react';
import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { BbcodePreview } from './BbcodePreview';

describe('BbcodePreview Steam BBCode regressions', () => {
  // Regression: ISSUE-001 — standalone [hr] tags were displayed as literal source.
  // Found by /qa on 2026-07-31
  // Report: .gstack/qa-reports/qa-report-127.0.0.1-2026-07-31.md
  it('renders a standalone Steam horizontal rule instead of previewing its source', () => {
    render(
      <MantineProvider>
        <BbcodePreview bbcode={'[hr]\n重要提示\n[hr]'} />
      </MantineProvider>,
    );

    expect(screen.getAllByRole('separator')).toHaveLength(2);
    expect(screen.queryByText('[hr]')).toBeNull();
    expect(screen.getByText('重要提示')).toBeInTheDocument();
  });

  // Regression: ISSUE-002 — Steam list items require implicit closing at [*] or [/list].
  // Found by /qa on 2026-07-31
  // Report: .gstack/qa-reports/qa-report-127.0.0.1-2026-07-31.md
  it('closes Steam list items implicitly at the next item or closing list tag', () => {
    render(
      <MantineProvider>
        <BbcodePreview bbcode={'[list]\n[*]第一项\n[*]第二项\n[/list]'} />
      </MantineProvider>,
    );

    expect(screen.getByRole('list')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByText('第一项')).toBeInTheDocument();
    expect(screen.getByText('第二项')).toBeInTheDocument();
    expect(screen.queryByText('[*]')).toBeNull();
    expect(screen.queryByText('[/list]')).toBeNull();
  });
});
