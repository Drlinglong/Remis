import { describe, expect, it } from 'vitest';
import { buildProofreadingUrl } from './proofreadingLinks';

describe('buildProofreadingUrl', () => {
  it('encodes the stable project, file, and entry-key protocol', () => {
    expect(buildProofreadingUrl({
      projectId: 'project 1',
      fileId: 'file/1',
      entryKey: 'event.key:0',
      lineHint: 42,
    })).toBe('/proofreading?projectId=project+1&fileId=file%2F1&entryKey=event.key%3A0&lineHint=42');
  });
});
