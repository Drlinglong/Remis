import { afterEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
    invoke: vi.fn(),
    isTauri: vi.fn(),
    save: vi.fn(),
}));

vi.mock('@tauri-apps/api/core', () => ({
    invoke: mocks.invoke,
    isTauri: mocks.isTauri,
}));
vi.mock('@tauri-apps/plugin-dialog', () => ({ save: mocks.save }));

import { saveThumbnail } from './ThumbnailGenerator';

const pngDataUrl = 'data:image/png;base64,AQID';

describe('ThumbnailGenerator download', () => {
    afterEach(() => {
        mocks.invoke.mockReset();
        mocks.isTauri.mockReset();
        mocks.save.mockReset();
        vi.restoreAllMocks();
    });

    // Regression: ISSUE-003 — the desktop download action never opened Save As.
    // Found by /qa on 2026-07-31
    // Report: .gstack/qa-reports/qa-report-127.0.0.1-2026-07-31.md
    it('opens the native Save As dialog and writes its selected PNG path in Tauri', async () => {
        mocks.isTauri.mockReturnValue(true);
        mocks.save.mockResolvedValue('C:/Users/test/thumbnail.png');

        await saveThumbnail(pngDataUrl);

        expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({
            defaultPath: 'thumbnail.png',
            filters: [{ name: 'PNG image', extensions: ['png'] }],
        }));
        expect(mocks.invoke).toHaveBeenCalledWith('save_thumbnail_png', {
            path: 'C:/Users/test/thumbnail.png',
            contents: [1, 2, 3],
        });
    });

    // Regression: ISSUE-003 — browser development still needs a real download fallback.
    // Found by /qa on 2026-07-31
    // Report: .gstack/qa-reports/qa-report-127.0.0.1-2026-07-31.md
    it('uses a browser download anchor outside Tauri', async () => {
        mocks.isTauri.mockReturnValue(false);
        const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
        const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:thumbnail');
        const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

        await saveThumbnail(pngDataUrl);

        expect(click).toHaveBeenCalledOnce();
        expect(createObjectURL).toHaveBeenCalledOnce();
        expect(revokeObjectURL).toHaveBeenCalledWith('blob:thumbnail');
        expect(mocks.save).not.toHaveBeenCalled();
    });
});
