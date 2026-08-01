import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const readSource = (fileName) => readFileSync(
    resolve(process.cwd(), 'src/components/neologism', fileName),
    'utf8',
);

const setupSource = readSource('ModArchiveAnalysisSetup.jsx');
const releaseSource = readSource('PublishedArchivePanel.jsx');
const editorSource = readSource('ModArchiveOverrideEditor.jsx');
const stylesSource = readSource('ModArchive.module.css');

describe('Mod Archive semantic workbench contract', () => {
    it('uses semantic material tokens without theme-specific selectors or raw colors', () => {
        expect(stylesSource).toContain('var(--canvas-text-main)');
        expect(stylesSource).toContain('var(--surface-bg)');
        expect(stylesSource).toContain('var(--paper-bg)');
        expect(stylesSource).toContain('var(--interactive-accent)');
        expect(stylesSource).not.toMatch(/data-theme|\.byzantine|\.victorian|\.scifi|\.wwii|\.medieval/);
        expect(stylesSource).not.toMatch(/#[0-9a-f]{3,8}\b/i);
    });

    it('keeps stable visual QA hooks and semantic action roles', () => {
        expect(setupSource).toContain('data-testid="mod-archive-analysis"');
        expect(setupSource).toContain('data-testid="mod-archive-scope-terms-only"');
        expect(setupSource).toContain('data-testid="mod-archive-scope-narrative-context"');
        expect(setupSource).toContain('data-testid="mod-archive-start-analysis"');
        expect(setupSource).toContain('data-remis-action="primary"');
        expect(releaseSource).toContain('data-testid="mod-archive-release-panel"');
        expect(releaseSource).toContain('data-testid="mod-archive-release-stale"');
        expect(releaseSource).toContain('data-testid="mod-archive-load-traceability"');
        expect(releaseSource).toContain('data-testid="mod-archive-start-draft"');
        expect(editorSource).toContain('data-testid="mod-archive-draft-editor"');
        expect(editorSource).toContain('data-testid="mod-archive-publish-confirm"');
        expect(releaseSource).toContain('data-remis-action="secondary"');
        expect(editorSource).toContain('data-remis-action="primary"');
    });

    it('leaves vertical scrolling to the page tab panels', () => {
        expect(setupSource).not.toContain('ScrollArea');
        expect(releaseSource).not.toContain('ScrollArea');
        expect(editorSource).not.toContain('ScrollArea');
    });
});
