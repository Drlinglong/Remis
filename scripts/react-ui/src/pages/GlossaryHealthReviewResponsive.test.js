import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const pageCss = readFileSync(
  resolve(process.cwd(), 'src/pages/GlossaryHealthReviewPage.module.css'),
  'utf8',
);
const workbenchCss = readFileSync(
  resolve(process.cwd(), 'src/components/glossary/GlossaryHealthWorkbench.module.css'),
  'utf8',
);

const narrowWorkbenchBlock = workbenchCss.slice(workbenchCss.indexOf('@container (max-width: 760px)'));

describe('Glossary health review responsive layout contract', () => {
  it('keeps the review page fixed while the workbench owns scrolling', () => {
    expect(pageCss).toMatch(/\.page\s*{[^}]*height:\s*100%/s);
    expect(pageCss).toMatch(/\.page\s*{[^}]*min-height:\s*0/s);
    expect(pageCss).toMatch(/\.page\s*{[^}]*overflow:\s*hidden/s);
    expect(pageCss).toMatch(/\.workbench\s*{[^}]*flex:\s*1 1 0/s);
    expect(workbenchCss).toMatch(/\.queueScroll,\s*\.reviewScroll\s*{[^}]*min-height:\s*0/s);
  });

  it('responds to its own container and stacks the queue above the editor when narrow', () => {
    expect(workbenchCss).toMatch(/\.root\s*{[^}]*container-type:\s*inline-size/s);
    expect(narrowWorkbenchBlock).toContain('grid-template-columns: minmax(0, 1fr)');
    expect(narrowWorkbenchBlock).toContain('grid-template-rows: minmax(150px, 32%) minmax(0, 1fr)');
    expect(narrowWorkbenchBlock).toMatch(/\.queue\s*{[^}]*border-bottom:/s);
  });
});
