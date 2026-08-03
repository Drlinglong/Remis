import React from 'react';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import ContextAnalysisReportPanel from './ContextAnalysisReportPanel';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

describe('ContextAnalysisReportPanel', () => {
  it('shows deterministic gates, usage, supporting context, and audit sections', () => {
    render(<MantineProvider><ContextAnalysisReportPanel report={{
      input_and_chunking: { source_items: 10, local_units: 6, chunks: 2 },
      source_integrity: { totals: { raw: 10, gate_passed: true } },
      unit_assignment_integrity: {
        missing: [], duplicate: [], unexpected: [], unassigned: 1, multi_linked: 0,
        repair_reasons: [{ stage: 'assignment', reason: 'coverage_validation', detail: 'missing unit_5' }],
      },
      coverage_and_contamination: { delivery_coverage: 0.9 },
      model_execution: {
        call_count: 3, reasoning_profile: 'reasoning_effort=high',
        token_usage: { total_tokens: 1200 }, cost: { amount: 0.01, complete: true },
      },
      final_chain_resolution: [{
        chain_id: 'worm_signal', primary_members: 4, supporting_context: 2,
        theme_related: 0, evidence: 2,
      }],
      chunk_boundary_impact: { cross_chunk_merged_chains: ['worm_signal'] },
      unassigned_units: [{ unit_id: 'unit_5', localization_keys: ['generic_button'], chunk: 2 }],
    }} /></MantineProvider>);

    expect(screen.getByTestId('context-analysis-report')).toBeInTheDocument();
    expect(screen.getByText('context_report.gates_passed')).toBeInTheDocument();
    expect(screen.getByText('worm_signal')).toBeInTheDocument();
    expect(screen.getByText('reasoning_effort=high', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('unit_5')).toBeInTheDocument();
  });
});
