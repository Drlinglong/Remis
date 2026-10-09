import React from 'react';
import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { normalizePreScanResults } from '../../utils/preScanPayload';
import { buildPreScanLanguageSummary } from './preScanSummary';
import { PreScanResultsStep } from './PreScanResultsStep';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key) => key }) }));
vi.mock('../shared/PerformanceControlPanel', () => ({ default: () => null }));
vi.mock('./TelemetrySummary', () => ({ default: () => null }));

describe('pre-scan payload integrity', () => {
  it('unwraps record arrays and preserves language counts and semantic text', () => {
    const data = normalizePreScanResults({ data: { total: 4, file_summaries: { items: [{
      file_path: 'a.yml', target_lang: 'zh-CN', total: 4, unchanged: 3, new: 1,
      dirty_entries: { data: [{ key: 'a', source: '$OWNER$' }] },
    }] } } });
    expect(data.file_summaries[0].dirty_entries[0].source).toBe('$OWNER$');
    expect(buildPreScanLanguageSummary({ scanResults: data }).aggregateTotal).toBe(4);
    expect(data.payloadError).toBeUndefined();
  });

  it.each([null, { file_summaries: false }, { file_summaries: {} }, { file_summaries: [null] },
    { file_summaries: [{ dirty_entries: {} }] }, { file_summaries: [{ dirty_entries: [null] }] },
  ])('reports malformed results and blocks translation: %j', (scanResults) => {
    const data = normalizePreScanResults(scanResults);
    expect(data.payloadError).toMatch(/Invalid/);
    const startTranslation = vi.fn();
    render(<MantineProvider><PreScanResultsStep scanResults={scanResults}
      selectedLangs={['zh-CN']} startTranslation={startTranslation} /></MantineProvider>);
    expect(screen.getByText(data.payloadError)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'incremental_translation.step_4_title' })).toBeDisabled();
    expect(startTranslation).not.toHaveBeenCalled();
  });
});
