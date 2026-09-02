import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../../utils/api';
import JudgmentCourt from './JudgmentCourt';

const labels = {
  'neologism_review.court.approve_all': 'Approve and save all ({{count}})',
  'neologism_review.court.card_view': 'Cards',
  'neologism_review.court.detail_view': 'Detail',
  'neologism_review.court.docket_view': 'Docket status',
  'neologism_review.court.open_candidate_detail': 'Open details for {{term}}',
  'neologism_review.court.reject_all_duplicates': 'Reject all duplicates ({{count}})',
  'neologism_review.court.search_label': 'Search candidate source terms and translations',
  'neologism_review.court.search_placeholder': 'Search source or translation',
  'neologism_review.court.tier_a': 'A · 3+ occurrences ({{count}})',
  'neologism_review.court.tier_b': 'B · 2 occurrences ({{count}})',
  'neologism_review.court.tier_c': 'C · 1 occurrence or less ({{count}})',
  'neologism_review.court.tier_all': 'All tiers',
  'neologism_review.court.tier_filter': 'Importance filter',
  'neologism_review.court.view_mode': 'Review layout',
};

const translate = vi.hoisted(() => (key, values = {}) => {
  let output = labels[key] || key;
  Object.entries(values).forEach(([name, value]) => {
    output = output.replace(`{{${name}}}`, String(value));
  });
  return output;
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: translate }),
}));

vi.mock('@mantine/notifications', () => ({
  notifications: { show: vi.fn() },
}));

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

const candidates = [
  {
    id: 'a', original: 'Alpha Relay', suggestion: '阿尔法中继', frequency: 4,
    reasoning: 'A', context_evidence: [], duplicate_matches: [],
  },
  {
    id: 'b', original: 'Beta Anchor', suggestion: '贝塔锚点', frequency: 2,
    reasoning: 'B', context_evidence: [], duplicate_matches: [],
  },
  {
    id: 'c', original: 'Gamma Beacon', suggestion: '伽马信标', frequency: 1,
    reasoning: 'C', context_evidence: [], duplicate_matches: [],
  },
  {
    id: 'duplicate', original: 'Known Gate', suggestion: '既有星门', frequency: 3,
    reasoning: 'Existing', context_evidence: [],
    duplicate_matches: [{ entry_id: 'main-1', source_term: 'Known Gate' }],
  },
];

const renderCourt = () => render(
  <MantineProvider>
    <JudgmentCourt selectedProject="project-1" onSelectedProjectChange={vi.fn()} />
  </MantineProvider>,
);

describe('JudgmentCourt dual view', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    HTMLElement.prototype.scrollIntoView = vi.fn();
    api.get.mockImplementation((url) => {
      if (url === '/api/projects') {
        return Promise.resolve({ data: { projects: [{ project_id: 'project-1', name: 'Demo' }] } });
      }
      if (url === '/api/neologisms?project_id=project-1') {
        return Promise.resolve({ data: { candidates } });
      }
      if (url === '/api/neologisms/project-glossary/project-1') {
        return Promise.resolve({ data: { glossary_id: 3, name: 'Project Glossary' } });
      }
      throw new Error(`Unexpected GET ${url}`);
    });
    api.post.mockResolvedValue({ data: { status: 'success' } });
  });

  it('groups cards by frequency, keeps C collapsed, and hands focus back to the selected detail', async () => {
    renderCourt();
    await screen.findByRole('button', { name: /Alpha Relay/ });

    fireEvent.click(screen.getByText('Cards'));
    expect(screen.getByTestId('judgment-court-card-view')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'A · 3+ occurrences (2)' })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: 'B · 2 occurrences (1)' })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: 'C · 1 occurrence or less (1)' })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('button', { name: 'Open details for Gamma Beacon' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'C · 1 occurrence or less (1)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Open details for Gamma Beacon' }));

    await waitFor(() => {
      expect(screen.queryByTestId('judgment-court-card-view')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Gamma Beacon/ })).toHaveFocus();
    });
    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it('shares source/translation search and tier filtering between detail and card views', async () => {
    renderCourt();
    await screen.findByRole('button', { name: /Alpha Relay/ });

    fireEvent.change(screen.getByLabelText('Search candidate source terms and translations'), {
      target: { value: '贝塔' },
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Beta Anchor/ })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Alpha Relay/ })).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Cards'));
    expect(screen.getByRole('button', { name: 'Open details for Beta Anchor' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Open details for Alpha Relay' })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Search candidate source terms and translations'), {
      target: { value: '' },
    });
    const tierFilter = screen.getByLabelText('Importance filter');
    fireEvent.click(within(tierFilter).getByText('C'));
    expect(screen.getByRole('button', { name: 'Open details for Gamma Beacon' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Open details for Beta Anchor' })).not.toBeInTheDocument();
  });

  it('requires confirmation before rejecting every duplicate candidate', async () => {
    renderCourt();
    await screen.findByRole('button', { name: 'Reject all duplicates (1)' });

    fireEvent.click(screen.getByRole('button', { name: 'Reject all duplicates (1)' }));
    expect(api.post).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole('button', {
      name: 'neologism_review.court.batch_reject_confirm',
    }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    expect(api.post).toHaveBeenCalledWith('/api/neologisms/duplicate/reject', {
      project_id: 'project-1',
    });
  });

  it('approves all through the existing batch workflow without inserting duplicates', async () => {
    renderCourt();
    await screen.findByText('Approve and save all (4)');

    fireEvent.click(screen.getByText('Approve and save all (4)').closest('button'));
    expect(api.post).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole('button', {
      name: 'neologism_review.court.batch_approve_confirm',
    }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(4));
    const duplicateCall = api.post.mock.calls.find(([url]) => url.includes('/duplicate/approve'));
    const regularCall = api.post.mock.calls.find(([url]) => url.includes('/a/approve'));
    expect(duplicateCall[1]).toEqual(expect.objectContaining({ resolution: 'duplicate' }));
    expect(regularCall[1]).toEqual(expect.objectContaining({ resolution: 'approve_project' }));
  });
});
