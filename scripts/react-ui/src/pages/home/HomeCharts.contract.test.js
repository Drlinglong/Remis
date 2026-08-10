import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const chartFiles = ['../../components/ProjectStatusPieChart.jsx', '../../components/ProjectDistributionPieChart.jsx'];

describe('Home chart visual contract', () => {
  it.each(chartFiles)('%s uses semantic chart and elevated tooltip tokens', (relativeFile) => {
    const source = readFileSync(new URL(relativeFile, import.meta.url), 'utf8');

    expect(source).toMatch(/var\(--chart-series-/);
    expect(source).toContain('var(--chart-empty)');
    expect(source).toContain('var(--chart-tooltip-bg)');
    expect(source).toContain('var(--chart-tooltip-border)');
    expect(source).toContain('var(--chart-tooltip-text)');
    expect(source).toContain('var(--shadow-elevated)');
    expect(source).not.toMatch(/var\(--glass-/);
    expect(source).not.toMatch(/#[0-9a-f]{3,8}/i);
  });
});
