const CANVAS_SIZE = 512;

const getImageSource = (value) => value?.image?.src || value?.src || null;

const serializeImage = (value) => {
    if (!value) return null;
    const { image: _image, ...rest } = value;
    return { ...rest, src: getImageSource(value) };
};

export const createEmptyCoverCanvas = () => ({
    schema_version: 1,
    width: CANVAS_SIZE,
    height: CANVAS_SIZE,
    backgroundColor: '#ffffff',
    backgroundImage: null,
    elements: [],
});

export const serializeCoverCanvas = ({ backgroundColor, backgroundImage, elements }) => ({
    schema_version: 1,
    width: CANVAS_SIZE,
    height: CANVAS_SIZE,
    backgroundColor,
    backgroundImage: serializeImage(backgroundImage),
    elements: elements.map(serializeImage),
});

const loadImage = (src) => new Promise((resolve, reject) => {
    if (!src) {
        resolve(null);
        return;
    }
    const image = new window.Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('cover_image_restore_failed'));
    image.src = src;
});

const hydrateImage = async (value) => {
    if (!value) return null;
    const image = await loadImage(value.src);
    const { src: _src, ...rest } = value;
    return { ...rest, image };
};

export const hydrateCoverCanvas = async (canvas) => {
    const source = canvas || createEmptyCoverCanvas();
    const [backgroundImage, elements] = await Promise.all([
        hydrateImage(source.backgroundImage),
        Promise.all((source.elements || []).map(hydrateImage)),
    ]);
    return {
        backgroundColor: source.backgroundColor || '#ffffff',
        backgroundImage,
        elements,
    };
};

export const coverDraftStorageKey = ({ workspaceId, projectId }) => {
    const scope = workspaceId ? `workspace:${workspaceId}` : projectId ? `project:${projectId}` : 'unbound';
    return `remis:steam-workshop:cover-draft:${scope}`;
};

export const readCoverDraft = (storage, context) => {
    const raw = storage.getItem(coverDraftStorageKey(context));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed.canvas || null;
};

export const writeCoverDraft = (storage, context, canvas) => {
    storage.setItem(coverDraftStorageKey(context), JSON.stringify({
        canvas,
        saved_at: new Date().toISOString(),
    }));
};

export { CANVAS_SIZE };
