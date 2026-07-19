import { describe, expect, it } from 'vitest';
import { sanitizeCopilotLogLine } from './copilotPageContext';

describe('sanitizeCopilotLogLine', () => {
  it('redacts secrets and local Windows paths', () => {
    const result = sanitizeCopilotLogLine('api_key=sk-private reading J:\\mods\\secret\\file.yml');
    expect(result).not.toContain('sk-private');
    expect(result).not.toContain('J:\\mods');
    expect(result).toContain('[REDACTED]');
    expect(result).toContain('[LOCAL_PATH]');
  });
});
