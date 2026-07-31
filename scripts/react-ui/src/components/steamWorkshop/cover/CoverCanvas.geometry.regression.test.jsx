import { render } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { stageProps } = vi.hoisted(() => ({ stageProps: [] }));

vi.mock('react-konva', async () => {
    const { Fragment, createElement } = await vi.importActual('react');
    return {
        Image: () => null,
        Layer: ({ children }) => createElement(Fragment, null, children),
        Rect: () => null,
        Stage: (props) => {
            stageProps.push(props);
            return createElement('div', null, props.children);
        },
        Text: () => null,
        Transformer: () => null,
    };
});

import { CoverCanvas } from './CoverCanvas';
import { getCoverStageScale } from './coverCanvasGeometry';

const editor = {
    backgroundColor: '#123456',
    backgroundImage: null,
    elements: [{
        id: 'text-1',
        type: 'text',
        text: 'Narrow text target',
        x: 400,
        y: 70,
        fontSize: 30,
        fontFamily: 'Arial',
        fill: '#000000',
    }],
    selectedId: null,
    setSelectedId: vi.fn(),
    updateElement: vi.fn(),
};

describe('CoverCanvas responsive hit geometry', () => {
    const originalResizeObserver = globalThis.ResizeObserver;

    beforeEach(() => {
        stageProps.length = 0;
        globalThis.ResizeObserver = class {
            constructor(callback) {
                this.callback = callback;
            }
            observe() {
                this.callback([{ contentRect: { width: 256 } }]);
            }
            disconnect() {}
        };
    });

    afterEach(() => {
        globalThis.ResizeObserver = originalResizeObserver;
    });

    // Regression: ISSUE-007 — CSS resizing caused Konva pointer positions to
    // differ from the displayed text position, so text selection/drags missed.
    it('scales the Stage container instead of resizing its 512px coordinate space', () => {
        expect(getCoverStageScale(256)).toBe(0.5);
        expect(getCoverStageScale(700)).toBe(1);

        render(
            <MantineProvider>
                <CoverCanvas
                    canvasRef={{ current: null }}
                    editor={editor}
                    onDrop={vi.fn()}
                    onDragOver={vi.fn()}
                    onRequestBackground={vi.fn()}
                    placeholder="Upload"
                    dragHint="Drop an image"
                />
            </MantineProvider>,
        );

        expect(stageProps.at(-1)).toMatchObject({
            width: 512,
            height: 512,
            style: { transform: 'scale(0.5)', transformOrigin: 'top left' },
        });
    });
});
