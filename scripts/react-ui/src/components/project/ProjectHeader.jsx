import React from 'react';
import { Paper, Group, Title, Button, Tooltip, Grid, Card, Text } from '@mantine/core';
import { IconArchive, IconRestore, IconTrash, IconSettings, IconPlayerPlay } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import styles from '../../pages/ProjectManagement.module.css';

const ProjectHeader = ({ projectDetails, handleStatusChange, onDeleteForever, onManageProject }) => {
    const { t } = useTranslation();
    const navigate = useNavigate();

    return (
        <Paper withBorder p="md" radius="md" className={styles.glassCard} mb="md">
            <Group justify="space-between" mb="md">
                <Title order={4}>{t('project_management.overview_title')}</Title>
                <Group>
                    {projectDetails.status === 'active' && (
                        <>
                            <Tooltip label={t('project_management.delete_project')}>
                                <Button
                                    variant="light"
                                    color="red"
                                    size="xs"
                                    leftSection={<IconTrash size={16} />}
                                    onClick={onDeleteForever}
                                >
                                    {t('project_management.delete_project')}
                                </Button>
                            </Tooltip>
                            <Tooltip label={t('project_management.tooltip_archive')}>
                                <Button
                                    variant="light"
                                    color="orange"
                                    size="xs"
                                    leftSection={<IconArchive size={16} />}
                                    onClick={() => handleStatusChange('archived')}
                                >
                                    {t('project_management.archive_project')}
                                </Button>
                            </Tooltip>
                            <Tooltip label={t('project_management.manage_project')}>
                                <Button
                                    variant="light"
                                    color="blue"
                                    size="xs"
                                    leftSection={<IconSettings size={16} />}
                                    onClick={onManageProject}
                                >
                                    {t('project_management.manage_project')}
                                </Button>
                            </Tooltip>
                        </>
                    )}
                    {projectDetails.status === 'archived' && (
                        <>
                            <Tooltip label={t('project_management.restore_project')}>
                                <Button variant="light" color="blue" size="xs" leftSection={<IconRestore size={16} />} onClick={() => handleStatusChange('active')}>
                                    {t('project_management.restore_project')}
                                </Button>
                            </Tooltip>
                            <Tooltip label={t('project_management.delete_project')}>
                                <Button variant="light" color="red" size="xs" leftSection={<IconTrash size={16} />} onClick={() => handleStatusChange('deleted')}>
                                    {t('project_management.delete_project')}
                                </Button>
                            </Tooltip>
                        </>
                    )}
                    {projectDetails.status === 'deleted' && (
                        <>
                            <Tooltip label={t('project_management.restore_project')}>
                                <Button variant="light" color="blue" size="xs" leftSection={<IconRestore size={16} />} onClick={() => handleStatusChange('active')}>
                                    {t('project_management.restore_project')}
                                </Button>
                            </Tooltip>
                            <Tooltip label={t('project_management.delete_forever')}>
                                <Button variant="filled" color="red" size="xs" leftSection={<IconTrash size={16} />} onClick={onDeleteForever}>
                                    {t('project_management.delete_forever')}
                                </Button>
                            </Tooltip>
                        </>
                    )}
                </Group>
            </Group>
            <Grid align="stretch">
                <Grid.Col span={8}>
                    <Grid id="project-stats-grid" gutter="xs">
                        <Grid.Col span={3}><Card withBorder className={styles.statCard} h="100%"><Text size="xs" c="dimmed">{t('project_management.overview.total_files')}</Text><Title order={3}>{projectDetails.overview.totalFiles}</Title></Card></Grid.Col>
                        <Grid.Col span={3}><Card withBorder className={styles.statCard} h="100%"><Text size="xs" c="dimmed">{t('project_management.overview.total_lines')}</Text><Title order={3}>{projectDetails.overview.totalLines}</Title></Card></Grid.Col>
                        <Grid.Col span={3}><Card withBorder className={styles.statCard} h="100%"><Text size="xs" c="dimmed">{t('project_management.overview.translated')}</Text><Title order={3} c="green">{projectDetails.overview.translated}%</Title></Card></Grid.Col>
                        <Grid.Col span={3}><Card withBorder className={styles.statCard} h="100%"><Text size="xs" c="dimmed">{t('project_management.overview.to_be_proofread')}</Text><Title order={3} c="yellow">{projectDetails.overview.toBeProofread}%</Title></Card></Grid.Col>
                    </Grid>
                </Grid.Col>
                <Grid.Col span={4}>
                    <Tooltip label={t('project_management.tooltip_start_translation')}>
                        <Button
                            id="start-translation-btn"
                            fullWidth
                            h="100%"
                            size="xl"
                            variant="gradient"
                            className={styles.startTranslationButton}
                            leftSection={<IconPlayerPlay size={32} className={styles.startBtnIcon} />}
                            onClick={() => navigate(`/translation?projectId=${projectDetails.project_id}`)}
                            styles={{
                                inner: {
                                    flexDirection: 'column',
                                    gap: '12px'
                                },
                                label: {
                                    className: styles.startBtnLabel
                                }
                            }}
                        >
                            <Text className={styles.startBtnLabel}>
                                {t('button_start_translation', '开始翻译')}
                            </Text>
                        </Button>
                    </Tooltip>
                </Grid.Col>
            </Grid>
        </Paper>
    );
};

export default ProjectHeader;
