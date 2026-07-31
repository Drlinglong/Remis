import { useEffect, useRef } from 'react';
import { Image as KonvaImage, Layer, Rect, Stage, Text as KonvaText, Transformer } from 'react-konva';
import { IconUpload } from '@tabler/icons-react';
import { Paper, Text, useMantineTheme } from '@mantine/core';

const DraggableItem = ({ item, selected, onSelect, onChange, onEdit, accentColor }) => {
    const shapeRef = useRef(null);
    const transformerRef = useRef(null);

    useEffect(() => {
        if (!selected || !shapeRef.current) return;
        transformerRef.current.nodes([shapeRef.current]);
        transformerRef.current.getLayer().batchDraw();
    }, [selected]);

    const finishTransform = () => {
        const node = shapeRef.current;
        const scaleX = node.scaleX();
        const scaleY = node.scaleY();
        node.scaleX(1);
        node.scaleY(1);
        onChange({
            ...item,
            x: node.x(),
            y: node.y(),
            width: Math.max(5, node.width() * scaleX),
            height: item.type === 'text' ? 'auto' : Math.max(5, node.height() * scaleY),
            fontSize: item.type === 'text' ? Math.max(5, (item.fontSize || 20) * scaleY) : item.fontSize,
        });
    };
    const commonProps = {
        ...item,
        ref: shapeRef,
        draggable: true,
        onClick: onSelect,
        onTap: onSelect,
        onDblClick: item.type === 'text' ? onEdit : undefined,
        onDblTap: item.type === 'text' ? onEdit : undefined,
        onDragEnd: (event) => onChange({ ...item, x: event.target.x(), y: event.target.y() }),
        onTransformEnd: finishTransform,
    };

    return (
        <>
            {item.type === 'image' && <KonvaImage {...commonProps} />}
            {item.type === 'text' && <KonvaText {...commonProps} />}
            {selected && (
                <Transformer
                    ref={transformerRef}
                    borderStroke={accentColor}
                    borderStrokeWidth={2}
                    boundBoxFunc={(oldBox, newBox) => (
                        newBox.width < 5 || newBox.height < 5 ? oldBox : newBox
                    )}
                />
            )}
        </>
    );
};

const BackgroundImage = ({ value }) => {
    const imageRef = useRef(null);

    useEffect(() => {
        imageRef.current?.getLayer?.()?.batchDraw();
    }, [value.image]);

    return (
        <KonvaImage
            ref={imageRef}
            image={value.image}
            x={value.x}
            y={value.y}
            width={value.width}
            height={value.height}
        />
    );
};

export const CoverCanvas = ({
    canvasRef,
    editTextLabel,
    editor,
    onDrop,
    onDragOver,
    onRequestBackground,
    placeholder,
    dragHint,
}) => {
    const theme = useMantineTheme();
    const accentColor = theme.colors[theme.primaryColor][6];
    const empty = editor.backgroundColor === '#ffffff'
        && !editor.backgroundImage
        && editor.elements.length === 0;
    if (empty) {
        return (
            <Paper
                id="thumbnail-upload-area"
                className="cover-canvas-placeholder"
                withBorder
                p="md"
                onClick={onRequestBackground}
                onDrop={onDrop}
                onDragOver={onDragOver}
                style={{
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                    alignItems: 'center',
                    cursor: 'pointer',
                    background: 'var(--surface-bg, transparent)',
                    border: '2px dashed var(--mantine-color-dimmed)',
                    backdropFilter: 'blur(5px)',
                }}
            >
                <IconUpload size={48} color="var(--mantine-color-dimmed)" />
                <Text c="dimmed" mt="md">{placeholder}</Text>
                <Text c="dimmed" size="xs" mt="xs">{dragHint}</Text>
            </Paper>
        );
    }

    return (
        <div
            id="thumbnail-canvas"
            ref={canvasRef}
            onDrop={onDrop}
            onDragOver={onDragOver}
        >
            <Stage
                width={512}
                height={512}
                onMouseDown={(event) => event.target === event.target.getStage() && editor.setSelectedId(null)}
                onTouchStart={(event) => event.target === event.target.getStage() && editor.setSelectedId(null)}
            >
                <Layer>
                    <Rect width={512} height={512} fill={editor.backgroundColor} />
                    {editor.backgroundImage && <BackgroundImage value={editor.backgroundImage} />}
                    {editor.elements.map((item) => (
                        <DraggableItem
                            key={item.id}
                            item={item}
                            selected={item.id === editor.selectedId}
                            accentColor={accentColor}
                            onSelect={() => editor.setSelectedId(item.id === editor.selectedId ? null : item.id)}
                            onEdit={() => editor.beginTextEditing(item.id)}
                            onChange={(attributes) => editor.updateElement(item.id, attributes)}
                        />
                    ))}
                </Layer>
            </Stage>
            {editor.editingTextId && editor.selectedElement?.type === 'text' && (
                <input
                    aria-label={editTextLabel}
                    autoFocus
                    className="cover-canvas-text-editor"
                    style={{
                        fontFamily: editor.selectedElement.fontFamily,
                        fontSize: `clamp(12px, ${editor.selectedElement.fontSize / 5.12}cqw, ${editor.selectedElement.fontSize}px)`,
                        left: `${editor.selectedElement.x / 5.12}%`,
                        top: `${editor.selectedElement.y / 5.12}%`,
                    }}
                    type="text"
                    value={editor.selectedElement.text}
                    onBlur={editor.finishTextEditing}
                    onChange={(event) => editor.updateElement(editor.selectedElement.id, {
                        ...editor.selectedElement,
                        text: event.target.value,
                    })}
                    onKeyDown={(event) => {
                        if (event.key === 'Enter') editor.finishTextEditing();
                    }}
                />
            )}
        </div>
    );
};
