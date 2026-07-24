import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { notifications } from '@mantine/notifications';

import api from '../../utils/api';
import JudgmentCourt from './JudgmentCourt';

const translate = vi.hoisted(() => (key) => key);

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: translate }),
}));

vi.mock('@mantine/notifications', () => ({
  notifications: { show: vi.fn() },
}));

vi.mock('../../utils/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

const pendingCandidates = [
  {
    id: 1,
    original: 'Hyperlane Relay',
    suggestion: 'Гиперретранслятор',
    reasoning: '采用语义翻译。',
    context_snippets: ['Hyperlane Relay activates.'],
    context_evidence: [{
      snippet: 'Hyperlane Relay activates.',
      source_file: 'events/relay_events.yml',
      line: null,
    }],
    source_lang: 'en',
    target_lang: 'ru',
    review_language: 'zh-CN',
    duplicate_matches: [],
  },
  {
    id: 2,
    original: 'Quantum Anchor',
    suggestion: 'Квантовый якорь',
    reasoning: '沿用既有词典译法。',
    context_snippets: [],
    duplicate_matches: [{ entry_id: 'existing-2', source_term: 'Quantum Anchor' }],
  },
  {
    id: 3,
    original: 'Void Beacon',
    suggestion: '',
    reasoning: '没有可靠建议。',
    context_snippets: [],
    duplicate_matches: [],
  },
];

const processedCandidates = [{
  ...pendingCandidates[0],
  status: 'approved',
}];

describe('JudgmentCourt adoption and recovery workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((url) => {
      if (url === '/api/projects') {
        return Promise.resolve({
          data: { projects: [{ project_id: 'project-1', name: 'Stellaris Demo' }] },
        });
      }
      if (url === '/api/neologisms?project_id=project-1') {
        return Promise.resolve({ data: { candidates: pendingCandidates } });
      }
      if (url === '/api/neologisms?project_id=project-1&view=processed') {
        return Promise.resolve({ data: { candidates: processedCandidates } });
      }
      if (url === '/api/neologisms/project-glossary/project-1') {
        return Promise.resolve({
          data: { glossary_id: 3, game_id: 'stellaris', name: 'Project Glossary' },
        });
      }
      throw new Error(`Unexpected GET ${url}`);
    });
    api.post.mockResolvedValue({ data: { status: 'success' } });
  });

  it('adopts processable suggestions, reuses duplicates, and keeps blank failures selected', async () => {
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    await screen.findByRole('button', { name: /Hyperlane Relay/ });
    expect(screen.getByText('events/relay_events.yml')).toBeInTheDocument();
    expect(screen.getByText('neologism_review.court.review_language_badge')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('checkbox', {
      name: 'neologism_review.court.select_all',
    }));
    fireEvent.click(screen.getByRole('button', {
      name: 'neologism_review.court.batch_approve',
    }));
    fireEvent.click(await screen.findByRole('button', {
      name: 'neologism_review.court.batch_approve_confirm',
    }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledTimes(2);
      expect(api.post).toHaveBeenCalledWith('/api/neologisms/1/approve', expect.objectContaining({
        resolution: 'approve_project',
        final_translation: 'Гиперретранслятор',
      }));
      expect(api.post).toHaveBeenCalledWith('/api/neologisms/2/approve', expect.objectContaining({
        resolution: 'duplicate',
      }));
      expect(screen.queryByRole('button', { name: /Hyperlane Relay/ })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Quantum Anchor/ })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Void Beacon/ })).toBeInTheDocument();
      expect(screen.getByRole('checkbox', {
        name: 'neologism_review.court.select_candidate',
      })).toBeChecked();
      expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
        title: 'neologism_review.court.batch_partial_title',
        color: 'orange',
      }));
    });
  });

  it('restores an approved candidate while explaining that its glossary entry is preserved', async () => {
    api.post.mockResolvedValue({
      data: {
        status: 'success',
        previous_status: 'approved',
        glossary_entry_preserved: true,
      },
    });
    render(
      <MantineProvider>
        <JudgmentCourt
          selectedProject="project-1"
          onSelectedProjectChange={vi.fn()}
        />
      </MantineProvider>,
    );

    await screen.findByRole('button', { name: /Hyperlane Relay/ });
    fireEvent.click(screen.getByText('neologism_review.court.processed_docket'));
    await screen.findByText('neologism_review.court.restore_preserves_glossary_note');
    fireEvent.click(screen.getByRole('button', {
      name: 'neologism_review.court.restore_candidate',
    }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/neologisms/1/restore', {
        project_id: 'project-1',
      });
      expect(notifications.show).toHaveBeenCalledWith(expect.objectContaining({
        title: 'neologism_review.court.restored_title',
        message: 'neologism_review.court.restored_glossary_preserved',
      }));
      expect(screen.queryByRole('button', { name: /Hyperlane Relay/ })).not.toBeInTheDocument();
    });
  });
});
