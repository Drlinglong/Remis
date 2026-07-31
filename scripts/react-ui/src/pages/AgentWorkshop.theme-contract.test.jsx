import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const pageSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/pages/AgentWorkshopPage.jsx'),
  'utf8',
);
const pageCss = fs.readFileSync(
  path.resolve(process.cwd(), 'src/pages/AgentWorkshop.module.css'),
  'utf8',
);

describe('Agent Workshop visual reliability contract', () => {
  it('uses semantic surface roles instead of theme-specific overrides', () => {
    expect(pageSource).toContain('data-remis-surface="canvas"');
    expect(pageSource).toContain('data-remis-surface="surface"');
    expect(pageSource).toContain('data-remis-surface="paper"');
    expect(pageCss).toContain('var(--paper-text-main)');
    expect(pageCss).toContain('var(--paper-text-muted)');
    expect(pageCss).not.toMatch(/data-theme|\.byzantine|\.wwii|\.medieval/);
  });

  it('keeps page scrolling under the shared layout and wraps long paths', () => {
    const containerRule = pageCss.match(/\.container\s*\{[^}]*\}/s)?.[0] || '';
    expect(containerRule).not.toContain('overflow-y');
    expect(pageSource).not.toContain('className={translationStyles.executionStep}');
    expect(pageCss).toContain('overflow-wrap: anywhere');
  });

  it('binds the approval overlay and actions to paper surface semantics', () => {
    expect(pageSource).toContain('content: styles.approvalModalContent');
    expect(pageSource).toContain('data-remis-action="primary"');
    expect(pageSource).toContain('data-remis-action="secondary"');
    expect(pageCss).toContain('.approvalModalHeader');
    expect(pageCss).toContain('.approvalWarning');
  });

  it('binds every scan summary card and value to readable paper text tokens', () => {
    expect(pageSource.match(/className=\{styles\.summaryCard\}/g)).toHaveLength(3);
    expect(pageSource.match(/data-remis-surface="paper"/g).length).toBeGreaterThanOrEqual(3);
    expect(pageSource.match(/className=\{styles\.summaryValue\}/g)).toHaveLength(3);
    expect(pageCss).toMatch(/--summary-text-main:\s*var\(--paper-text-main,\s*var\(--surface-text-main\)\)/);
    expect(pageCss).toMatch(/\.summaryCard:global\(\.mantine-Card-root\)\s*\{[\s\S]*?color:\s*var\(--summary-text-main\)\s*!important;/);
    expect(pageCss).toMatch(/\.summaryValue\s*\{[\s\S]*?color:\s*var\(--summary-text-main\)\s*!important;[\s\S]*?-webkit-text-fill-color:\s*currentColor\s*!important;/);
  });
});
