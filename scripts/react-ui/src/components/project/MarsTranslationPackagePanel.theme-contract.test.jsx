import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const themes = ['victorian', 'byzantine', 'scifi', 'wwii', 'medieval'];
const source = (file) => readFileSync(resolve(process.cwd(), file), 'utf8');
const panel = source('src/components/project/MarsTranslationPackagePanel.jsx');
const dialog = source('src/components/project/MarsTranslationPackageDialog.jsx');
const preview = source('src/components/project/TranslationPackagePreview.jsx');
const surfaces = source('src/components/project/ProjectDetailSurfaces.module.css');
const definitions = source('src/themes/definitions.css');

describe('Mars translation package theme contract', () => {
  it('uses shared paper and elevated surfaces across every supported theme', () => {
    expect(panel).toContain('data-remis-surface="paper"');
    expect(panel).toContain('styles.paperPanel');
    expect(dialog).toContain('data-remis-surface="elevated"');
    expect(preview).toContain('styles.paperInset');
    expect(surfaces).toMatch(/\.paperPanel\s*\{[\s\S]*?--mantine-color-text:\s*var\(--paper-text-main\)/);

    for (const theme of themes) {
      const themeBlock = definitions.match(
        new RegExp(`\\[data-theme=['"]${theme}['"]\\]\\s*\\{([\\s\\S]*?)\\n\\}`),
      )?.[1] || '';
      expect(themeBlock, `${theme} defines paper foreground and background`).toContain('--paper-bg:');
      expect(themeBlock, `${theme} defines paper foreground and background`).toContain('--paper-text-main:');
      expect(themeBlock, `${theme} defines modal foreground and background`).toContain('--elevated-bg:');
      expect(themeBlock, `${theme} defines modal foreground and background`).toContain('--elevated-text-main:');
    }
  });
});
