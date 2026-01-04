import React from 'react';
import { Paper, Text, Group, ThemeIcon, RingProgress } from '@mantine/core';
import { IconArrowUpRight, IconArrowDownRight } from '@tabler/icons-react';

const StatCard = ({ title, value, icon, color, progress, trend, className }) => {
    return (
        <Paper withBorder radius="md" p="xs" className={className} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'transparent' }}>
            <Group>
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

                <div>
                    <Text c="dimmed" size="xs" tt="uppercase" fw={700}>
                        {title}
                    </Text>
                    <Text fw={700} size="xl">
                        {value}
                    </Text>
                </div>
            </Group>

            {!!trend && (
                <Group gap={2}>
                    <Text c={trend > 0 ? 'teal' : 'red'} fz="sm" fw={500}>
                        {trend}%
                    </Text>
                    {trend > 0 ? (
                        <IconArrowUpRight size={16} color="var(--mantine-color-teal-6)" />
                    ) : (
                        <IconArrowDownRight size={16} color="var(--mantine-color-red-6)" />
                    )}
                </Group>
            )}
        </Paper>
    );
};

export default StatCard;
