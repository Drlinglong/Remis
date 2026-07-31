import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const readSource = (relativePath) => readFileSync(resolve(process.cwd(), relativePath), 'utf8');

const pageSource = readSource('src/pages/SteamWorkshopPage.jsx');
const overviewSource = readSource('src/components/steamWorkshop/SteamWorkshopOverview.jsx');
const workspaceSource = readSource('src/components/steamWorkshop/SteamWorkshopWorkspace.jsx');
const workspaceCardSource = readSource('src/components/steamWorkshop/WorkspaceCard.jsx');
const workspaceEditorSource = readSource('src/components/steamWorkshop/WorkspaceEditorModal.jsx');
const versionHistorySource = readSource('src/components/steamWorkshop/PublishingVersionHistory.jsx');
const descriptionGenerationSource = readSource(
  'src/components/steamWorkshop/description/DescriptionGenerationPanel.jsx',
);
const generatorSource = readSource('src/components/tools/WorkshopGenerator.jsx');
const definitionsSource = readSource('src/themes/definitions.css');

describe('Steam Workshop semantic surface contract', () => {
  it('keeps publishing pages on the nearest workbench material', () => {
    expect(pageSource).toContain('<Container data-remis-surface="canvas"');
    expect(pageSource).toContain('<Paper data-remis-surface="surface"');
    expect(overviewSource).toContain('<Stack data-remis-surface="surface"');
    expect(workspaceSource).toContain('<Stack data-remis-surface="surface"');
    expect(workspaceSource).toContain('<Paper withBorder p="lg" data-remis-surface="paper"');
    expect(workspaceSource).not.toContain('<Paper withBorder p="lg" data-remis-surface="surface"');
    expect(workspaceCardSource).toContain('data-remis-surface="paper"');
    expect(generatorSource).toContain('data-remis-surface="surface"');
    expect(generatorSource).toContain('data-remis-surface="paper"');
    expect(generatorSource).toContain('data-remis-surface="elevated"');
  });

  it('resolves titles, badges, and tabs from the nearest semantic material', () => {
    expect(definitionsSource).toContain('--remis-content-muted: var(--canvas-text-muted)');
    expect(definitionsSource).toContain('--remis-content-muted: var(--surface-text-muted)');
    expect(definitionsSource).toContain('--remis-content-muted: var(--paper-text-muted)');
    expect(definitionsSource).toContain('--remis-content-muted: var(--elevated-text-muted)');
    expect(definitionsSource).toContain(
      "html[data-theme] [data-remis-surface='surface'] .mantine-Title-root",
    );
    expect(definitionsSource).toContain(
      "html[data-theme] [data-remis-surface='elevated'] .mantine-Title-root",
    );
    expect(definitionsSource).toContain(
      "html[data-theme] [data-remis-surface] .mantine-Badge-root[data-variant='light']",
    );
    expect(definitionsSource).toContain(
      "html[data-theme] [data-remis-surface] .mantine-Badge-root[data-variant='outline']",
    );

    const defaultTabs = definitionsSource.indexOf(
      'html[data-theme] [data-remis-surface] .mantine-Tabs-tab {',
    );
    const hoverTabs = definitionsSource.indexOf(
      'html[data-theme] [data-remis-surface] .mantine-Tabs-tab:hover {',
    );
    const selectedTabs = definitionsSource.indexOf(
      "html[data-theme] [data-remis-surface] .mantine-Tabs-tab:is([data-active], [aria-selected='true']) {",
    );

    expect(defaultTabs).toBeGreaterThan(-1);
    expect(hoverTabs).toBeGreaterThan(defaultTabs);
    expect(selectedTabs).toBeGreaterThan(hoverTabs);
    expect(definitionsSource).toContain('color: var(--remis-content-muted) !important;');
    expect(definitionsSource).toContain('color: var(--remis-content-text) !important;');
    expect(definitionsSource).toContain('background: var(--interactive-accent) !important;');
    expect(definitionsSource).toContain('color: var(--interactive-accent-text) !important;');
  });

  it('keeps every publishing modal Portal on the elevated semantic material', () => {
    [workspaceEditorSource, versionHistorySource, descriptionGenerationSource].forEach((source) => {
      expect(source).toContain('data-remis-surface="elevated"');
    });

    [
      '.mantine-Modal-content',
      '.mantine-Modal-header',
      '.mantine-Modal-body',
      '.mantine-Modal-title',
      '.mantine-Modal-close',
    ].forEach((selector) => {
      expect(definitionsSource).toContain(selector);
    });
    expect(definitionsSource).toContain('background: var(--elevated-bg) !important;');
    expect(definitionsSource).toContain('--remis-content-text: var(--elevated-text-main) !important;');
  });

  it('does not introduce theme-name branches in publishing components', () => {
    expect(
      `${pageSource}\n${overviewSource}\n${workspaceSource}\n${workspaceCardSource}\n${workspaceEditorSource}\n${versionHistorySource}\n${descriptionGenerationSource}\n${generatorSource}`,
    ).not.toMatch(/data-theme|\.(?:byzantine|wwii|medieval|victorian|scifi)\b/);
  });
});
