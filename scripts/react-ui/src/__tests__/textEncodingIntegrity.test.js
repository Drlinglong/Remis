import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '../../../../');

const scanRoots = [
  path.join(repoRoot, 'scripts', 'core'),
  path.join(repoRoot, 'scripts', 'routers'),
  path.join(repoRoot, 'scripts', 'schemas'),
  path.join(repoRoot, 'scripts', 'react-ui', 'src'),
  path.join(repoRoot, 'scripts', 'react-ui', 'src-tauri'),
].filter((dirPath) => {
  try {
    return statSync(dirPath).isDirectory();
  } catch {
    return false;
  }
});

const excludedDirs = new Set([
  '.git',
  '__pycache__',
  'archive',
  'build',
  'data',
  'dist',
  'node_modules',
  'source_mod',
  'my_translation',
  'sandbox_test_tmp',
  'target',
  '__tests__',
  'tests_tmp',
  'tmp',
  'venv',
]);

const excludedFiles = new Set([
  'package-lock.json',
  'package.json',
]);

const includedExtensions = new Set([
  '.py',
  '.js',
  '.jsx',
  '.ts',
  '.tsx',
  '.json',
  '.toml',
  '.md',
  '.css',
  '.yml',
  '.yaml',
]);

const mojibakeMarkers = [
  '鏂囦欢',
  '寮€鍙',
  '缈昏瘧浠诲',
  '浠诲姟鏈',
  '闄愬埗杩',
  '娴呮嫹璐',
  '宸蹭笂浼',
  '澶勭悊澶辫触',
];

function walk(dirPath, output = []) {
  let entries = [];

  try {
    entries = readdirSync(dirPath);
  } catch {
    return output;
  }

  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry);
    let stats;

    try {
      stats = statSync(fullPath);
    } catch {
      continue;
    }

    if (stats.isDirectory()) {
      if (!excludedDirs.has(entry)) {
        walk(fullPath, output);
      }
      continue;
    }

    if (includedExtensions.has(path.extname(entry).toLowerCase())) {
      if (fullPath === __filename) {
        continue;
      }
      output.push(fullPath);
    }
  }

  return output;
}

describe('text encoding integrity', () => {
  it('keeps business code free of placeholder question marks and known mojibake markers', () => {
    const offenders = [];

    for (const filePath of scanRoots.flatMap((scanRoot) => walk(scanRoot))) {
      if (excludedFiles.has(path.basename(filePath))) {
        continue;
      }

      let text;

      try {
        text = readFileSync(filePath, 'utf8');
      } catch {
        continue;
      }

      const lines = text.split(/\r?\n/);
      lines.forEach((line, index) => {
        const trimmed = line.trim();
        const hasQuestionPlaceholder = /\?{3,}|\?{8,}/.test(trimmed);
        const mojibakeMarker = mojibakeMarkers.find((marker) => line.includes(marker));

        if (hasQuestionPlaceholder || mojibakeMarker) {
          offenders.push(`${path.relative(repoRoot, filePath)}:${index + 1}:${trimmed}`);
        }
      });
    }

    expect(offenders, offenders.join('\n')).toEqual([]);
  });
});
