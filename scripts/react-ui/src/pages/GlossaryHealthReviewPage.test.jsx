import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GlossaryHealthReviewPage from './GlossaryHealthReviewPage';
import api from '../utils/api';

const navigateMock = vi.fn();
const translateMock = (key, options) => options?.defaultValue || key;

vi.mock('../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock('react-router', () => ({
  useNavigate: () => navigateMock,
  useParams: () => ({ taskId: 'health-task' }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: translateMock,
  }),
}));

const { MantineProvider } = await import('@mantine/core');

const healthTask = {
  task_id: 'health-task',
  title: 'Check glossary assets',
  status: 'completed',
  result: {
    types: ['glossary_health_report', 'advisory_review'],
    metadata: {
      score: 81,
      issue_count: 2,
      target_lang: 'zh-CN',
      issues: [{
        code: 'placeholder_mismatch',
        severity: 'error',
        count: 2,
        message: 'Source and translation placeholders differ',
        items: [{
          detail: 'zh-CN placeholders differ.',
          entry_id: 'token-a',
          glossary_id: 7,
          glossary_name: 'Health Test',
          game_id: 'vic3',
          source: 'Army $COUNT$',
        }],
      }],
      ai_advice: [{
        case_id: 'placeholder_mismatch:token-a',
        entry_id: 'token-a',
        issue_code: 'placeholder_mismatch',
        suggested_source: null,
        suggested_translation: '陆军 $COUNT$',
        recommendation: 'Preserve the source placeholder in the Chinese translation.',
        rationale: 'The $COUNT$ token is required at runtime.',
      }],
      ai_review_plan: {
        case_count: 1,
        batch_count: 1,
        batch_sizes: [1],
      },
    },
  },
};

describe('GlossaryHealthReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({ data: healthTask });
    api.post.mockResolvedValue({
      data: {
        entries: [{
          id: 'token-a',
          source: 'Army $COUNT$',
          translations: { 'zh-CN': '陆军' },
          notes: 'Existing note.',
          variants: {},
          abbreviations: {},
          metadata: { source_lang: 'en', target_lang: 'zh-CN' },
        }],
        totalCount: 1,
      },
    });
    api.put.mockResolvedValue({ data: {} });
  });

  it('loads the task report and supports repairing an identified glossary entry', async () => {
    render(<MantineProvider><GlossaryHealthReviewPage /></MantineProvider>);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/api/tasks/health-task');
    });
    expect(await screen.findByTestId('glossary-health-workbench')).toBeInTheDocument();
    expect(screen.getByText('glossary_health_penalty_error')).toBeInTheDocument();
    expect(screen.getAllByText('Army $COUNT$').length).toBeGreaterThan(0);
    expect(screen.getByText('Suggestion — review required')).toBeInTheDocument();
    expect(screen.getByText(
      'Only the values in this section are saved. AI rationale is not added to notes automatically.',
    )).toBeInTheDocument();

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/glossary/search', expect.objectContaining({
        query: 'token-a',
      }));
    });
    expect(await screen.findByDisplayValue('陆军')).toBeInTheDocument();
    const notes = screen.getByLabelText('glossary_notes');
    expect(notes.value).toBe('Existing note.');
    expect(screen.getByText('Preserve the source placeholder in the Chinese translation.')).toBeInTheDocument();
    expect(screen.getByText('The $COUNT$ token is required at runtime.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Apply suggestion to editable draft' }));
    expect(await screen.findByDisplayValue('陆军 $COUNT$')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Save and review next' }));

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith('/api/glossary/entry/token-a', expect.objectContaining({
        translations: expect.objectContaining({ 'zh-CN': '陆军 $COUNT$' }),
        notes: 'Existing note.',
      }));
    });

    fireEvent.click(screen.getByRole('button', { name: 'button_back' }));
    expect(navigateMock).toHaveBeenCalledWith('/tasks/health-task');
  });
});
