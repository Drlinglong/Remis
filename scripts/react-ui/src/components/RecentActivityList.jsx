import React from 'react';
import { Paper, Text, Group, Avatar, Stack, Badge, ActionIcon, ScrollArea, Skeleton } from '@mantine/core';
import { IconDotsVertical } from '@tabler/icons-react';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { useTranslation } from 'react-i18next';

dayjs.extend(relativeTime);

const RecentActivityList = ({ id, className, activities, loading }) => {
    const { t } = useTranslation();

    const statusMap = {
        active: t('project_management.status.active'),
        archived: t('project_management.status.archived'),
        deleted: t('project_management.status.deleted'),
    };

    const translateDescription = (activity) => {
        const description = activity.description || '';
        const metadata = activity.metadata || {};

        if (
            activity.type === 'path_registered' &&
            (description === 'history.path_registered_desc' || description === 'Auto-registered translation output path')
        ) {
            return t('recent_activity_desc_path_registered');
        }

        if (
            activity.type === 'translate' &&
            (description === 'history.incremental_translate_desc' || description.startsWith('Build incremental update ('))
        ) {
            return t('agent_workshop.history.incremental_translate_desc', metadata);
        }

        if (activity.type === 'file_update' && description.includes(' to ')) {
            return t('recent_activity_desc_status_updated', {
                status: t(
                    `project_management.kanban.columns.${description.split(' to ')[1]}`,
                    description.split(' to ')[1]
                ),
            });
        }

        if (description.includes('Status updated to:')) {
            return t('recent_activity_desc_status_updated', {
                status: statusMap[description.split(': ')[1]] || description.split(': ')[1],
            });
        }

        return t(`recent_activity_desc_${activity.type}`, description);
    };

    return (
        <Paper id={id} withBorder radius="md" p="md" className={className} style={{ background: 'transparent' }}>
            <Group justify="space-between" mb="md">
                <Text fw={700}>{t('homepage_recent_activity')}</Text>
                <ActionIcon variant="subtle" color="gray">
                    <IconDotsVertical size={16} />
                </ActionIcon>
            </Group>

            <ScrollArea h={300} offsetScrollbars>
                <Stack gap="md">
                    {loading ? (
                        Array(5)
                            .fill(0)
                            .map((_, i) => (
                                <Group key={i} wrap="nowrap">
                                    <Skeleton height={38} circle />
                                    <div style={{ flex: 1 }}>
                                        <Skeleton height={14} mb={6} width="80%" />
                                        <Skeleton height={10} width="40%" />
                                    </div>
                                </Group>
                            ))
                    ) : (activities || []).length > 0 ? (
                        activities.map((activity) => (
                            <Group key={activity.id} wrap="nowrap">
                                <Avatar color="blue" radius="xl">
                                    {(activity.title || 'SY').substring(0, 2).toUpperCase()}
                                </Avatar>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <Text size="sm" fw={500}>
                                        {activity.title}
                                    </Text>
                                    <Text c="dimmed" size="xs">
                                        {translateDescription(activity)} • {dayjs(activity.timestamp).fromNow()}
                                    </Text>
                                </div>
                                <Badge variant="light" size="xs">
                                    {t(`recent_activity_type_${activity.type}`, activity.type.replace('_', ' '))}
                                </Badge>
                            </Group>
                        ))
                    ) : (
                        <Text size="xs" c="dimmed" ta="center" py="xl">
                            {t('recent_activity_no_data')}
                        </Text>
                    )}
                </Stack>
            </ScrollArea>
        </Paper>
    );
};

export default RecentActivityList;
