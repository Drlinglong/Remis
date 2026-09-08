import React from 'react';
import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ResumeCheckpointModal from './ResumeCheckpointModal';

const translations = {
  'translation_page.resume_modal.title': 'Resume translation',
  'translation_page.resume_modal.content': 'A saved checkpoint is available.',
  'translation_page.resume_modal.completed_files': 'Completed files:',
  'translation_page.resume_modal.question': 'How should the saved checkpoint be handled?',
  'translation_page.resume_modal.start_over': 'Start over',
  'translation_page.resume_modal.resume': 'Resume',
};

const renderModal = (canStartOver, onStartOver = vi.fn()) => {
  render(
    <MantineProvider>
      <ResumeCheckpointModal
        canStartOver={canStartOver}
        checkpointInfo={{ completed_count: 1, total_files_estimate: 2 }}
        onClose={vi.fn()}
        onResume={vi.fn()}
        onStartOver={onStartOver}
        opened
        t={(key) => translations[key] || key}
      />
    </MantineProvider>,
  );
  return onStartOver;
};

describe('ResumeCheckpointModal', () => {
  it('hides Start over when the recovery action is not allowed', () => {
    renderModal(false);

    expect(screen.queryByRole('button', { name: 'Start over' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resume' })).toBeInTheDocument();
  });

  it('shows and invokes Start over when the recovery action is allowed', () => {
    const onStartOver = renderModal(true);

    fireEvent.click(screen.getByRole('button', { name: 'Start over' }));

    expect(onStartOver).toHaveBeenCalledTimes(1);
  });
});
