import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const taskRunnerSource = readFileSync(
  resolve(process.cwd(), 'src/components/TaskRunner.jsx'),
  'utf8',
);

describe('TaskRunner semantic surface contract', () => {
  it('keeps the completed report on the elevated text contract', () => {
    expect(taskRunnerSource).toMatch(
      /<Paper\s+[\s\S]*?bg=\{theme\.colors\.dark\[7\]\}[\s\S]*?data-remis-surface="elevated"/,
    );
  });
});
