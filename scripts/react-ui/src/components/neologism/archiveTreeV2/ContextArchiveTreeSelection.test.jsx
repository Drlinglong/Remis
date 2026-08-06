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

describe('ContextArchiveTreeReview selection inspector', () => {
    it('shows the selected fragment summary and delivery metadata', () => {
        render(
            <MantineProvider>
                <ContextArchiveTreeReview treeData={treeFixture} />
            </MantineProvider>,
        );

        fireEvent.click(screen.getByTestId('context-tree-fragment-fragment-2'));

        expect(screen.getByTestId('context-tree-selected-fragment')).toHaveTextContent('Second beat');
        expect(screen.getByTestId('context-tree-selected-fragment')).toHaveTextContent('narrative');
        expect(screen.getByTestId('context-tree-fragment-fragment-2')).toHaveAttribute('aria-selected', 'true');
    });
});
