import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const definitionsCss = readFileSync(
  resolve(process.cwd(), 'src/themes/definitions.css'),
  'utf8',
);
const translationCss = readFileSync(
  resolve(process.cwd(), 'src/pages/Translation.module.css'),
  'utf8',
);
const themeIds = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];

function parseThemeTokens(themeId) {
  const block = definitionsCss.match(
    new RegExp(`\\[data-theme=['"]${themeId}['"]\\]\\s*\\{([\\s\\S]*?)\\n\\}`),
  );

  return Object.fromEntries(
    [...block[1].matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)]
      .map(([, name, value]) => [name, value]),
  );
}

function relativeLuminance(hex) {
  return hex
    .slice(1)
    .match(/../g)
    .map((value) => parseInt(value, 16) / 255)
    .map((value) => (
      value <= 0.04045
        ? value / 12.92
        : ((value + 0.055) / 1.055) ** 2.4
    ))
    .reduce(
      (sum, value, index) => sum + (value * [0.2126, 0.7152, 0.0722][index]),
      0,
    );
}

function contrastRatio(foreground, background) {
  const values = [
    relativeLuminance(foreground),
    relativeLuminance(background),
  ].sort((a, b) => b - a);

  return (values[0] + 0.05) / (values[1] + 0.05);
}

describe.each(themeIds)('%s incremental translation contrast contract', (themeId) => {
  const tokens = parseThemeTokens(themeId);

  it.each([
    ['canvas-text-main', 'canvas-bg-solid'],
    ['canvas-text-muted', 'canvas-bg-solid'],
    ['surface-text-main', 'surface-bg-solid'],
    ['surface-text-muted', 'surface-bg-solid'],
    ['paper-text-main', 'paper-bg'],
    ['paper-text-muted', 'paper-bg'],
    ['elevated-text-main', 'elevated-bg'],
    ['elevated-text-muted', 'elevated-bg'],
  ])('%s remains readable on %s', (foreground, background) => {
    expect(
      contrastRatio(tokens[foreground], tokens[background]),
      `${themeId}: ${foreground} on ${background}`,
    ).toBeGreaterThanOrEqual(4.5);
  });
});

describe('incremental translation semantic surfaces', () => {
  it('uses surface tokens instead of theme-specific selectors and raw glass colors', () => {
    expect(translationCss).toContain('background: var(--surface-bg-solid) !important;');
    expect(translationCss).toContain('background: var(--paper-bg) !important;');
    expect(translationCss).toContain('background: var(--elevated-bg);');
    expect(translationCss).not.toMatch(/data-theme|\.byzantine|\.wwii|\.medieval/);
    expect(translationCss).not.toContain('background: rgba(0, 0, 0, 0.3)');
    expect(translationCss).not.toContain('background: rgba(0, 0, 0, 0.4)');
  });
});
