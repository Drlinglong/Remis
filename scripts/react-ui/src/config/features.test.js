import { describe, expect, it } from 'vitest';

describe('build-channel features', () => {
  it('derives Copilot visibility only from the Agent Preview channel', async () => {
    const { BUILD_CHANNEL, FEATURES, IS_AGENT_PREVIEW } = await import('./features');
    const expectedPreview = import.meta.env.VITE_REMIS_BUILD_CHANNEL === 'agent-preview';

    expect(BUILD_CHANNEL).toBe(expectedPreview ? 'agent-preview' : 'stable');
    expect(IS_AGENT_PREVIEW).toBe(expectedPreview);
    expect(FEATURES.ENABLE_REMIS_COPILOT).toBe(expectedPreview);
  });
});
