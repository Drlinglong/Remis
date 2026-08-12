import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const styles = readFileSync(
  resolve(process.cwd(), 'src/components/neologism/JudgmentCourt.module.css'),
  'utf8',
);

describe('JudgmentCourt motion contract', () => {
  it('uses semantic motion tokens for meaningful state transitions', () => {
    expect(styles).toContain('@keyframes judgment-case-enter');
    expect(styles).toContain('@keyframes judgment-toolbar-enter');
    expect(styles).toContain('var(--motion-duration-standard)');
    expect(styles).toContain('var(--motion-ease-emphasized)');
  });

  it('removes local movement when reduced motion is requested', () => {
    expect(styles).toContain('@media (prefers-reduced-motion: reduce)');
    expect(styles).toMatch(/\.caseWorkspaceMotion,[\s\S]*\.batchActions[\s\S]*animation: none;/);
  });
});

