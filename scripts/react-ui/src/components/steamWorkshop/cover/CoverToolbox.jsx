import { Button, Paper, Stack, Title, Tooltip } from '@mantine/core';
import { IconUpload } from '@tabler/icons-react';
import { AVAILABLE_FLAGS, FLAG_SOURCES } from './coverEditorAssets';

export const CoverToolbox = ({ editor, labels }) => (
    <Paper id="thumbnail-toolbox" withBorder p="md" data-remis-surface="surface">
        <Stack>
            <Title order={4}>{labels.toolboxTitle}</Title>
            <Button
                variant="light"
                leftSection={<IconUpload size={14} />}
                onClick={() => editor.inputRefs.modImageInputRef.current?.click()}
            >
                {labels.uploadModImage}
            </Button>
            <input
                ref={editor.inputRefs.modImageInputRef}
                type="file"
                accept="image/*"
                onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) editor.addFileImage(file, 'mod');
                    event.target.value = '';
                }}
                style={{ display: 'none' }}
            />

            <div>
                <Title order={5}>{labels.addFlags}</Title>
                <div className="flag-list">
                    {AVAILABLE_FLAGS.map(({ code, name }) => (
                        <Tooltip label={name} key={code}>
                            <button
                                type="button"
                                className="flag-button"
                                aria-label={name}
                                onClick={() => editor.addFlag(code)}
                            >
                                <img src={FLAG_SOURCES[code]} alt="" className="flag-item" />
                            </button>
                        </Tooltip>
                    ))}
                </div>
            </div>

            <Button variant="light" onClick={editor.addText}>{labels.addText}</Button>
            <Button variant="light" onClick={editor.addAllFlags}>{labels.addAllFlags}</Button>
            <Button
                variant="subtle"
                color="red"
                onClick={() => {
                    editor.setElements([]);
                    editor.setSelectedId(null);
                }}
            >
                {labels.resetCanvas}
            </Button>
            <Button
                variant="subtle"
                color="red"
                onClick={() => {
                    editor.setBackgroundImage(null);
                    editor.setBackgroundColor('#ffffff');
                }}
            >
                {labels.deleteCanvas}
            </Button>
        </Stack>
    </Paper>
);
