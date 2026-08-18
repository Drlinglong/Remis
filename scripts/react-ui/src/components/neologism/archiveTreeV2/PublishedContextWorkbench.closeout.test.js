import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const styles = readFileSync(
    resolve(process.cwd(), 'src/components/neologism/archiveTreeV2/PublishedContextWorkbench.module.css'),
    'utf8',
);

describe('Published context closeout contract', () => {
    it('keeps the needs-placement queue visibly distinct from normal chains', () => {
        expect(styles).toContain(".groupColumn[data-group-kind='needs-placement']");
        expect(styles).toContain('var(--status-warning) 14%');
        expect(styles).toContain('var(--status-warning) 42%');
        expect(styles).toContain(".groupColumn[data-group-kind='needs-placement'] .groupCount");
    });

    it('animates the entity section with a reduced-motion escape hatch', () => {
        expect(styles).toContain('.entitySectionContent');
        expect(styles).toContain(".entitySectionContent[data-expanded='true']");
        expect(styles).toContain('grid-template-rows: 0fr');
        expect(styles).toContain('grid-template-rows: 1fr');
        expect(styles).toContain('@media (prefers-reduced-motion: reduce)');
    });
});
