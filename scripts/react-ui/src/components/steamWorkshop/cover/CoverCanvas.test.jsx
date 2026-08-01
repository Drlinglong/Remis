import { fireEvent, render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { imageProps, textProps } = vi.hoisted(() => ({ imageProps: [], textProps: [] }));

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
        Text: (props) => {
            textProps.push(props);
            return null;
        },
        Transformer: () => null,
    };
});

import { CoverCanvas } from './CoverCanvas';

describe('CoverCanvas background rendering', () => {
    beforeEach(() => {
        imageProps.length = 0;
        textProps.length = 0;
    });

    // Regression: ISSUE-006 — canvas text could be selected but not edited in place.
    // Found by /qa on 2026-07-31
    // Report: .gstack/qa-reports/qa-report-127.0.0.1-2026-07-31.md
    it('provides an inline editor for selected text and supports double-click editing', () => {
        const text = {
            id: 'text-1',
            type: 'text',
            text: '可编辑文本',
            x: 70,
            y: 70,
            fontSize: 30,
            fontFamily: 'Arial',
            fill: '#000000',
        };
        const editor = {
            backgroundColor: '#123456',
            backgroundImage: null,
            beginTextEditing: vi.fn(),
            editingTextId: text.id,
            elements: [text],
            finishTextEditing: vi.fn(),
            selectedElement: text,
            selectedId: text.id,
            setSelectedId: vi.fn(),
            updateElement: vi.fn(),
        };

        render(
            <MantineProvider>
                <CoverCanvas
                    canvasRef={{ current: null }}
                    editTextLabel="Text content"
                    editor={editor}
                    onDrop={vi.fn()}
                    onDragOver={vi.fn()}
                    onRequestBackground={vi.fn()}
                    placeholder="Upload"
                    dragHint="Drop an image"
                />
            </MantineProvider>,
        );

        textProps[0].onDblClick();
        expect(editor.beginTextEditing).toHaveBeenCalledWith(text.id);

        fireEvent.change(screen.getByRole('textbox', { name: 'Text content' }), {
            target: { value: '已修改文本' },
        });
        expect(editor.updateElement).toHaveBeenCalledWith(text.id, {
            ...text,
            text: '已修改文本',
        });
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
