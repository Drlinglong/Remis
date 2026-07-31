export const COVER_CANVAS_SIZE = 512;

// Keep Konva's 512×512 coordinate system intact while the DOM preview shrinks.
// CSS resizing the canvas bitmap alone makes pointer coordinates diverge from
// Konva coordinates, which is most noticeable on narrow text hit targets.
export const getCoverStageScale = (displayWidth) => {
    if (!Number.isFinite(displayWidth) || displayWidth <= 0) return 1;
    return Math.min(1, displayWidth / COVER_CANVAS_SIZE);
};
