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
});
