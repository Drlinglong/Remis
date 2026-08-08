import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const definitionsCss = readFileSync(
  resolve(process.cwd(), 'src/themes/definitions.css'),
  'utf8',
);
const themeIds = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];

function parseThemeTokens(themeId) {
  const block = definitionsCss.match(
    new RegExp(`\\[data-theme=['"]${themeId}['"]\\]\\s*\\{([\\s\\S]*?)\\n\\}`),
  );

  if (!block) {
    throw new Error(`Missing semantic token block for ${themeId}`);
  }

  return Object.fromEntries(
    [...block[1].matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)]
      .map(([, name, value]) => [name, value]),
  );
}

function relativeLuminance(hex) {
  const channels = hex
    .slice(1)
    .match(/../g)
    .map((value) => parseInt(value, 16) / 255)
    .map((value) => (
      value <= 0.04045
        ? value / 12.92
        : ((value + 0.055) / 1.055) ** 2.4
    ));

  return (
    (0.2126 * channels[0])
    + (0.7152 * channels[1])
    + (0.0722 * channels[2])
  );
}

function contrastRatio(foreground, background) {
  const luminances = [
    relativeLuminance(foreground),
    relativeLuminance(background),
  ].sort((a, b) => b - a);

  return (luminances[0] + 0.05) / (luminances[1] + 0.05);
}

describe.each(themeIds)('%s semantic contrast contract', (themeId) => {
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
    ['interactive-accent-text', 'interactive-accent'],
  ])('%s meets WCAG AA against %s', (foregroundToken, backgroundToken) => {
    expect(
      contrastRatio(tokens[foregroundToken], tokens[backgroundToken]),
      `${themeId}: ${foregroundToken} on ${backgroundToken}`,
    ).toBeGreaterThanOrEqual(4.5);
  });

  it('keeps the surface boundary distinguishable', () => {
    expect(
      contrastRatio(tokens['surface-border'], tokens['surface-bg-solid']),
      `${themeId}: surface-border on surface-bg-solid`,
    ).toBeGreaterThanOrEqual(3);
  });
});

describe('semantic badge bindings', () => {
  it('keeps light and outline badges readable on their nearest material', () => {
    expect(definitionsCss).toContain(
      "[data-remis-surface] .mantine-Badge-root[data-variant='light']",
    );
    expect(definitionsCss).toContain(
      "[data-remis-surface] .mantine-Badge-root[data-variant='outline']",
    );
    expect(definitionsCss).toContain('color: var(--remis-content-text) !important');
  });
});

describe('semantic modal bindings', () => {
  it('keeps Mantine portal primitives on the elevated material', () => {
    [
      '.mantine-Modal-content',
      '.mantine-Modal-header',
      '.mantine-Modal-body',
      '.mantine-Modal-title',
      '.mantine-Modal-close',
    ].forEach((selector) => {
      expect(definitionsCss).toContain(selector);
    });
    expect(definitionsCss).toContain('background: var(--elevated-bg);');
    expect(definitionsCss).toContain('color: var(--elevated-text-main);');
  });
});
