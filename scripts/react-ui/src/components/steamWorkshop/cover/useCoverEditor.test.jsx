import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { useCoverEditor } from './useCoverEditor';

const originalFileReader = window.FileReader;
const originalImage = window.Image;

afterEach(() => {
    window.FileReader = originalFileReader;
    window.Image = originalImage;
});

describe('useCoverEditor image uploads', () => {
    it('uses intrinsic dimensions when the detached image has zero layout dimensions', async () => {
        const images = [];

        window.FileReader = class {
            readAsDataURL() {
                this.result = 'data:image/png;base64,cover';
                queueMicrotask(() => this.onload?.());
            }
        };
        window.Image = class {
            constructor() {
                this.width = 0;
                this.height = 0;
                this.naturalWidth = 1024;
                this.naturalHeight = 256;
                this.complete = false;
                images.push(this);
            }

            set src(value) {
                this._src = value;
                this.complete = true;
                queueMicrotask(() => this.onload?.());
            }

            get src() {
                return this._src;
            }
        };

        const { result } = renderHook(() => useCoverEditor({ defaultText: 'Cover' }));
        const file = new File(['cover'], 'cover.png', { type: 'image/png' });

        await act(async () => {
            await result.current.addFileImage(file, 'background');
        });

        expect(images).toHaveLength(1);
        expect(result.current.backgroundImage).toMatchObject({
            image: images[0],
            x: 0,
            y: 192,
            width: 512,
            height: 128,
        });
    });

    // Regression: ISSUE-005 — reset and clear canvas previously appeared identical.
    // Found by /qa on 2026-07-31
    // Report: .gstack/qa-reports/qa-report-127.0.0.1-2026-07-31.md
    it('opens newly added text for editing and resets only its element layers', async () => {
        const { result } = renderHook(() => useCoverEditor({ defaultText: 'Cover' }));

        act(() => {
            result.current.setBackgroundColor('#123456');
            result.current.addText();
        });

        expect(result.current.elements).toHaveLength(1);
        expect(result.current.selectedElement).toMatchObject({ type: 'text', text: 'Cover' });
        expect(result.current.editingTextId).toBe(result.current.selectedId);

        act(() => result.current.resetCanvas());

        expect(result.current.elements).toEqual([]);
        expect(result.current.backgroundColor).toBe('#123456');
        expect(result.current.selectedId).toBeNull();
        expect(result.current.editingTextId).toBeNull();
    });
});
