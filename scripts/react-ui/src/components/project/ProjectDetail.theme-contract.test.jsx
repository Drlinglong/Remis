import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const readSource = (path) => readFileSync(resolve(process.cwd(), path), 'utf8');

const dashboardSource = readSource('src/components/projectManagement/ProjectDashboardView.jsx');
const headerSource = readSource('src/components/project/ProjectHeader.jsx');
const historySource = readSource('src/components/project/ProjectHistory.jsx');
const validationSource = readSource('src/components/project/ProjectValidation.jsx');
const stylesSource = readSource('src/pages/ProjectManagement.module.css');

describe('project detail semantic surface contract', () => {
  it('keeps the page header on paper without the legacy highlighted title treatment', () => {
    expect(dashboardSource).toContain('data-remis-surface="canvas"');
    expect(dashboardSource).toContain('data-remis-surface="paper"');
    expect(dashboardSource).toContain('className={styles.paperTitle}');
    expect(dashboardSource).not.toContain("color: 'var(--text-highlight)'");
  });

  it('keeps overview and history summary cards on explicit dark surfaces', () => {
    expect(headerSource).toContain('data-remis-surface="surface"');
    expect(headerSource).toContain('className={styles.surfaceInset}');
    expect(historySource).toContain('className={styles.surfacePanel}');
    expect(historySource).toContain('className={styles.surfaceInset}');
    expect(historySource).not.toContain("background: 'rgba(0,0,0,0.2)'");
  });

  it('keeps validation cards and help messages on explicit paper surfaces', () => {
    expect(validationSource).toContain('className={styles.paperPanel}');
    expect(validationSource).toContain('className={styles.paperInset}');
    expect(validationSource).toContain('className={styles.paperAlert}');
  });

  it('binds semantic text tokens to the same solid backgrounds used by the panels', () => {
    expect(stylesSource).toMatch(
      /\.surfacePanel\s*\{[\s\S]*?background:\s*var\(--surface-bg-solid\)\s*!important;[\s\S]*?color:\s*var\(--surface-text-main\)\s*!important;/,
    );
    expect(stylesSource).toMatch(
      /\.paperPanel\s*\{[\s\S]*?background:\s*var\(--paper-bg\)\s*!important;[\s\S]*?color:\s*var\(--paper-text-main\)\s*!important;/,
    );
    expect(stylesSource).toMatch(
      /\.paperPanel :global\(\.mantine-Title-root\),[\s\S]*?background:\s*transparent\s*!important;/,
    );
  });
});
