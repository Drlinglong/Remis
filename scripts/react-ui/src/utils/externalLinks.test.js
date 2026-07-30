import { afterEach, describe, expect, it, vi } from 'vitest';

import { openExternalUrl } from './externalLinks';

describe('openExternalUrl', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('opens HTTP links in a new browser tab outside Tauri', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue({});

    await expect(openExternalUrl('https://github.com/Drlinglong/Remis/issues/153'))
      .resolves.toBe(true);
    expect(open).toHaveBeenCalledWith(
      'https://github.com/Drlinglong/Remis/issues/153',
      '_blank',
      'noopener,noreferrer',
    );
  });

  it('rejects unsupported URL schemes', async () => {
    await expect(openExternalUrl('file:///private.txt')).rejects.toThrow(
      'Only HTTP(S) external links are supported.',
    );
  });
});
