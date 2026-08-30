import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const styles = readFileSync(
    resolve(process.cwd(), 'src/components/neologism/archiveTreeV2/PublishedContextWorkbench.module.css'),
    'utf8',
);

describe('Published context workbench motion contract', () => {
    it('uses transform and opacity view motion with a reduced-motion escape hatch', () => {
        expect(styles).toContain('@keyframes context-view-enter');
        expect(styles).toContain('@keyframes context-view-exit');
        expect(styles).toContain(".mapPanel[data-transition='entering']");
        expect(styles).toContain('transform: scale(0.98)');
        expect(styles).toContain('@media (prefers-reduced-motion: reduce)');
    });

    it('animates native details without replacing their open semantics', () => {
        expect(styles).toContain('grid-template-rows: 0fr');
        expect(styles).toContain('details[open] > .detailsContent');
        expect(styles).toContain('grid-template-rows: 1fr');
    });

    it('keeps focused chain rails fixed, compact, and hidden below the desktop threshold', () => {
        expect(styles).toMatch(/\.miniRail\s*\{[\s\S]*flex:\s*0 0 72px;[\s\S]*width:\s*72px;/);
        expect(styles).toMatch(/\.miniRailLabel\s*\{[\s\S]*-webkit-line-clamp:\s*2;[\s\S]*line-clamp:\s*2;/);
        expect(styles).toMatch(/@media \(max-width: 64em\)\s*\{[\s\S]*\.focusedMiniRails\s*\{[\s\S]*display:\s*none;/);
    });
});
