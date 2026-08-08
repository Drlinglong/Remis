import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const definitionsCss = readFileSync(
  resolve(process.cwd(), 'src/themes/definitions.css'),
  'utf8',
);

describe('semantic material paint regressions', () => {
  // Regression: ISSUE-007 — legacy theme paint diverged from declared surface text.
  // Found by /design-review on 2026-07-31
  // Report: .gstack/design-reports/design-audit-127.0.0.1-2026-07-31.md
  it('paints directly declared Paper and Card components with their semantic material', () => {
    expect(definitionsCss).toContain(
      "[data-remis-surface='surface']:is(.mantine-Paper-root, .mantine-Card-root)",
    );
    expect(definitionsCss).toContain('background: var(--surface-bg-solid) !important;');
    expect(definitionsCss).toContain(
      "[data-remis-surface='paper']:is(.mantine-Paper-root, .mantine-Card-root)",
    );
    expect(definitionsCss).toContain('background: var(--paper-bg) !important;');
    expect(definitionsCss).toContain('color: var(--surface-text-main) !important;');
    expect(definitionsCss).toContain('color: var(--paper-text-main) !important;');
  });

  it('themes native select inputs and their operating-system option list', () => {
    expect(definitionsCss).toContain('.mantine-NativeSelect-input');
    expect(definitionsCss).toContain('.mantine-NativeSelect-input option');
    expect(definitionsCss).toContain('background: var(--menu-surface-bg, var(--menu-bg));');
  });

  // Regression: ISSUE-008 — light badges and alerts inherited unreadable theme ink.
  // Found by /design-review on 2026-07-31
  // Report: .gstack/design-reports/design-audit-127.0.0.1-2026-07-31.md
  it('binds light badges and alerts to the nearest semantic material', () => {
    expect(definitionsCss).toContain(
      '--remis-content-text: var(--surface-text-main) !important;',
    );
    expect(definitionsCss).toContain(
      'border: 1px solid currentColor !important;',
    );
    expect(definitionsCss).toContain('background: var(--remis-content-bg) !important;');
    expect(definitionsCss).toContain('border: 1px solid var(--remis-content-border) !important;');
  });
});
