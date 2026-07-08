import { describe, expect, it, vi } from 'vitest';

import {
  buildCheckpointStatusPayload,
  requestIncrementalCheckpointStatus,
} from './incrementalTranslationCheckpoint';

describe('incrementalTranslationCheckpoint', () => {
  it('builds checkpoint status payloads from project, source path, and targets', () => {
    expect(buildCheckpointStatusPayload({
      project: { project_id: 'project-1' },
      sourcePath: 'J:/mods/Victoria3/localization',
      targetLangs: ['zh-CN', '', 'ja'],
    })).toEqual({
      project_id: 'project-1',
      mod_name: 'localization',
      target_lang_codes: ['zh-CN', 'ja'],
    });
  });

  it('skips checkpoint requests when target languages are empty', async () => {
    const translationService = { getCheckpointStatus: vi.fn() };

    await expect(requestIncrementalCheckpointStatus({
      project: { project_id: 'project-1' },
      sourcePath: 'J:/mods/Victoria3',
      targetLangs: [],
      translationService,
    })).resolves.toEqual({ found: false, info: null, skipped: true });

    expect(translationService.getCheckpointStatus).not.toHaveBeenCalled();
  });

  it('returns checkpoint info only when resumable completed work exists', async () => {
    const translationService = {
      getCheckpointStatus: vi.fn().mockResolvedValue({
        data: { exists: true, completed_count: 3 },
      }),
    };

    await expect(requestIncrementalCheckpointStatus({
      project: { project_id: 'project-1' },
      sourcePath: 'J:\\mods\\Victoria3',
      targetLangs: ['zh-CN'],
      translationService,
    })).resolves.toEqual({
      found: true,
      info: { exists: true, completed_count: 3 },
      skipped: false,
    });
  });
});
