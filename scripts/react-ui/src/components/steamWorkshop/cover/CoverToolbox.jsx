import { Button, Paper, Stack, Text, Title, Tooltip } from '@mantine/core';
import { IconUpload } from '@tabler/icons-react';
import { AVAILABLE_FLAGS, FLAG_SOURCES } from './coverEditorAssets';

export const CoverToolbox = ({
    canLoadProjectThumbnail,
    editor,
    labels,
    onLoadProjectThumbnail,
    projectThumbnailError,
}) => (
    <Paper id="thumbnail-toolbox" withBorder p="md" data-remis-surface="paper">
        <Stack>
            <Tooltip label={labels.useProjectThumbnailTooltip} multiline w={230} withArrow>
                <span>
                    <Button
                        variant="light"
                        leftSection={<IconUpload size={14} />}
                        disabled={!canLoadProjectThumbnail}
                        onClick={onLoadProjectThumbnail}
                    >
                        {labels.useProjectThumbnail}
                    </Button>
                </span>
            </Tooltip>
            {projectThumbnailError && <Text c="red" role="alert" size="xs">{projectThumbnailError}</Text>}

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
                onClick={editor.resetCanvas}
            >
                {labels.resetCanvas}
            </Button>
            <Button
                variant="subtle"
                color="red"
                onClick={editor.clearCanvas}
            >
                {labels.deleteCanvas}
            </Button>
        </Stack>
    </Paper>
);
