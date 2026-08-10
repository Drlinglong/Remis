import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const definitionsCss = readFileSync(
  resolve(process.cwd(), 'src/themes/definitions.css'),
  'utf8',
);

const themeIds = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];

const fixedSpacing = {
  'space-1': '0.25rem',
  'space-2': '0.5rem',
  'space-3': '0.75rem',
  'space-4': '1rem',
  'space-6': '1.5rem',
  'space-8': '2rem',
  'space-12': '3rem',
};

const themeRadius = {
  byzantine: {
    'radius-control': '6px',
    'radius-panel': '8px',
    'radius-paper': '6px',
    'radius-pill': '999px',
  },
  victorian: {
    'radius-control': '2px',
    'radius-panel': '2px',
    'radius-paper': '2px',
    'radius-pill': '999px',
  },
  scifi: {
    'radius-control': '0px',
    'radius-panel': '0px',
    'radius-paper': '0px',
    'radius-pill': '0px',
  },
  wwii: {
    'radius-control': '0px',
    'radius-panel': '0px',
    'radius-paper': '0px',
    'radius-pill': '999px',
  },
  medieval: {
    'radius-control': '8px',
    'radius-panel': '12px',
    'radius-paper': '8px',
    'radius-pill': '999px',
  },
};

const statusTokens = [
  'status-neutral',
  'status-info',
  'status-success',
  'status-warning',
  'status-error',
];

const chartTokens = [
  'chart-series-1',
  'chart-series-2',
  'chart-series-3',
  'chart-series-4',
  'chart-series-5',
  'chart-series-6',
  'chart-series-7',
  'chart-empty',
  'chart-tooltip-bg',
  'chart-tooltip-border',
  'chart-tooltip-text',
];

const rootRequiredTokens = [
  ...Object.keys(fixedSpacing),
  'font-header',
  'font-body',
  'font-mono',
  'type-size-label',
  'type-size-body-sm',
  'type-size-body',
  'type-size-section',
  'type-size-page',
  'type-leading-tight',
  'type-leading-ui',
  'type-leading-body',
  'type-measure-body',
  'radius-control',
  'radius-panel',
  'radius-paper',
  'radius-pill',
  'card-radius',
  'canvas-bg-solid',
  'canvas-text-main',
  'canvas-text-muted',
  'surface-bg-solid',
  'surface-text-main',
  'surface-text-muted',
  'surface-border',
  'surface-border-quiet',
  'surface-border-anchor',
  'paper-bg',
  'paper-text-main',
  'paper-text-muted',
  'paper-border-quiet',
  'paper-border',
  'paper-border-anchor',
  'elevated-bg',
  'elevated-text-main',
  'elevated-text-muted',
  'interactive-accent',
  'interactive-accent-text',
  'focus-ring',
  ...statusTokens,
  ...chartTokens,
  'shadow-elevation',
  'shadow-quiet',
  'shadow-anchor',
  'shadow-elevated',
  'menu-surface-bg',
  'menu-bg',
  'menu-text',
  'menu-muted',
  'menu-border',
  'menu-hover-bg',
  'menu-selected-bg',
  'menu-selected-text',
];

const themeRequiredTokens = [
  'radius-control',
  'radius-panel',
  'radius-paper',
  'radius-pill',
  'card-radius',
  'surface-border-quiet',
  'surface-border-anchor',
  'paper-border-quiet',
  'paper-border',
  'paper-border-anchor',
  ...statusTokens,
  ...chartTokens,
  'shadow-quiet',
  'shadow-anchor',
  'shadow-elevated',
];

function readBlock(selector) {
  const match = definitionsCss.match(
    new RegExp(`${selector}\\s*\\{([\\s\\S]*?)\\n\\}`),
  );

  if (!match) {
    throw new Error(`Missing token block for ${selector}`);
  }

  return match[1];
}

function parseDeclarations(block) {
  return Object.fromEntries(
    [...block.matchAll(/--([\w-]+):\s*([^;]+);/g)]
      .map(([, name, value]) => [name, value.trim()]),
  );
}

const rootTokens = parseDeclarations(readBlock(':root'));
const themeTokens = Object.fromEntries(
  themeIds.map((themeId) => [
    themeId,
    parseDeclarations(readBlock(`\\[data-theme=['"]${themeId}['"]\\]`)),
  ]),
);

describe('phase 2 design primitive contract', () => {
  it('provides a complete safe root fallback', () => {
    rootRequiredTokens.forEach((token) => {
      expect(rootTokens[token], `:root --${token}`).toBeDefined();
      expect(rootTokens[token], `:root --${token}`).not.toBe('');
    });
  });

  it('keeps the global spacing scale on the fixed 4px rhythm', () => {
    Object.entries(fixedSpacing).forEach(([token, value]) => {
      expect(rootTokens[token]).toBe(value);
    });
    expect(definitionsCss).not.toMatch(/--space-(?:5|7|9)\s*:/);
  });

  it.each(themeIds)('defines radius roles explicitly for %s', (themeId) => {
    const tokens = themeTokens[themeId];

    Object.entries(themeRadius[themeId]).forEach(([token, value]) => {
      expect(tokens[token], `${themeId} --${token}`).toBe(value);
    });
    expect(tokens['card-radius']).toBe('var(--radius-panel)');
  });

  it.each(themeIds)('declares the complete theme foundation contract for %s', (themeId) => {
    themeRequiredTokens.forEach((token) => {
      expect(themeTokens[themeId][token], `${themeId} --${token}`).toBeDefined();
      expect(themeTokens[themeId][token], `${themeId} --${token}`).not.toBe('');
    });
  });

  it.each(themeIds)('defines status, chart, and shadow roles explicitly for %s', (themeId) => {
    const tokens = themeTokens[themeId];

    [...statusTokens, ...chartTokens, 'shadow-quiet', 'shadow-anchor', 'shadow-elevated']
      .forEach((token) => {
        expect(tokens[token], `${themeId} --${token}`).toBeDefined();
      });
    expect(tokens['shadow-anchor']).toBe('var(--shadow-elevation)');
    expect(new Set(chartTokens.slice(0, 7).map((token) => tokens[token])).size).toBe(7);
  });

  it('keeps chart tooltip roles on the elevated material', () => {
    expect(rootTokens['chart-tooltip-bg']).toBe('var(--elevated-bg)');
    expect(rootTokens['chart-tooltip-border']).toBe('var(--surface-border)');
    expect(rootTokens['chart-tooltip-text']).toBe('var(--elevated-text-main)');
  });

  it('does not make token values depend on theme classes or component selectors', () => {
    expect(definitionsCss).not.toMatch(
      /--[\w-]+\s*:[^;]*(?:\.(?:byzantine|victorian|scifi|wwii|medieval|mantine-[\w-]+))/,
    );
  });
});
