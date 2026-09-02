import React from 'react';
import { MantineProvider } from '@mantine/core';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ArchiveABReviewPage from './ArchiveABReviewPage';
import archiveABReviewService from '../services/archiveABReviewService';

const service = archiveABReviewService;
const translate = vi.hoisted(() => (key) => key);

vi.mock('../config/features', () => ({ FEATURES: { ENABLE_ARCHIVE_AB_REVIEW: true } }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: translate }) }));
vi.mock('@mantine/core', async () => {
  const actual = await vi.importActual('@mantine/core');
  return {
    ...actual,
    Select: ({ label, value, onChange, data }) => (
      <label>
        {label}
        <select aria-label={label} value={value || ''} onChange={(event) => onChange(event.currentTarget.value)}>
          <option value="" />
          {(data || []).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
    ),
  };
});
vi.mock('../services/archiveABReviewService', () => ({
  default: { getStatus: vi.fn(), loadCases: vi.fn(), submitReview: vi.fn() },
}));
vi.mock('../components/archiveABReview/ArchiveABReviewPanel', () => ({
  default: ({ cases, activeIndex, onChangeCase, onSubmit }) => {
    const item = cases[activeIndex];
    return (
      <div>
        <h2 data-testid="page-case-title">{item?.case_id || 'no-case'}</h2>
        {item?.revealed && <div data-testid="page-reveal" aria-live="polite">revealed</div>}
        <button type="button" onClick={() => onSubmit({ manifest_id: item.manifest_id, case_id: item.case_id, selection: 'left', error_tags: [], confidence: 1, note: '' })}>submit</button>
        <button type="button" onClick={() => onChangeCase(activeIndex + 1)}>next</button>
      </div>
    );
  },
}));

const caseOf = (caseId, datasetId = 'dataset-a') => ({
  case_id: caseId,
  manifest_id: 'run-1',
  dataset_id: datasetId,
  case_kind: 'event_chain',
  source_entries: [],
  anonymous_outputs: [],
});

const responseOf = (cases) => ({ manifests: [{ manifest_id: 'run-1', reviewable_case_count: cases.length }], cases, total_count: cases.length, reviewed_count: 0 });

describe('ArchiveABReviewPage state and request boundaries', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('stays on the submitted case, shows reveal, and advances only on manual Next', async () => {
    service.getStatus.mockResolvedValue({ enabled: true });
    service.loadCases.mockResolvedValue(responseOf([caseOf('case-1'), caseOf('case-2')]));
    service.submitReview.mockResolvedValue({ case: { ...caseOf('case-1'), revealed: true, reveal: { semantic_identity: {} } } });
    render(<MantineProvider><ArchiveABReviewPage /></MantineProvider>);

    expect(await screen.findByTestId('page-case-title')).toHaveTextContent('case-1');
    expect(service.loadCases).toHaveBeenCalledWith(expect.objectContaining({ status: 'all' }), expect.any(Object));
    fireEvent.click(screen.getByRole('button', { name: 'submit' }));
    await waitFor(() => expect(service.submitReview).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId('page-reveal')).toBeInTheDocument());
    expect(screen.getByTestId('page-case-title')).toHaveTextContent('case-1');
    fireEvent.click(screen.getByRole('button', { name: 'next' }));
    await waitFor(() => expect(screen.getByTestId('page-case-title')).toHaveTextContent('case-2'));
  });

  it('ignores an older out-of-order filter response and aborts it', async () => {
    service.getStatus.mockResolvedValue({ enabled: true });
    const requests = [];
    service.loadCases.mockImplementation((params, options) => new Promise((resolve) => {
      requests.push({ params, options, resolve });
    }));
    render(<MantineProvider><ArchiveABReviewPage /></MantineProvider>);
    await waitFor(() => expect(requests).toHaveLength(1));
    requests[0].resolve(responseOf([caseOf('old-case', 'dataset-a'), caseOf('new-case', 'dataset-b')]));
    await screen.findByText('old-case');

    fireEvent.change(screen.getByLabelText('archive_ab_review.dataset'), { target: { value: 'dataset-b' } });
    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests[0].options.signal.aborted).toBe(true);
    requests[1].resolve(responseOf([caseOf('new-case', 'dataset-b')]));
    await screen.findByText('new-case');
    requests[0].resolve(responseOf([caseOf('stale-case', 'dataset-a')]));
    await waitFor(() => expect(screen.queryByText('stale-case')).not.toBeInTheDocument());
    expect(screen.getByText('new-case')).toBeInTheDocument();
  });

  it('keeps the page closed when the backend capability is disabled', async () => {
    service.getStatus.mockResolvedValue({ enabled: false, reason: 'developer flag required' });
    render(<MantineProvider><ArchiveABReviewPage /></MantineProvider>);
    expect(await screen.findByText('developer flag required')).toBeInTheDocument();
    expect(service.loadCases).not.toHaveBeenCalled();
  });
});
