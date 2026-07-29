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
});
