import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const sourceRoot = join(process.cwd(), 'src');

const collectProductionSources = (directory) => readdirSync(directory, { withFileTypes: true })
  .flatMap((entry) => {
    const entryPath = join(directory, entry.name);
    if (entry.isDirectory()) return collectProductionSources(entryPath);
    return entry.name.includes('.test.') ? [] : [entryPath];
  });

describe('localized date-time usage', () => {
  it('does not let production UI formatting fall back to the system locale', () => {
    const violations = collectProductionSources(sourceRoot)
      .flatMap((path) => {
        const source = readFileSync(path, 'utf8');
        return [
          /Intl\.DateTimeFormat\(undefined/.test(source) && `${path}: Intl.DateTimeFormat(undefined)`,
          /\.toLocale(?:Date|Time)?String\(\s*\)/.test(source) && `${path}: parameterless toLocale*String`,
        ].filter(Boolean);
      });

    expect(violations).toEqual([]);
  });
});
