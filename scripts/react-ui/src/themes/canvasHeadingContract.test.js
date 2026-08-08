import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';

const readSource = (relativePath) => readFileSync(path.resolve(process.cwd(), relativePath), 'utf8');

describe('canvas heading theme contract', () => {
  it('removes legacy decorative shadows from structural headings', () => {
    const definitions = readSource('src/themes/definitions.css');
    const contractStart = definitions.indexOf(
      "html[data-theme] [data-remis-surface='canvas'] .mantine-Title-root",
    );
    const contract = definitions.slice(contractStart, contractStart + 420);

    expect(contractStart).toBeGreaterThan(-1);
    expect(contract).toContain('color: var(--canvas-text-main);');
    expect(contract).toContain('text-shadow: none;');
    expect(contract).toContain('background: transparent;');
  });

  it('marks the affected workbench pages as canvas surfaces', () => {
    [
      'src/pages/HomePage.jsx',
      'src/pages/InitialTranslation.jsx',
      'src/pages/IncrementalTranslationPage.jsx',
      'src/components/projectManagement/ProjectListView.jsx',
    ].forEach((sourcePath) => {
      expect(readSource(sourcePath), sourcePath).toContain('data-remis-surface="canvas"');
    });
  });
});
