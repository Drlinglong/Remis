import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const modalSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/components/projectManagement/CreateProjectModal.jsx'),
  'utf8',
);
const modalCss = fs.readFileSync(
  path.resolve(process.cwd(), 'src/components/projectManagement/CreateProjectModal.module.css'),
  'utf8',
);

describe('Create Project modal visual reliability contract', () => {
  it('binds the overlay and its supporting controls to paper surface semantics', () => {
    expect(modalSource).toContain('content: styles.modalContent');
    expect(modalSource).toContain('header: styles.modalHeader');
    expect(modalSource).toContain('data-remis-surface="paper"');
    expect(modalSource).toContain('className={styles.importModeAlert}');
    expect(modalSource.match(/classNames=\{\{ input: styles\.modalInput \}\}/g)).toHaveLength(2);
    expect(modalCss).toContain('var(--paper-text-main)');
    expect(modalCss).toContain('var(--paper-text-muted)');
    expect(modalCss).toContain('.modalInput::placeholder');
    expect(modalCss).toContain('caret-color: var(--paper-text-main, var(--surface-text-main))');
    expect(modalCss).toContain('var(--paper-bg, var(--surface-bg-solid))');
    expect(modalCss).not.toMatch(/data-theme|\.byzantine|\.wwii|\.medieval/);
  });

  it('keeps the modal opaque and removes inherited theme text effects', () => {
    const contentRule = modalCss.match(/\.modalContent\s*\{[^}]*\}/s)?.[0] || '';
    expect(contentRule).toContain('background-image: none');
    expect(contentRule).toContain('backdrop-filter: none');
    expect(modalCss).toContain('text-shadow: none');
  });
});
