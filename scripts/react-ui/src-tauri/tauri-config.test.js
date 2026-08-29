import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));

const readConfig = (filename) => JSON.parse(
  fs.readFileSync(path.join(currentDirectory, filename), 'utf-8'),
);

describe('Tauri sidecar configuration', () => {
  it('requires the frozen backend only for packaged builds', () => {
    const releaseConfig = readConfig('tauri.conf.json');
    const developmentConfig = readConfig('tauri.dev.conf.json');

    expect(releaseConfig.bundle.externalBin).toEqual(['web_server']);
    expect(developmentConfig.bundle.active).toBe(false);
    expect(developmentConfig.bundle.externalBin).toEqual([]);
  });

  it('gives Agent Preview its own install and application identity', () => {
    const stable = readConfig('tauri.conf.json');
    const preview = readConfig('tauri.agent-preview.conf.json');

    expect(preview.productName).toBe('Remis Agent Preview');
    expect(preview.version).toBe('3.1.7-agent-preview.1');
    expect(preview.productName).not.toBe(stable.productName);
    expect(preview.identifier).not.toBe(stable.identifier);
    expect(preview.bundle.targets).toEqual(['nsis']);
  });
});
