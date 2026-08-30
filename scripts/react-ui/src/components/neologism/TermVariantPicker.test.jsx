import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, expect, it, vi } from 'vitest';

import TermVariantPicker from './TermVariantPicker';

const candidate = {
    id: 'candidate-1',
    suggestion: '第一译法',
    reasoning: '第一份解释',
    suggestion_variants: [
        { variant_id: 'variant-1', suggestion: '第一译法', reasoning: '第一份解释' },
        { variant_id: 'variant-2', suggestion: '第二译法', reasoning: '第二份解释' },
    ],
};

describe('TermVariantPicker', () => {
    it('keeps every AI translation and explanation selectable as one pair', () => {
        const onSelect = vi.fn();
        render(
            <MantineProvider>
                <TermVariantPicker candidate={candidate} onSelect={onSelect} t={(key) => key} />
            </MantineProvider>,
        );

        expect(screen.getByText('第一份解释')).toBeInTheDocument();
        expect(screen.getByText('第二份解释')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'neologism_review.court.select_variant' }));
        expect(onSelect).toHaveBeenCalledWith(candidate.suggestion_variants[1]);
    });
});
