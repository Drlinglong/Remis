import { render } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { imageProps } = vi.hoisted(() => ({ imageProps: [] }));

vi.mock('react-konva', async () => {
    const { Fragment, createElement } = await vi.importActual('react');
    return {
        Image: (props) => {
            imageProps.push(props);
            return null;
        },
        Layer: ({ children }) => createElement(Fragment, null, children),
        Rect: () => null,
        Stage: ({ children }) => createElement(Fragment, null, children),
        Text: () => null,
        Transformer: () => null,
    };
});

import { CoverCanvas } from './CoverCanvas';

describe('CoverCanvas background rendering', () => {
    beforeEach(() => {
        imageProps.length = 0;
    });

    it('passes the loaded background image and fitted geometry to KonvaImage', () => {
        const image = { src: 'data:image/png;base64,background' };
        const editor = {
            backgroundColor: '#ffffff',
            backgroundImage: { image, x: 0, y: 64, width: 512, height: 384 },
            elements: [],
            selectedId: null,
            setSelectedId: vi.fn(),
            updateElement: vi.fn(),
        };

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

        expect(imageProps).toHaveLength(1);
        expect(imageProps[0]).toMatchObject({
            image,
            x: 0,
            y: 64,
            width: 512,
            height: 384,
        });
        expect(imageProps[0]).not.toHaveProperty('src');
    });
});
