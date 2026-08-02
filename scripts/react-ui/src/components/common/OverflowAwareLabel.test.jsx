import { Button, MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { OverflowAwareLabel } from './OverflowAwareLabel';
import { expandPseudoLocale } from '../../test/pseudoLocalization';

const longRussianLabel = 'Использовать обложку проекта';
const projectCoverDescription = 'Use the linked project thumbnail as the editor background.';
const originalResizeObserver = globalThis.ResizeObserver;

const renderLabel = ({ disabled = false } = {}) => render(
    <MantineProvider>
        <OverflowAwareLabel label={longRussianLabel}>
            <Button disabled={disabled}>placeholder</Button>
        </OverflowAwareLabel>
    </MantineProvider>,
);

describe('OverflowAwareLabel', () => {
    afterEach(() => {
        globalThis.ResizeObserver = originalResizeObserver;
        window.ResizeObserver = originalResizeObserver;
        vi.restoreAllMocks();
    });

    it('keeps the entire label as the button accessible name while visually ellipsizing it', () => {
        const { container } = renderLabel();

        expect(screen.getByRole('button', { name: longRussianLabel })).toBeInTheDocument();
        expect(container.querySelector('.overflow-aware-label')).toHaveTextContent(longRussianLabel);
        expect(screen.getByRole('button', { name: longRussianLabel })).not.toHaveAttribute('data-overflowing');
    });

    it('enables the full-text hover and focus tooltip only after its label overflows', async () => {
        const observers = [];
        class TestResizeObserver {
            constructor(callback) {
                this.callback = callback;
                observers.push(this);
            }

            disconnect() {}

            observe(target) {
                if (!target.classList.contains('overflow-aware-label')) return;
                Object.defineProperties(target, {
                    clientWidth: { configurable: true, value: 100 },
                    scrollWidth: { configurable: true, value: 140 },
                });
                this.callback([{ target }]);
            }
        }
        globalThis.ResizeObserver = TestResizeObserver;
        window.ResizeObserver = TestResizeObserver;

        renderLabel();
        const button = screen.getByRole('button', { name: longRussianLabel });

        await waitFor(() => expect(observers).toHaveLength(1));
        await waitFor(() => expect(button).toHaveAttribute('data-overflowing', 'true'));
        fireEvent.focus(button);
        fireEvent.mouseEnter(button);

        expect(await screen.findByRole('tooltip')).toHaveTextContent(longRussianLabel);
    });

    it('keeps an existing functional description available without label overflow', async () => {
        render(
            <MantineProvider>
                <OverflowAwareLabel description={projectCoverDescription} label={longRussianLabel}>
                    <Button>placeholder</Button>
                </OverflowAwareLabel>
            </MantineProvider>,
        );

        fireEvent.mouseEnter(screen.getByRole('button', { name: longRussianLabel }));

        expect(await screen.findByRole('tooltip')).toHaveTextContent(projectCoverDescription);
    });

    it('provides a reusable forty-percent pseudo-locale expansion for constrained controls', () => {
        const source = 'Use project cover';
        const expanded = expandPseudoLocale(source);

        expect(Array.from(expanded)).toHaveLength(Math.ceil(Array.from(source).length * 1.4));
    });

    it('keeps the overflowing label available on hover when its button is disabled', async () => {
        class TestResizeObserver {
            constructor(callback) {
                this.callback = callback;
            }

            disconnect() {}

            observe(target) {
                if (!target.classList.contains('overflow-aware-label')) return;
                Object.defineProperties(target, {
                    clientWidth: { configurable: true, value: 100 },
                    scrollWidth: { configurable: true, value: 140 },
                });
                this.callback([{ target }]);
            }
        }
        globalThis.ResizeObserver = TestResizeObserver;
        window.ResizeObserver = TestResizeObserver;

        const { container } = renderLabel({ disabled: true });
        await waitFor(() => expect(screen.getByRole('button', { name: longRussianLabel }))
            .toHaveAttribute('data-overflowing', 'true'));

        fireEvent.mouseEnter(container.querySelector('.overflow-aware-control'));

        expect(await screen.findByRole('tooltip')).toHaveTextContent(longRussianLabel);
    });
});
