import { describe, expect, it } from 'vitest';

describe('build-channel features', () => {
  it('exposes released workflow features in stable and Agent Preview channels', async () => {
    const { BUILD_CHANNEL, FEATURES, IS_AGENT_PREVIEW, IS_RELEASED_WORKFLOW_CHANNEL } = await import('./features');
    const { PAGE_REGISTRY } = await import('./pageRegistry');
    const expectedPreview = import.meta.env.VITE_REMIS_BUILD_CHANNEL === 'agent-preview';

    expect(BUILD_CHANNEL).toBe(expectedPreview ? 'agent-preview' : 'stable');
    expect(IS_AGENT_PREVIEW).toBe(expectedPreview);
    expect(IS_RELEASED_WORKFLOW_CHANNEL).toBe(true);
    expect(FEATURES.ENABLE_REMIS_COPILOT).toBe(true);
    expect(FEATURES.ENABLE_CHECKPOINT_RESUME).toBe(true);
    expect(FEATURES.ENABLE_MOD_ARCHIVE).toBe(true);
    expect(PAGE_REGISTRY.find((page) => page.id === 'neologism-review')?.navigation.label)
      .toBe('mod_archive.title');
  });
});
