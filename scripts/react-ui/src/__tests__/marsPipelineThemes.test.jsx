import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const themes = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];
const readSource = (file) => readFileSync(resolve(process.cwd(), file), 'utf8');
const definitions = readSource('src/themes/definitions.css');
const delivery = readSource('src/components/project/MarsPipelineDelivery.jsx');
const importFlow = readSource('src/components/project/MarsPipelineImport.jsx');
const importStyles = readSource('src/components/project/MarsPipelineImport.module.css');
const createProject = readSource('src/components/projectManagement/CreateProjectModal.jsx');
const visualLab = readSource('src/visual-fixtures/VisualReliabilityLab.jsx');
const marsVisual = readSource('src/visual-fixtures/MarsPipelineVisualFixture.jsx');

describe('Mars pipeline semantic theme surfaces', () => {
  it('places delivery and project creation surfaces on shared theme tokens', () => {
    expect(delivery).toContain('data-remis-surface="paper"');
    expect(createProject).toContain('<Stack data-remis-surface="paper">');
    expect(importFlow).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(/i);
    expect(importStyles).toContain('--paper-text-main');
    expect(importStyles).toContain('--paper-bg');
    expect(importStyles).toContain('mantine-Accordion-control');
    expect(delivery).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(/i);

    for (const theme of themes) {
      const block = definitions.match(
        new RegExp(`\\[data-theme=['"]${theme}['"]\\]\\s*\\{([\\s\\S]*?)\\n\\}`),
      )?.[1] || '';
      expect(block, `${theme}: paper background`).toContain('--paper-bg:');
      expect(block, `${theme}: paper foreground`).toContain('--paper-text-main:');
      expect(block, `${theme}: muted paper foreground`).toContain('--paper-text-muted:');
    }
  });

  it('routes a static Mars dialog fixture through the five-theme visual lab', () => {
    expect(visualLab).toContain("contract === 'mars-pipeline'");
    expect(marsVisual).toContain('controller={controller}');
    expect(marsVisual).toContain('data-testid="mars-pipeline-visual-fixture"');
    expect(marsVisual).toContain('source_copy');
  });
});
