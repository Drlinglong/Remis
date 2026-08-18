import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const taskSummarySource = readFileSync(
  resolve(process.cwd(), 'src/components/tasks/TaskSummaryCard.jsx'),
  'utf8',
);

describe('TaskSummaryCard semantic surface contract', () => {
  it('uses paper action variants on its paper surface', () => {
    expect(taskSummarySource).toContain('data-remis-surface="paper"');
    expect(taskSummarySource).toContain('data-remis-action="paper-secondary"');
    expect(taskSummarySource).not.toContain('data-remis-action="secondary"');
  });
});
