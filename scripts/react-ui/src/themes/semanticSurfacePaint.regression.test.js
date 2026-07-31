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
  });

  // Regression: ISSUE-008 — light badges and alerts inherited unreadable theme ink.
  // Found by /design-review on 2026-07-31
  // Report: .gstack/design-reports/design-audit-127.0.0.1-2026-07-31.md
  it('binds light badges and alerts to the nearest semantic material', () => {
    expect(definitionsCss).toContain(
      'background: color-mix(in srgb, var(--remis-content-text) 12%, var(--remis-content-bg)) !important;',
    );
    expect(definitionsCss).toContain('background: var(--remis-content-bg) !important;');
    expect(definitionsCss).toContain('border: 1px solid var(--remis-content-border) !important;');
  });
});
