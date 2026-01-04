import React from 'react';
import { Paper, Group, Title, Table, Tooltip, Text, Badge, Button, Select } from '@mantine/core';
import { IconClock, IconCheck, IconX, IconPlayerPlay, IconEdit, IconPlayerPause } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import styles from '../../pages/ProjectManagement.module.css';

const ProjectFileList = ({ projectDetails, handleProofread, onFileStatusChange }) => {
    const { t } = useTranslation();

    // Helper to get relative path
    const getRelativePath = (fullPath) => {
        if (!fullPath) return '';

        // Check source path
        if (projectDetails.source_path && fullPath.startsWith(projectDetails.source_path)) {
            let rel = fullPath.substring(projectDetails.source_path.length);
            if (rel.startsWith('/') || rel.startsWith('\\')) rel = rel.substring(1);
            return rel;
        }

        // Check translation dirs
        if (projectDetails.translation_dirs) {
            for (const dir of projectDetails.translation_dirs) {
                if (fullPath.startsWith(dir)) {
                    let rel = fullPath.substring(dir.length);
                    if (rel.startsWith('/') || rel.startsWith('\\')) rel = rel.substring(1);
                    return rel;
                }
            }
        }

        return fullPath; // Fallback
    };

    const statusOptions = [
        { value: 'todo', label: t('project_management.kanban.columns.todo'), color: 'gray', icon: IconClock },
        { value: 'in_progress', label: t('project_management.kanban.columns.in_progress'), color: 'blue', icon: IconPlayerPlay },
        { value: 'proofreading', label: t('project_management.kanban.columns.proofreading'), color: 'yellow', icon: IconEdit },
        { value: 'paused', label: t('project_management.kanban.columns.paused'), color: 'orange', icon: IconPlayerPause },
        { value: 'done', label: t('project_management.kanban.columns.done'), color: 'green', icon: IconCheck },
    ];

    const rows = projectDetails.files.map((file) => {
        const relativePath = getRelativePath(file.name);
        const currentOption = statusOptions.find(o => o.value === file.status) || statusOptions[0];

        return (
            <Table.Tr key={file.key}>
                <Table.Td style={{ maxWidth: '300px' }}>
                    <Tooltip label={relativePath} openDelay={500}>
                        <Text fw={500} truncate>{relativePath.split('/').pop().split('\\').pop()}</Text>
                    </Tooltip>
                </Table.Td>
                <Table.Td style={{ width: '100px' }}>
                    <Badge variant="dot" color={file.file_type === 'source' ? 'blue' : 'violet'}>
                        {file.file_type === 'source' ? t('project_management.file_type.source') : t('project_management.file_type.translation')}
                    </Badge>
                </Table.Td>
                <Table.Td style={{ width: '80px' }}>{file.lines}</Table.Td>
                <Table.Td style={{ width: '150px' }}>
                    <Select
                        size="xs"
                        variant="unstyled"
                        value={file.status}
                        data={statusOptions}
                        onChange={(val) => onFileStatusChange(file.key, val)}
                        allowDeselect={false}
                        leftSection={<currentOption.icon size={14} color={currentOption.color} />}
                        styles={{
                            input: {
                                fontWeight: 500,
                                color: `var(--mantine-color-${currentOption.color}-filled)`,
                                '&:hover': {
                                    backgroundColor: 'rgba(255,255,255,0.05)',
                                }
                            }
                        }}
                    />
                </Table.Td>
                <Table.Td style={{ width: '80px' }}>{file.progress}</Table.Td>
                <Table.Td style={{ width: '120px' }}>
                    <Group gap="xs">
                        {file.actions.map(action => (
                            <Tooltip key={action} label={t('project_management.tooltip_proofread')}>
                                <Button
                                    variant="subtle"
                                    size="xs"
                                    onClick={() => {
                                        if (action === 'Proofread') handleProofread(file);
                                    }}
                                >
                                    {t('proofreading.proofread')}
                                </Button>
                            </Tooltip>
                        ))}
                    </Group>
                </Table.Td>
            </Table.Tr>
        );
    });

    return (
        <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
            <div style={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: 0, overflowY: 'auto', overflowX: 'hidden' }}>
                <Paper withBorder p="md" radius="md" className={styles.glassCard}>
                    <Group justify="space-between" mb="md">
                        <Title order={4}>{t('project_management.file_list_title', { count: projectDetails.files.length })}</Title>
                    </Group>
                    <Table verticalSpacing="sm" className={styles.table} stickyHeader>
                        <Table.Thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--glass-bg)', zIndex: 1 }}>
                            <Table.Tr>
                                <Table.Th>{t('project_management.file_list.table.name')}</Table.Th>
                                <Table.Th style={{ width: '100px' }}>{t('project_management.file_list.table.type')}</Table.Th>
                                <Table.Th style={{ width: '80px' }}>{t('project_management.file_list.table.lines')}</Table.Th>
                                <Table.Th style={{ width: '150px' }}>{t('project_management.file_list.table.status')}</Table.Th>
                                <Table.Th style={{ width: '80px' }}>{t('project_management.file_list.table.progress')}</Table.Th>
                                <Table.Th style={{ width: '120px' }}>{t('project_management.file_list.table.actions')}</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>{rows}</Table.Tbody>
                    </Table>
                </Paper>
            </div>
        </div>
    );
};

export default ProjectFileList;
