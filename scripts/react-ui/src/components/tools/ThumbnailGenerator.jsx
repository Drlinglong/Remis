import React, { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Stage, Layer, Rect, Image as KonvaImage, Transformer, Text as KonvaText } from 'react-konva';
import { Button, Grid, Paper, Title, ColorInput, TextInput, NumberInput, Select, Stack, Tooltip, Text } from '@mantine/core';
import { IconUpload } from '@tabler/icons-react';
import { v4 as uuidv4 } from 'uuid';
import html2canvas from 'html2canvas';

import './ThumbnailGenerator.css';

import flagEn from '../../assets/flags/us.svg';
import flagZhCN from '../../assets/flags/cn.svg';
import flagFr from '../../assets/flags/fr.svg';
import flagDe from '../../assets/flags/de.svg';
import flagEs from '../../assets/flags/es.svg';
import flagJa from '../../assets/flags/jp.svg';
import flagKo from '../../assets/flags/ko.svg';
import flagPl from '../../assets/flags/pl.svg';
import flagPtBR from '../../assets/flags/br.svg';
import flagRu from '../../assets/flags/ru.svg';
import flagTr from '../../assets/flags/tr.svg';

const flagSvgs = {
    'en': flagEn,
    'zh-CN': flagZhCN,
    'fr': flagFr,
    'de': flagDe,
    'es': flagEs,
    'ja': flagJa,
    'ko': flagKo,
    'pl': flagPl,
    'pt-BR': flagPtBR,
    'ru': flagRu,
    'tr': flagTr,
};
const AVAILABLE_FLAGS = [
    { "code": "en", "name": "English" },
    { "code": "zh-CN", "name": "简体中文" },
    { "code": "fr", "name": "Français" },
    { "code": "de", "name": "Deutsch" },
    { "code": "es", "name": "Español" },
    { "code": "ja", "name": "日本語" },
    { "code": "ko", "name": "한국어" },
    { "code": "pl", "name": "Polski" },
    { "code": "pt-BR", "name": "Português do Brasil" },
    { "code": "ru", "name": "Русский" },
    { "code": "tr", "name": "Türkçe" }
];

const AVAILABLE_FONTS = ['Arial', 'Verdana', 'Times New Roman', 'Courier New', 'Georgia', 'Comic Sans MS'];


const DraggableItem = ({ itemProps, isSelected, onSelect, onChange }) => {
    const shapeRef = useRef();
    const trRef = useRef();

    useEffect(() => {
        if (isSelected) {
            trRef.current.nodes([shapeRef.current]);
            trRef.current.getLayer().batchDraw();
        }
    }, [isSelected]);

    const itemStyle = isSelected ? {
        shadowColor: 'black',
        shadowBlur: 10,
        shadowOpacity: 0.6,
        shadowOffsetX: 5,
        shadowOffsetY: 5,
    } : {};

    const commonProps = {
        onClick: onSelect,
        onTap: onSelect,
        ref: shapeRef,
        draggable: true,
        onDragEnd: (e) => {
            onChange({ ...itemProps, x: e.target.x(), y: e.target.y() });
        },
        onTransformEnd: () => {
            const node = shapeRef.current;
            const scaleX = node.scaleX();
            const scaleY = node.scaleY();
            node.scaleX(1);
            node.scaleY(1);
            onChange({
                ...itemProps,
                x: node.x(),
                y: node.y(),
                width: Math.max(5, node.width() * scaleX),
                height: itemProps.type === 'text' ? 'auto' : Math.max(node.height() * scaleY),
                fontSize: itemProps.type === 'text' ? Math.max(5, (itemProps.fontSize || 20) * scaleY) : itemProps.fontSize,
            });
        },
    };

    return (
        <>
            {itemProps.type === 'image' && <KonvaImage {...commonProps} {...itemProps} {...itemStyle} />}
            {itemProps.type === 'text' && (
                <KonvaText
                    {...commonProps}
                    {...itemProps}
                    {...itemStyle}
                    // special handling for text resizing
                    onTransform={() => {
                        const node = shapeRef.current;
                        const scaleX = node.scaleX();
                        const scaleY = node.scaleY();
                        node.scaleX(1);
                        node.scaleY(1);
                        onChange({
                            ...itemProps,
                            width: Math.max(5, node.width() * scaleX),
                            height: 'auto',
                            fontSize: Math.max(5, (itemProps.fontSize || 20) * scaleY),
                        });
                    }}
                />
            )}
            {isSelected && (
                <Transformer
                    ref={trRef}
                    borderStroke="#007bff"
                    borderStrokeWidth={2}
                    boundBoxFunc={(oldBox, newBox) => {
                        if (newBox.width < 5 || newBox.height < 5) return oldBox;
                        return newBox;
                    }}
                />
            )}
        </>
    );
};

const ThumbnailGenerator = () => {
    const { t } = useTranslation();
    const canvasContainerRef = useRef(null);
    const modImageInputRef = useRef(null);
    const bgImageInputRef = useRef(null);
    const customEmblemInputRef = useRef(null);
    const [backgroundColor, setBackgroundColor] = useState('#ffffff');
    const [backgroundImage, setBackgroundImage] = useState(null);
    const [elements, setElements] = useState([]);
    const [selectedId, selectShape] = useState(null);

    const processAndAddEmblem = (file) => {
        const reader = new FileReader();
        reader.onload = () => {
            const img = new window.Image();
            img.src = reader.result;
            img.onload = () => {
                const maxWidth = 128;
                const maxHeight = 128;
                let { width, height } = img;
                if (width > height) {
                    if (width > maxWidth) {
                        height *= maxWidth / width;
                        width = maxWidth;
                    }
                } else if (height > maxHeight) {
                    width *= maxHeight / height;
                    height = maxHeight;
                }

                const newImage = {
                    type: 'image',
                    image: img,
                    x: 50,
                    y: 50,
                    width,
                    height,
                    id: uuidv4(),
                };
                addElement(newImage);
            };
        };
        reader.readAsDataURL(file);
    };

    const handleCustomEmblemUpload = (e) => {
        if (e.target.files && e.target.files[0]) {
            processAndAddEmblem(e.target.files[0]);
            e.target.value = null;
        }
    };

    const handleBackgroundImageUpload = (e) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            const reader = new FileReader();
            reader.onload = () => {
                const img = new window.Image();
                img.src = reader.result;
                img.onload = () => {
                    const canvasWidth = 512;
                    const canvasHeight = 512;
                    let { width, height } = img;

                    const aspectRatio = width / height;
                    const canvasAspectRatio = canvasWidth / canvasHeight;

                    let newWidth = canvasWidth;
                    let newHeight = canvasHeight;

                    if (aspectRatio > canvasAspectRatio) {
                        newHeight = canvasWidth / aspectRatio;
                    } else {
                        newWidth = canvasHeight * aspectRatio;
                    }

                    setBackgroundImage({
                        image: img,
                        x: (canvasWidth - newWidth) / 2,
                        y: (canvasHeight - newHeight) / 2,
                        width: newWidth,
                        height: newHeight,
                    });
                };
            };
            reader.readAsDataURL(file);
            e.target.value = null;
        }
    };

    const addElement = (newElement) => {
        setElements((prev) => [...prev, newElement]);
    };

    const processAndAddImage = (file, isModImage = false) => {
        const reader = new FileReader();
        reader.onload = () => {
            const img = new window.Image();
            img.src = reader.result;
            img.onload = () => {
                const maxWidth = isModImage ? 512 : 128;
                const maxHeight = isModImage ? 512 : 128;
                let { width, height } = img;
                if (width > height) {
                    if (width > maxWidth) {
                        height *= maxWidth / width;
                        width = maxWidth;
                    }
                } else if (height > maxHeight) {
                    width *= maxHeight / height;
                    height = maxHeight;
                }

                const newImage = {
                    type: 'image',
                    image: img,
                    x: isModImage ? (512 - width) / 2 : 50,
                    y: isModImage ? (512 - height) / 2 : 50,
                    width,
                    height,
                    id: uuidv4(),
                };
                if (isModImage) {
                    setElements(prev => [newImage, ...prev.filter(el => el.isModImage !== true)]);
                } else {
                    addElement(newImage);
                }
            };
        };
        reader.readAsDataURL(file);
    };

    const handleImageUpload = (e, isModImage = false) => {
        if (e.target.files && e.target.files[0]) {
            processAndAddImage(e.target.files[0], isModImage);
            e.target.value = null;
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            if (file.type.startsWith('image/')) {
                // Treat dropped images as Mod Images (Logos)
                processAndAddImage(file, true);
            }
        }
    };

    const handleDragOver = (e) => e.preventDefault();

    const handleAddFlag = (code) => {
        const img = new window.Image();
        img.src = flagSvgs[code];
        img.onload = () => {
            addElement({
                type: 'image',
                image: img,
                x: 60,
                y: 60,
                width: 100,
                height: 75,
                id: uuidv4(),
            });
        };
    };

    const handleAddText = () => {
        addElement({
            type: 'text',
            text: t('thumbnail_generator.default_text'),
            x: 70,
            y: 70,
            fontSize: 30,
            fontFamily: 'Arial',
            fill: '#000000',
            id: uuidv4(),
        });
    };

    const handleAddAllFlags = () => {
        const flagWidth = 80;
        const flagHeight = 60;
        const padding = 10;
        const canvasWidth = 512;
        const canvasHeight = 512;

        const positions = [
            { x: padding, y: padding },
            { x: padding, y: padding + (canvasHeight - padding * 2 - flagHeight) / 4 * 1 },
            { x: padding, y: padding + (canvasHeight - padding * 2 - flagHeight) / 4 * 2 },
            { x: padding, y: padding + (canvasHeight - padding * 2 - flagHeight) / 4 * 3 },
            { x: padding, y: canvasHeight - flagHeight - padding },
            { x: canvasWidth - flagWidth - padding, y: padding },
            { x: canvasWidth - flagWidth - padding, y: padding + (canvasHeight - padding * 2 - flagHeight) / 4 * 1 },
            { x: canvasWidth - flagWidth - padding, y: padding + (canvasHeight - padding * 2 - flagHeight) / 4 * 2 },
            { x: canvasWidth - flagWidth - padding, y: padding + (canvasHeight - padding * 2 - flagHeight) / 4 * 3 },
            { x: canvasWidth - flagWidth - padding, y: canvasHeight - flagHeight - padding },
            { x: (canvasWidth - flagWidth) / 2, y: canvasHeight - flagHeight - padding },
        ];

        const flagPromises = AVAILABLE_FLAGS.map(flag => {
            return new Promise((resolve) => {
                const img = new window.Image();
                img.src = flagSvgs[flag.code];
                img.onload = () => resolve({ img, code: flag.code });
            });
        });

        Promise.all(flagPromises).then(loadedFlags => {
            const newFlagElements = loadedFlags.map((flagData, index) => {
                if (flagData.code === 'tr') {
                    return { type: 'image', image: flagData.img, x: positions[10].x, y: positions[10].y, width: flagWidth, height: flagHeight, id: uuidv4() };
                }
                return { type: 'image', image: flagData.img, x: positions[index].x, y: positions[index].y, width: flagWidth, height: flagHeight, id: uuidv4() };
            }).filter((_, index) => index < positions.length);
            setElements(prev => [...prev, ...newFlagElements]);
        });
    };

    const handleResetCanvas = () => setElements([]);
    const handleDeleteCanvas = () => {
        setBackgroundImage(null);
        setBackgroundColor('#ffffff');
    };

    const checkDeselect = (e) => {
        if (e.target === e.target.getStage()) selectShape(null);
    };

    const updateElement = (id, newAttrs) => {
        setElements(elements.map(el => (el.id === id ? newAttrs : el)));
    };

    const handleDeleteElement = () => {
        if (selectedId) {
            setElements(elements.filter(el => el.id !== selectedId));
            selectShape(null);
        }
    };

    const handleExport = () => {
        const originallySelectedId = selectedId;
        selectShape(null);

        setTimeout(() => {
            if (canvasContainerRef.current) {
                html2canvas(canvasContainerRef.current, { backgroundColor: null, logging: false, useCORS: true })
                    .then(canvas => {
                        const link = document.createElement('a');
                        link.download = 'thumbnail.png';
                        link.href = canvas.toDataURL('image/png');
                        link.click();
                        selectShape(originallySelectedId);
                    });
            } else {
                selectShape(originallySelectedId);
            }
        }, 100);
    };

    const selectedElement = elements.find(el => el.id === selectedId);
    const isCanvasEmpty = !backgroundImage && elements.length === 0;

    return (
        <Grid>
            <Grid.Col span={{ base: 12, md: 3 }}>
                <Paper id="thumbnail-toolbox" withBorder p="md">
                    <Stack>
                        <Title order={4}>{t('thumbnail_generator.toolbox_title')}</Title>
                        <Button leftSection={<IconUpload size={14} />} onClick={() => modImageInputRef.current?.click()}>
                            {t('thumbnail_generator.upload_mod_image')}
                        </Button>
                        <input ref={modImageInputRef} type="file" accept="image/*" onChange={(e) => handleImageUpload(e, true)} style={{ display: 'none' }} />

                        <div>
                            <Title order={5}>{t('thumbnail_generator.add_flags')}</Title>
                            <div className="flag-list">
                                {AVAILABLE_FLAGS.map(({ code, name }) => (
                                    <Tooltip label={name} key={code}>
                                        <img src={flagSvgs[code]} alt={name} onClick={() => handleAddFlag(code)} className="flag-item" />
                                    </Tooltip>
                                ))}
                            </div>
                        </div>

                        <Button onClick={handleAddText}>{t('thumbnail_generator.add_text')}</Button>
                        <Button onClick={handleAddAllFlags}>{t('thumbnail_generator.add_all_flags')}</Button>
                        <Button color="red" onClick={handleResetCanvas}>{t('thumbnail_generator.reset_canvas')}</Button>
                        <Button color="red" onClick={handleDeleteCanvas}>{t('thumbnail_generator.delete_canvas')}</Button>
                    </Stack>
                </Paper>
            </Grid.Col>

            <Grid.Col span={{ base: 12, md: 6 }}>
                <Paper withBorder p="md" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    {isCanvasEmpty ? (
                        <Paper
                            id="thumbnail-upload-area"
                            withBorder
                            p="md"
                            onClick={() => bgImageInputRef.current?.click()}
                            style={{
                                width: '100%',
                                maxWidth: '512px',
                                aspectRatio: '1/1',
                                display: 'flex',
                                flexDirection: 'column',
                                justifyContent: 'center',
                                alignItems: 'center',
                                cursor: 'pointer',
                                background: 'var(--glass-bg, rgba(30, 30, 30, 0.3))',
                                border: '2px dashed var(--mantine-color-dimmed)',
                                backdropFilter: 'blur(5px)',
                                transition: 'all 0.2s ease'
                            }}
                            onDrop={handleDrop}
                            onDragOver={handleDragOver}
                        >
                            <IconUpload size={48} color="var(--mantine-color-dimmed)" />
                            <Text c="dimmed" mt="md">{t('thumbnail_generator.canvas_placeholder')}</Text>
                            <Text c="dimmed" size="xs" mt="xs">{t('thumbnail_generator.drag_hint')}</Text>
                        </Paper>
                    ) : (
                        <div
                            id="thumbnail-canvas"
                            ref={canvasContainerRef}
                            style={{ width: 512, height: 512 }}
                            onDrop={handleDrop}
                            onDragOver={handleDragOver}
                        >
                            <Stage width={512} height={512} onMouseDown={checkDeselect} onTouchStart={checkDeselect}>
                                <Layer>
                                    <Rect width={512} height={512} fill={backgroundColor} />
                                    {backgroundImage && <KonvaImage image={backgroundImage.image} x={backgroundImage.x} y={backgroundImage.y} width={backgroundImage.width} height={backgroundImage.height} />}
                                    {elements.map((item) => (
                                        <DraggableItem
                                            key={item.id}
                                            itemProps={item}
                                            isSelected={item.id === selectedId}
                                            onSelect={() => selectShape(item.id === selectedId ? null : item.id)}
                                            onChange={(newAttrs) => updateElement(item.id, newAttrs)}
                                        />
                                    ))}
                                </Layer>
                            </Stage>
                        </div>
                    )}
                    <Button onClick={handleExport} mt="md">
                        {t('thumbnail_generator.download_thumbnail')}
                    </Button>
                </Paper>
            </Grid.Col>

            <Grid.Col span={{ base: 12, md: 3 }}>
                <Paper withBorder p="md">
                    <Stack>
                        <Title order={4}>{t('thumbnail_generator.inspector_title')}</Title>

                        <ColorInput
                            label={t('thumbnail_generator.background_color')}
                            value={backgroundColor}
                            onChange={setBackgroundColor}
                        />
                        <Button leftSection={<IconUpload size={14} />} onClick={() => bgImageInputRef.current?.click()}>
                            {t('thumbnail_generator.upload_background_image')}
                        </Button>
                        <input ref={bgImageInputRef} type="file" accept="image/*" onChange={handleBackgroundImageUpload} style={{ display: 'none' }} />

                        {selectedElement && (
                            <Stack>
                                <Title order={5}>{t('thumbnail_generator.element_properties')}</Title>
                                {selectedElement.type === 'text' && (
                                    <>
                                        <TextInput
                                            label={t('thumbnail_generator.prop_text_content')}
                                            value={selectedElement.text}
                                            onChange={(e) => updateElement(selectedId, { ...selectedElement, text: e.target.value })}
                                        />
                                        <NumberInput
                                            label={t('thumbnail_generator.prop_font_size')}
                                            value={selectedElement.fontSize}
                                            onChange={(value) => updateElement(selectedId, { ...selectedElement, fontSize: value })}
                                        />
                                        <Select
                                            label={t('thumbnail_generator.prop_font_family')}
                                            value={selectedElement.fontFamily}
                                            onChange={(value) => updateElement(selectedId, { ...selectedElement, fontFamily: value })}
                                            data={AVAILABLE_FONTS.map(font => ({ value: font, label: font }))}
                                        />
                                        <ColorInput
                                            label={t('thumbnail_generator.prop_color')}
                                            value={selectedElement.fill}
                                            onChange={(value) => updateElement(selectedId, { ...selectedElement, fill: value })}
                                        />
                                    </>
                                )}
                                <Button color="red" onClick={handleDeleteElement} mt="md">{t('thumbnail_generator.delete_element')}</Button>
                            </Stack>
                        )}

                        <Button leftSection={<IconUpload size={14} />} mt="md" onClick={() => customEmblemInputRef.current?.click()}>
                            {t('thumbnail_generator.upload_custom_emblem')}
                        </Button>
                        <input ref={customEmblemInputRef} type="file" accept="image/*" onChange={handleCustomEmblemUpload} style={{ display: 'none' }} />
                    </Stack>
                </Paper>
            </Grid.Col>
        </Grid>
    );
};

export default ThumbnailGenerator;