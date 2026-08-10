import React from 'react';
import { Paper, Group, Title, Button, Textarea } from '@mantine/core';
import { IconPlus } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import styles from './ProjectDetailSurfaces.module.css';

const ProjectNoteList = ({ notes, setNotes, onSaveNote, onViewHistory }) => {
    const { t } = useTranslation();

    return (
        <Paper withBorder p="md" radius="md" className={styles.glassCard} mb="md">
            <Group justify="space-between" mb="xs">
                <Title order={4}>{t('project_management.notes')}</Title>
                <Group>
                    <Button variant="light" size="xs" onClick={onViewHistory}>{t('project_management.view_notes_history')}</Button>
                    <Button
                        id="new-task-btn"
                        variant="light"
                        size="xs"
                        leftSection={<IconPlus size={14} />}
                        onClick={onSaveNote}
                    >
                        {t('project_management.add_note')}
                    </Button>
                </Group>
            </Group>
            <Textarea
                value={notes}
                onChange={(event) => setNotes(event.currentTarget.value)}
                placeholder={t('project_management.notes_placeholder')}
                autosize
                minRows={2}
            />
        </Paper>
    );
};

export default ProjectNoteList;
