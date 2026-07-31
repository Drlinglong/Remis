import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const readSource = (relativePath) => readFileSync(resolve(process.cwd(), relativePath), 'utf8');

const thumbnailCss = readSource('src/components/tools/ThumbnailGenerator.css');
const thumbnailSource = readSource('src/components/tools/ThumbnailGenerator.jsx');
const coverCanvasSource = readSource('src/components/steamWorkshop/cover/CoverCanvas.jsx');

const cssRule = (selector) => {
    const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return thumbnailCss.match(new RegExp(`${escapedSelector}\\s*\\{([^}]*)\\}`))?.[1] || '';
};

describe('thumbnail generator responsive layout contract', () => {
    it('keeps both preview states inside a proportional narrow frame', () => {
        for (const selector of ['#thumbnail-canvas', '.cover-canvas-placeholder']) {
            const rule = cssRule(selector);
            expect(rule).toContain('width: min(512px, 100%)');
            expect(rule).toContain('max-width: 100%');
            expect(rule).toContain('min-width: 0');
            expect(rule).toContain('aspect-ratio: 1');
        }

        expect(cssRule('#thumbnail-canvas')).toContain('height: auto');
        expect(coverCanvasSource).not.toMatch(/id="thumbnail-canvas"[\s\S]*style=\{\{\s*width:\s*512/);
    });

    it('scales the Konva host and keeps the download action in normal flow', () => {
        expect(thumbnailCss).toMatch(
            /#thumbnail-canvas \{[\s\S]*position: relative/s,
        );
        expect(thumbnailCss).toMatch(
            /#thumbnail-canvas \.konvajs-content\s*\{[\s\S]*position: absolute !important[\s\S]*inset: 0[\s\S]*width: 100% !important[\s\S]*height: 100% !important/s,
        );
        expect(thumbnailCss).toMatch(
            /#thumbnail-canvas canvas\s*\{[\s\S]*position: absolute !important[\s\S]*inset: 0[\s\S]*width: 100% !important[\s\S]*height: 100% !important/s,
        );
        expect(thumbnailCss).toMatch(
            /\.cover-canvas-panel\s*\{[\s\S]*display: flex[\s\S]*flex-direction: column[\s\S]*gap: 16px/s,
        );
        expect(thumbnailCss).toMatch(
            /\.cover-canvas-action\s*\{[\s\S]*max-width: 100%[\s\S]*flex: 0 0 auto/s,
        );
        expect(thumbnailSource).toContain('className="cover-canvas-action"');
    });

    it('uses the workbench surface for editor content and controls', () => {
        expect(thumbnailSource).toContain('<Stack data-remis-surface="surface"');
        expect(thumbnailSource).not.toContain('<Stack data-remis-surface="canvas"');
    });
});
