import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const readSource = (path) => readFileSync(resolve(process.cwd(), path), 'utf8');

const dashboardSource = readSource('src/components/projectManagement/ProjectDashboardView.jsx');
const headerSource = readSource('src/components/project/ProjectHeader.jsx');
const historySource = readSource('src/components/project/ProjectHistory.jsx');
const validationSource = readSource('src/components/project/ProjectValidation.jsx');
const glossarySource = readSource('src/components/project/ProjectGlossaryPanel.jsx');
const definitionsSource = readSource('src/themes/definitions.css');
const materialStylePaths = [
  'src/components/tools/KanbanBoard.module.css',
  'src/components/tools/KanbanColumn.module.css',
  'src/components/tools/TaskCard.module.css',
  'src/components/projectManagement/ProjectListView.module.css',
  'src/components/projectManagement/ProjectDashboardView.module.css',
  'src/components/project/ProjectDetailSurfaces.module.css',
  'src/components/project/ProjectHeader.module.css',
];
const materialSources = Object.fromEntries(
  materialStylePaths.map((path) => [path, readSource(path)]),
);
const stylesSource = materialSources['src/components/project/ProjectDetailSurfaces.module.css'];

describe('project detail semantic surface contract', () => {
  it('keeps the page header on paper without the legacy highlighted title treatment', () => {
    expect(dashboardSource).toContain('data-remis-surface="canvas"');
    expect(dashboardSource).toContain('data-remis-surface="paper"');
    expect(dashboardSource).toContain('className={surfaceStyles.paperTitle}');
    expect(dashboardSource).not.toContain("color: 'var(--text-highlight)'");
  });

  it('keeps overview and history summary cards on explicit dark surfaces', () => {
    expect(headerSource).toContain('data-remis-surface="surface"');
    expect(headerSource).toContain('className={surfaceStyles.surfaceInset}');
    expect(historySource).toContain('className={styles.surfacePanel}');
    expect(historySource).toContain('className={styles.surfaceInset}');
    expect(historySource).not.toContain("background: 'rgba(0,0,0,0.2)'");
  });

  it('keeps validation cards and help messages on explicit paper surfaces', () => {
    expect(validationSource).toContain('className={styles.paperPanel}');
    expect(validationSource).toContain('className={styles.paperInset}');
    expect(validationSource).toContain('className={styles.paperAlert}');
  });

  it('keeps project glossary cards, badges, and alerts on explicit paper semantics', () => {
    expect(glossarySource.match(/data-remis-surface="paper"/g)).toHaveLength(2);
    expect(glossarySource.match(/className=\{styles\.paperPanel\}/g)).toHaveLength(2);
    expect(glossarySource).toContain('className={styles.paperAlert}');
    expect(definitionsSource).toContain(
      "[data-remis-surface] .mantine-Badge-root[data-variant='light']",
    );
    expect(definitionsSource).toContain("[data-remis-surface] .mantine-Alert-root");
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

  it('reads every ownership module that carries the project material contract', () => {
    expect(Object.keys(materialSources)).toHaveLength(7);
    expect(materialSources['src/components/tools/KanbanBoard.module.css']).toContain('.boardContainer');
    expect(materialSources['src/components/tools/KanbanColumn.module.css']).toContain('.columnHeader');
    expect(materialSources['src/components/tools/TaskCard.module.css']).toContain('.taskCardDragging');
    expect(materialSources['src/components/projectManagement/ProjectListView.module.css']).toContain('.projectCard');
    expect(materialSources['src/components/projectManagement/ProjectDashboardView.module.css']).toContain('.tabsPanel');
    expect(materialSources['src/components/project/ProjectDetailSurfaces.module.css']).toContain('.paperAlert');
    expect(materialSources['src/components/project/ProjectHeader.module.css']).toContain('.startTranslationButton');
  });
});
