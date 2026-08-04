import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import ContextArchiveTreeReview from './ContextArchiveTreeReview';
import { treeFixture } from './contextArchiveTreeFixture';

vi.mock('react-i18next', () => ({
    useTranslation: () => ({
        t: (key, options) => options?.defaultValue || key,
    }),
}));

const renderReview = () => render(
    <MantineProvider>
        <ContextArchiveTreeReview treeData={treeFixture} projectId="project-1" releaseId="release-1" />
    </MantineProvider>,
);

describe('ContextArchiveTreeReview', () => {
    it('renders relationship-only tree content and final event context preview', () => {
        renderReview();

        expect(screen.getByTestId('context-tree-review')).toBeInTheDocument();
        expect(screen.getByTestId('context-tree-group-group-arrival')).toBeInTheDocument();
        expect(screen.getAllByText('The expedition arrives.')).toHaveLength(2);
        expect(screen.getByTestId('context-tree-event-context')).toBeInTheDocument();
        expect(screen.getByTestId('context-tree-reference-tier-A')).toHaveAttribute('open');
        expect(screen.getByTestId('context-tree-reference-tier-C')).not.toHaveAttribute('open');
    });

    it('supports creating a story through the accessible form', () => {
        renderReview();

        fireEvent.click(screen.getByRole('button', { name: /Add story/i }));
        fireEvent.change(screen.getByLabelText('New story'), { target: { value: 'New branch' } });
        fireEvent.click(screen.getByRole('button', { name: 'Create' }));

        expect(screen.getByDisplayValue('New branch')).toBeInTheDocument();
    });
});
