import React from 'react';
import { Paper, Text, Group, ThemeIcon, RingProgress } from '@mantine/core';
import { IconArrowUpRight, IconArrowDownRight } from '@tabler/icons-react';

const StatCard = ({ title, value, icon, color, progress, trend, className }) => {
    return (
        <Paper
            withBorder
            radius="md"
            p="xs"
            className={className}
            data-remis-surface="surface"
            data-remis-stat-card
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', minWidth: 0 }}
        >
            <Group wrap="nowrap" style={{ minWidth: 0 }}>
                <RingProgress
                    size={80}
                    roundCaps
                    thickness={8}
                    sections={[{ value: progress, color: color }]}
                    label={
                        <ThemeIcon color={color} variant="light" radius="xl" size="lg" style={{ margin: 'auto', display: 'flex' }}>
                            {icon}
                        </ThemeIcon>
                    }
                />

                <div style={{ minWidth: 0 }}>
                    <Text c="dimmed" size="xs" tt="uppercase" fw={700} lineClamp={2} style={{ overflowWrap: 'anywhere' }}>
                        {title}
                    </Text>
                    <Text fw={700} size="xl" style={{ overflowWrap: 'anywhere' }}>
                        {value}
                    </Text>
                </div>
            </Group>

            {!!trend && (
                <Group gap={2}>
                    <Text fz="sm" fw={500} style={{ color: trend > 0 ? 'var(--status-success)' : 'var(--status-error)' }}>
                        {trend}%
                    </Text>
                    {trend > 0 ? (
                        <IconArrowUpRight size={16} color="var(--status-success)" />
                    ) : (
                        <IconArrowDownRight size={16} color="var(--status-error)" />
                    )}
                </Group>
            )}
        </Paper>
    );
};

export default StatCard;
