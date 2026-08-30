import path from 'path';
import { fileURLToPath } from 'url';
import { describe, expect, it } from 'vitest';
import { loadTauriDevConfig, resolveTauriDevProfile } from './tauriDevProfile';

const frontendDirectory = path.dirname(fileURLToPath(import.meta.url));

describe('Tauri development profile', () => {
  it('keeps the stable development identity and origin deterministic', () => {
    const profile = resolveTauriDevProfile('stable');
    const config = loadTauriDevConfig(frontendDirectory, profile);

    expect(profile.port).toBe(5174);
    expect(config.identifier).toBeUndefined();
    expect(config.build.devUrl).toBe('http://127.0.0.1:5174');
    expect(config.bundle.active).toBe(false);
  });

  it('keeps Agent Preview development separate from the packaged Preview', () => {
    const profile = resolveTauriDevProfile('agent-preview');
    const config = loadTauriDevConfig(frontendDirectory, profile);

    expect(profile.port).toBe(5175);
    expect(config.productName).toBe('Remis Agent Preview Dev');
    expect(config.identifier).toBe('com.remis.modfactory.agent-preview.dev');
    expect(config.identifier).not.toBe('com.remis.modfactory.agent-preview');
    expect(config.build.devUrl).toBe('http://127.0.0.1:5175');
    expect(config.bundle.active).toBe(false);
    expect(config.bundle.externalBin).toEqual([]);
  });

  it('fails closed for unknown channels and invalid ports', () => {
    expect(() => resolveTauriDevProfile('nightly')).toThrow(/Unsupported/);
    expect(() => resolveTauriDevProfile('agent-preview', 'nope')).toThrow(/Invalid/);
  });
});
