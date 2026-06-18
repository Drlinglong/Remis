import React, { useCallback } from 'react';
import {
    Accordion,
    Badge,
    Box,
    Card,
    Group,
    SimpleGrid,
    Stack,
    Text,
} from '@mantine/core';
import { useTranslation } from 'react-i18next';

export const TelemetrySummary = ({ telemetry }) => {
    const { t } = useTranslation();

    const formatDuration = useCallback((ms) => {
        if (typeof ms !== 'number' || Number.isNaN(ms)) return '--';
        if (ms < 1000) return `${Math.round(ms)} ms`;
        return `${(ms / 1000).toFixed(ms >= 10000 ? 0 : 1)} s`;
    }, []);

    const formatDateTime = useCallback((value) => {
        if (!value) return '--';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleString();
    }, []);

    if (!telemetry) return null;

    const languageTelemetry = Array.isArray(telemetry.languages) ? telemetry.languages : [];
    const topLevelItems = [
        { label: t('incremental_translation.telemetry_snapshot'), value: formatDuration(telemetry.snapshot_ms) },
        { label: t('incremental_translation.telemetry_total'), value: formatDuration(telemetry.total_ms) },
    ];

    return (
        <Stack gap="xs" mt="md">
            <Text size="sm" fw={600}>{t('incremental_translation.telemetry_title')}</Text>
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
                {topLevelItems.map((item) => (
                    <Card key={item.label} withBorder p="sm" radius="md">
                        <Text size="xs" c="dimmed">{item.label}</Text>
                        <Text size="sm" fw={600}>{item.value}</Text>
                    </Card>
                ))}
            </SimpleGrid>
            {languageTelemetry.length > 0 && (
                <Accordion variant="separated" radius="md" chevronPosition="right">
                    {languageTelemetry.map((item) => (
                        <Accordion.Item key={item.target_lang} value={item.target_lang}>
                            <Accordion.Control>
                                <Group justify="space-between" wrap="nowrap">
                                    <Text size="sm" fw={600}>{item.target_lang}</Text>
                                    <Badge color="blue" variant="light">{formatDuration(item.total_ms)}</Badge>
                                </Group>
                            </Accordion.Control>
                            <Accordion.Panel>
                                {item.archive_baseline && (
                                    <Card withBorder p="sm" radius="md" mb="md">
                                        <Text size="xs" c="dimmed">{t('incremental_translation.archive_baseline_title')}</Text>
                                        <SimpleGrid cols={{ base: 1, sm: 2 }} mt="xs">
                                            <Box>
                                                <Text size="xs" c="dimmed">{t('incremental_translation.archive_version_label')}</Text>
                                                <Text size="sm" fw={600}>v{item.archive_baseline.version_id ?? '--'}</Text>
                                            </Box>
                                            <Box>
                                                <Text size="xs" c="dimmed">{t('incremental_translation.archive_entries_label')}</Text>
                                                <Text size="sm" fw={600}>{item.archive_baseline.translated_count ?? '--'}</Text>
                                            </Box>
                                            <Box>
                                                <Text size="xs" c="dimmed">{t('incremental_translation.archive_uploaded_label')}</Text>
                                                <Text size="sm">{formatDateTime(item.archive_baseline.last_translation_at)}</Text>
                                            </Box>
                                            <Box>
                                                <Text size="xs" c="dimmed">{t('incremental_translation.archive_snapshot_label')}</Text>
                                                <Text size="sm">{formatDateTime(item.archive_baseline.created_at)}</Text>
                                            </Box>
                                        </SimpleGrid>
                                    </Card>
                                )}
                                <SimpleGrid cols={{ base: 1, sm: 2 }}>
                                    {[
                                        ['incremental_translation.telemetry_archive_fetch', item.archive_fetch_ms],
                                        ['incremental_translation.telemetry_prepare', item.prepare_ms],
                                        ['incremental_translation.telemetry_translation', item.translation_ms],
                                        ['incremental_translation.telemetry_build', item.build_ms],
                                        ['incremental_translation.telemetry_workshop_export', item.workshop_export_ms],
                                        ['incremental_translation.telemetry_embedded_workshop', item.embedded_workshop_ms],
                                        ['incremental_translation.telemetry_archive_write', item.archive_write_ms],
                                    ]
                                        .filter(([, value]) => typeof value === 'number')
                                        .map(([labelKey, value]) => (
                                            <Card key={labelKey} withBorder p="sm" radius="md">
                                                <Text size="xs" c="dimmed">{t(labelKey)}</Text>
                                                <Text size="sm" fw={600}>{formatDuration(value)}</Text>
                                            </Card>
                                        ))}
                                </SimpleGrid>
                            </Accordion.Panel>
                        </Accordion.Item>
                    ))}
                </Accordion>
            )}
        </Stack>
    );
};

export default TelemetrySummary;
