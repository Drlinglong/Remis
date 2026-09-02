import React from 'react';
import { DndContext } from '@dnd-kit/core';
import { MantineProvider } from '@mantine/core';
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import PublishedContextGroupColumn from './PublishedContextGroupColumn';
import styles from './PublishedContextWorkbench.module.css';

const t = (_key, options) => options.defaultValue;
const fragment = (id, unitCount) => ({
    id,
    label: `Fragment ${id}`,
    summary: `Summary ${id}`,
    unitIds: Array.from({ length: unitCount }, (_, index) => `${id}-unit-${index}`),
});

const renderColumn = (fragments) => render(
    <MantineProvider>
        <DndContext>
            <PublishedContextGroupColumn
                group={{ id: 'chain-1', label: 'Event chain', summary: 'Chain summary' }}
                fragments={fragments}
                selectedFragmentId={null}
                focused={false}
                onSelect={vi.fn()}
                onSelectGroup={vi.fn()}
                totalFragmentCount={fragments.length}
                totalUnitCount={new Set(fragments.flatMap((item) => item.unitIds)).size}
                isOverview
                t={t}
            />
        </DndContext>
    </MantineProvider>,
);

describe('PublishedContextGroupColumn overview composition', () => {
    it('promotes a single fragment into the event-chain card', () => {
        renderColumn([fragment('one', 7)]);

        expect(screen.getByText('Chain summary')).toBeInTheDocument();
        expect(within(screen.getByTestId('published-context-group-header-chain-1'))
            .getByText('7')).toBeInTheDocument();
        expect(screen.getByTestId('published-context-fragments-chain-1'))
            .toHaveClass(styles.overviewSingleFragmentList);
    });

    it('keeps nested fragment cards when the chain contains several fragments', () => {
        renderColumn([fragment('one', 2), fragment('two', 3)]);

        expect(within(screen.getByTestId('published-context-group-header-chain-1'))
            .getByText('2')).toBeInTheDocument();
        expect(screen.getByTestId('published-context-fragment-one')).toBeInTheDocument();
        expect(screen.getByTestId('published-context-fragment-two')).toBeInTheDocument();
        expect(screen.getByTestId('published-context-fragments-chain-1'))
            .not.toHaveClass(styles.overviewSingleFragmentList);
    });
});
