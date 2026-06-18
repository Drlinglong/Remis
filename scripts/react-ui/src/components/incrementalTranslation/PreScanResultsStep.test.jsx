import { describe, expect, it } from 'vitest';

import { buildPreScanLanguageSummary } from './preScanSummary';

describe('buildPreScanLanguageSummary', () => {
  it('separates per-language metrics from aggregate translation workload', () => {
    const summary = buildPreScanLanguageSummary({
      selectedLangs: ['zh-CN', 'fr'],
      scanResults: {
        total: 10,
        unchanged: 6,
        new: 4,
        changed: 0,
        file_summaries: [
          { target_lang: 'zh-CN', total: 5, unchanged: 3, new: 2, changed: 0 },
          { target_lang: 'fr', total: 5, unchanged: 3, new: 2, changed: 0 },
        ],
      },
    });

    expect(summary.languageCount).toBe(2);
    expect(summary.perLanguageTotal).toEqual({ min: 5, max: 5, uniform: true });
    expect(summary.perLanguageReusable).toEqual({ min: 3, max: 3, uniform: true });
    expect(summary.perLanguageDirty).toEqual({ min: 2, max: 2, uniform: true });
    expect(summary.aggregateTotal).toBe(10);
    expect(summary.aggregateReusable).toBe(6);
    expect(summary.aggregateDirty).toBe(4);
  });

  it('shows ranges when target languages have different archive baselines', () => {
    const summary = buildPreScanLanguageSummary({
      selectedLangs: ['zh-CN', 'fr'],
      scanResults: {
        total: 11,
        unchanged: 5,
        new: 6,
        changed: 0,
        file_summaries: [
          { target_lang: 'zh-CN', total: 5, unchanged: 3, new: 2, changed: 0 },
          { target_lang: 'fr', total: 6, unchanged: 2, new: 4, changed: 0 },
        ],
      },
    });

    expect(summary.perLanguageTotal).toEqual({ min: 5, max: 6, uniform: false });
    expect(summary.perLanguageReusable).toEqual({ min: 2, max: 3, uniform: false });
    expect(summary.perLanguageDirty).toEqual({ min: 2, max: 4, uniform: false });
  });
});
