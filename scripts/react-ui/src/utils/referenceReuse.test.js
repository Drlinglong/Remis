import { describe, expect, it } from 'vitest';

import {
  referenceEntryIdentity,
  toggleReferenceExclusion,
} from './referenceReuse';

const entry = {
  file_path: 'localization\\english\\countries.yml',
  key: 'TRK:0',
  source_text: 'Turkana',
  target_lang_code: 'zh-CN',
};

describe('reference reuse exclusions', () => {
  it('normalizes file separators for identity matching', () => {
    expect(referenceEntryIdentity(entry)).toBe(
      referenceEntryIdentity({ ...entry, file_path: 'LOCALIZATION/ENGLISH/countries.yml' }),
    );
  });

  it('deselects and reselects a preview entry', () => {
    const excluded = toggleReferenceExclusion([], entry, false);
    expect(excluded).toHaveLength(1);
    expect(toggleReferenceExclusion(excluded, entry, true)).toEqual([]);
  });
});
