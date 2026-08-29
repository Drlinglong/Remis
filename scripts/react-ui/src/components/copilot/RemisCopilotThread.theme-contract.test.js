import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const threadCss = fs.readFileSync(
  path.resolve(process.cwd(), 'src/components/copilot/RemisCopilotThread.module.css'),
  'utf8',
);

describe('Remis Copilot thread theme contract', () => {
  it('keeps assistant copy readable on its fixed dark message surface', () => {
    expect(threadCss).toMatch(
      /\.assistantMessage \.bubble\s*\{[\s\S]*?--remis-content-text:\s*#f8f9fa;[\s\S]*?background:[\s\S]*?color:\s*#f8f9fa;/,
    );
    expect(threadCss).toMatch(/\.assistantMessage \.markdown a\s*\{[\s\S]*?color:\s*#74c0fc;/);
    expect(threadCss).toMatch(/\.assistantMessage \.metadataBadge\s*\{[\s\S]*?color:\s*#f8f9fa;/);
  });
});
