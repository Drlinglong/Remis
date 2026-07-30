import React from 'react';
import { ActionIcon, Group, Tooltip } from '@mantine/core';
import { IconEdit, IconExternalLink } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

const GlossaryRowActions = ({ glossary, onOpen, onEdit, className }) => {
    const { t } = useTranslation();
    const openLabel = t('glossary_overview_open', 'Open glossary');
    const editLabel = t('glossary_edit_metadata_action', 'Edit information');

    return (
        <Group className={className} gap="xs" wrap="nowrap">
            <Tooltip label={openLabel} position="top" withArrow>
                <ActionIcon
                    size="lg"
                    variant="subtle"
                    aria-label={openLabel}
                    onClick={() => onOpen(glossary)}
                >
                    <IconExternalLink size={18} aria-hidden="true" />
                </ActionIcon>
            </Tooltip>
            <Tooltip label={editLabel} position="top" withArrow>
                <ActionIcon
                    size="lg"
                    variant="subtle"
                    aria-label={editLabel}
                    onClick={() => onEdit(glossary)}
                >
                    <IconEdit size={18} aria-hidden="true" />
                </ActionIcon>
            </Tooltip>
        </Group>
    );
};

export default GlossaryRowActions;
