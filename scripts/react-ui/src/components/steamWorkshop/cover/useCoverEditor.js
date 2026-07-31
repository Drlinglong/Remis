import { useCallback, useMemo, useRef, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { AVAILABLE_FLAGS, FLAG_SOURCES } from './coverEditorAssets';

const readImageFile = (file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => {
        const image = new window.Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error('cover_image_load_failed'));
        image.src = reader.result;
    };
    reader.readAsDataURL(file);
});

const loadImageSource = (src) => new Promise((resolve, reject) => {
    const image = new window.Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('cover_image_load_failed'));
    image.src = src;
});

const fitInside = (image, maxWidth, maxHeight) => {
    const ratio = Math.min(maxWidth / image.width, maxHeight / image.height, 1);
    return { width: image.width * ratio, height: image.height * ratio };
};

export const useCoverEditor = ({ defaultText }) => {
    const modImageInputRef = useRef(null);
    const backgroundInputRef = useRef(null);
    const emblemInputRef = useRef(null);
    const [backgroundColor, setBackgroundColor] = useState('#ffffff');
    const [backgroundImage, setBackgroundImage] = useState(null);
    const [elements, setElements] = useState([]);
    const [selectedId, setSelectedId] = useState(null);

    const addElement = useCallback((element) => {
        setElements((current) => [...current, element]);
    }, []);

    const addFileImage = useCallback(async (file, kind) => {
        const image = await readImageFile(file);
        if (kind === 'background') {
            const size = fitInside(image, 512, 512);
            setBackgroundImage({
                image,
                x: (512 - size.width) / 2,
                y: (512 - size.height) / 2,
                ...size,
            });
            return;
        }
        const isModImage = kind === 'mod';
        const size = fitInside(image, isModImage ? 512 : 128, isModImage ? 512 : 128);
        const element = {
            type: 'image',
            image,
            x: isModImage ? (512 - size.width) / 2 : 50,
            y: isModImage ? (512 - size.height) / 2 : 50,
            ...size,
            id: uuidv4(),
            isModImage,
        };
        if (isModImage) {
            setElements((current) => [element, ...current.filter((item) => !item.isModImage)]);
        } else {
            addElement(element);
        }
    }, [addElement]);

    const addFlag = useCallback(async (code, position = { x: 60, y: 60 }) => {
        const image = await loadImageSource(FLAG_SOURCES[code]);
        addElement({
            type: 'image',
            image,
            x: position.x,
            y: position.y,
            width: position.width || 100,
            height: position.height || 75,
            id: uuidv4(),
        });
    }, [addElement]);

    const addAllFlags = useCallback(async () => {
        const positions = AVAILABLE_FLAGS.map((_, index) => ({
            x: index < 5 ? 10 : index < 10 ? 422 : 216,
            y: index < 5 ? 10 + index * 108 : index < 10 ? 10 + (index - 5) * 108 : 442,
            width: 80,
            height: 60,
        }));
        const images = await Promise.all(AVAILABLE_FLAGS.map((flag) => loadImageSource(FLAG_SOURCES[flag.code])));
        setElements((current) => [
            ...current,
            ...images.map((image, index) => ({
                type: 'image',
                image,
                ...positions[index],
                id: uuidv4(),
            })),
        ]);
    }, []);

    const addText = useCallback(() => {
        addElement({
            type: 'text',
            text: defaultText,
            x: 70,
            y: 70,
            fontSize: 30,
            fontFamily: 'Arial',
            fill: '#000000',
            id: uuidv4(),
        });
    }, [addElement, defaultText]);

    const updateElement = useCallback((id, attributes) => {
        setElements((current) => current.map((item) => item.id === id ? attributes : item));
    }, []);

    const deleteSelected = useCallback(() => {
        setElements((current) => current.filter((item) => item.id !== selectedId));
        setSelectedId(null);
    }, [selectedId]);

    const replaceCanvas = useCallback((canvas) => {
        setBackgroundColor(canvas.backgroundColor);
        setBackgroundImage(canvas.backgroundImage);
        setElements(canvas.elements);
        setSelectedId(null);
    }, []);

    const canvasState = useMemo(() => ({
        backgroundColor,
        backgroundImage,
        elements,
    }), [backgroundColor, backgroundImage, elements]);

    return {
        canvasState,
        backgroundColor,
        setBackgroundColor,
        backgroundImage,
        setBackgroundImage,
        elements,
        setElements,
        selectedId,
        setSelectedId,
        selectedElement: elements.find((item) => item.id === selectedId),
        inputRefs: { modImageInputRef, backgroundInputRef, emblemInputRef },
        addFileImage,
        addFlag,
        addAllFlags,
        addText,
        updateElement,
        deleteSelected,
        replaceCanvas,
    };
};
