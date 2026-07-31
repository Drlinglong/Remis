import {
    Button,
    ColorInput,
    NumberInput,
    Paper,
    Select,
    Stack,
    TextInput,
    Title,
} from '@mantine/core';
import { IconUpload } from '@tabler/icons-react';
import { AVAILABLE_FONTS } from './coverEditorAssets';

export const CoverInspector = ({ editor, labels }) => {
    const selected = editor.selectedElement;
    return (
        <Paper withBorder p="md" data-remis-surface="surface">
            <Stack>
                <Title order={4}>{labels.inspectorTitle}</Title>
                <ColorInput
                    label={labels.backgroundColor}
                    value={editor.backgroundColor}
                    onChange={editor.setBackgroundColor}
                />
                <Button
                    variant="light"
                    leftSection={<IconUpload size={14} />}
                    onClick={() => editor.inputRefs.backgroundInputRef.current?.click()}
                >
                    {labels.uploadBackground}
                </Button>
                <input
                    ref={editor.inputRefs.backgroundInputRef}
                    type="file"
                    accept="image/*"
                    onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) editor.addFileImage(file, 'background');
                        event.target.value = '';
                    }}
                    style={{ display: 'none' }}
                />

                {selected && (
                    <Stack>
                        <Title order={5}>{labels.elementProperties}</Title>
                        {selected.type === 'text' && (
                            <>
                                <TextInput
                                    label={labels.textContent}
                                    value={selected.text}
                                    onChange={(event) => editor.updateElement(
                                        selected.id,
                                        { ...selected, text: event.target.value },
                                    )}
                                />
                                <NumberInput
                                    label={labels.fontSize}
                                    value={selected.fontSize}
                                    onChange={(value) => editor.updateElement(
                                        selected.id,
                                        { ...selected, fontSize: value },
                                    )}
                                />
                                <Select
                                    label={labels.fontFamily}
                                    value={selected.fontFamily}
                                    onChange={(value) => editor.updateElement(
                                        selected.id,
                                        { ...selected, fontFamily: value },
                                    )}
                                    data={AVAILABLE_FONTS}
                                />
                                <ColorInput
                                    label={labels.color}
                                    value={selected.fill}
                                    onChange={(value) => editor.updateElement(
                                        selected.id,
                                        { ...selected, fill: value },
                                    )}
                                />
                            </>
                        )}
                        <Button variant="subtle" color="red" onClick={editor.deleteSelected}>
                            {labels.deleteElement}
                        </Button>
                    </Stack>
                )}

                <Button
                    variant="light"
                    leftSection={<IconUpload size={14} />}
                    onClick={() => editor.inputRefs.emblemInputRef.current?.click()}
                >
                    {labels.uploadEmblem}
                </Button>
                <input
                    ref={editor.inputRefs.emblemInputRef}
                    type="file"
                    accept="image/*"
                    onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) editor.addFileImage(file, 'emblem');
                        event.target.value = '';
                    }}
                    style={{ display: 'none' }}
                />
            </Stack>
        </Paper>
    );
};
