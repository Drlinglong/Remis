import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const themeIds = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];
const source = (file) => readFileSync(resolve(process.cwd(), file), 'utf8');
const panelSource = source('src/components/project/ProjectGameSupportPanel.jsx');
const surfaceSource = source('src/components/project/ProjectDetailSurfaces.module.css');
const themesSource = source('src/themes/definitions.css');

describe('ProjectGameSupportPanel theme contract', () => {
  it('uses shared paper surfaces and text tokens for every supported theme', () => {
    expect(panelSource).toContain('data-remis-surface="paper"');
    expect(panelSource).toContain('styles.paperPanel');
    expect(panelSource).toContain('styles.paperInset');
    expect(panelSource).toContain('styles.paperAlert');
    expect(panelSource).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(/i);
    expect(surfaceSource).toMatch(/\.paperPanel\s*\{[\s\S]*?--mantine-color-text:\s*var\(--paper-text-main\)/);

    for (const themeId of themeIds) {
      const block = themesSource.match(
        new RegExp(`\\[data-theme=['"]${themeId}['"]\\]\\s*\\{([\\s\\S]*?)\\n\\}`),
      )?.[1] || '';
      expect(block, `${themeId} must define readable paper colors`).toContain('--paper-bg:');
      expect(block, `${themeId} must define readable paper text`).toContain('--paper-text-main:');
    }
  });
});
