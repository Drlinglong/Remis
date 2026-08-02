import React from 'react';
import { Badge, Box, Button, Group, Paper, Select, Text, ThemeIcon } from '@mantine/core';
import { IconBook2, IconExternalLink } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import styles from './ProjectGlossaryToolbar.module.css';

const asProjectOption = (project) => ({
    value: project.value || project.project_id,
    label: project.label || project.name || project.project_id,
});

const ProjectGlossaryToolbar = ({
    projects,
    selectedProject,
    onSelectedProjectChange,
    projectGlossary,
    onOpenGlossary,
    contextBadge,
}) => {
    const { t } = useTranslation();
    const glossaryReady = Boolean(projectGlossary?.glossary_id && onOpenGlossary);

    return (
        <Paper
            p="sm"
            radius="md"
            data-testid="neologism-project-toolbar"
            data-remis-surface="surface"
            className={styles.toolbar}
        >
            <Group justify="space-between" gap="sm" wrap="wrap">
                <Group gap="xs" style={{ flex: '1 1 420px', minWidth: 0 }}>
                    <Text size="xs" c="dimmed" tt="uppercase" fw={700} ls={1}>
                        {t('neologism_review.court.current_project')}
                    </Text>
                    <Select
                        aria-label={t('neologism_review.court.current_project')}
                        data={(projects || []).map(asProjectOption)}
                        value={selectedProject}
                        onChange={onSelectedProjectChange}
                        placeholder={t('neologism_review.court.select_project')}
                        size="sm"
                        searchable
                        classNames={{ input: styles.field }}
                        style={{ flex: '1 1 220px', maxWidth: 360 }}
                    />
                    {contextBadge && (
                        <Badge size="md" variant="light" color="blue">
                            {contextBadge}
                        </Badge>
                    )}
                </Group>
                <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
                    <ThemeIcon color="teal" variant="light" size="md">
                        <IconBook2 size={16} />
                    </ThemeIcon>
                    <Box style={{ minWidth: 0, maxWidth: 220 }}>
                        <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
                            {t('neologism_review.court.project_glossary')}
                        </Text>
                        <Text className={styles.glossaryName} size="sm" fw={700} truncate>
                            {projectGlossary?.name || t('neologism_review.court.project_glossary_pending')}
                        </Text>
                    </Box>
                    <Button
                        variant="outline"
                        size="compact-sm"
                        data-remis-action="secondary"
                        className={styles.secondaryAction}
                        leftSection={<IconExternalLink size={14} />}
                        onClick={onOpenGlossary}
                        disabled={!glossaryReady}
                    >
                        {t('neologism_review.court.inspect_project_glossary')}
                    </Button>
                </Group>
            </Group>
        </Paper>
    );
};

export default ProjectGlossaryToolbar;
