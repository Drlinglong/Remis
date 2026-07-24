import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const layoutCss = readFileSync(
    resolve(process.cwd(), 'src/pages/GlossaryManager.module.css'),
    'utf8'
);
const overviewCss = readFileSync(
    resolve(process.cwd(), 'src/components/glossary/GlossaryOverview.module.css'),
    'utf8'
);

const narrowLayoutBlock = layoutCss.slice(layoutCss.indexOf('@media (max-width: 760px)'));

describe('Glossary Manager responsive layout contract', () => {
    it('stacks narrow panels without making the whole page the vertical scroll owner', () => {
        expect(narrowLayoutBlock).toContain('flex-direction: column');
        expect(narrowLayoutBlock).toContain('overflow: hidden');
        expect(narrowLayoutBlock).not.toContain('overflow-y: auto');
        expect(narrowLayoutBlock).toMatch(/\.leftPanel\s*{[^}]*width:\s*100%/s);
        expect(narrowLayoutBlock).toMatch(/\.mainPanel\s*{[^}]*width:\s*100%/s);
    });

    it('keeps the overview fixed while assigning scrolling to the inventory', () => {
        expect(overviewCss).toMatch(/\.overview\s*{[^}]*flex:\s*1/s);
        expect(overviewCss).toMatch(/\.overview\s*{[^}]*min-height:\s*0/s);
        expect(overviewCss).toMatch(/\.overview\s*{[^}]*overflow:\s*hidden/s);
        expect(overviewCss).toMatch(/\.inventoryCard\s*{[^}]*flex:\s*1 1 0/s);
        expect(overviewCss).toMatch(/\.inventoryScroll\s*{[^}]*flex:\s*1 1 0/s);
        expect(overviewCss).toMatch(
            /\.inventoryTable thead th\s*{[^}]*background:\s*var\(--surface-bg-solid/s
        );
        expect(overviewCss).toMatch(/\.inventoryTable\s*{[^}]*table-layout:\s*fixed/s);
        expect(overviewCss).toMatch(
            /\.actionCell\s*{[^}]*position:\s*sticky[^}]*right:\s*0/s
        );
        expect(overviewCss).toMatch(
            /@media \(max-width: 1100px\)[\s\S]*\.projectCell,[\s\S]*\.updatedCell\s*{[^}]*display:\s*none/s
        );
        expect(overviewCss).toMatch(
            /@media \(max-width: 760px\)[\s\S]*\.typeCell\s*{[^}]*display:\s*none/s
        );
    });
});
