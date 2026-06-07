import React, { useCallback } from 'react';
import { SimpleGrid, Select, Group, Text, Tooltip, ThemeIcon } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

/**
 * PerformanceControlPanel is a reusable configuration panel for tuning API request parameters:
 * - Batch Size (Chunk Size)
 * - Concurrency Limit
 * - RPM Limit (Requests Per Minute)
 */
export const PerformanceControlPanel = ({
    batchSize,
    onChangeBatchSize,
    concurrency,
    onChangeConcurrency,
    rpm,
    onChangeRpm,
    showBatchSize = true,
    showConcurrency = true,
    showRpm = true,
    batchSizeOpts = null,
    concurrencyOpts = null,
    rpmOpts = null,
}) => {
    const { t } = useTranslation();

    // Default configurations
    const defaultBatchSizeOptions = [
        { value: '', label: t('translation_page.translation_limit_auto', { defaultValue: 'Auto (Recommended)' }) },
        ...['5', '10', '20', '40', '60'].map((value) => ({ value, label: value })),
    ];
    const defaultConcurrencyOptions = ['1', '2', '5', '10', '20', '50'].map((value) => ({ value, label: value }));
    const defaultRpmOptions = ['5', '10', '20', '30', '50', '100'].map((value) => ({ value, label: value }));

    const renderInfoLabel = useCallback((label, tooltip) => (
        <Group gap={4} wrap="nowrap">
            <Text size="sm" fw={500}>{label}</Text>
            {tooltip && (
                <Tooltip label={tooltip} multiline w={320} withArrow>
                    <ThemeIcon variant="subtle" color="gray" size="sm" style={{ cursor: 'help' }}>
                        <IconAlertCircle size={14} />
                    </ThemeIcon>
                </Tooltip>
            )}
        </Group>
    ), []);

    const activeCount = [showBatchSize, showConcurrency, showRpm].filter(Boolean).length;
    const cols = activeCount === 3 ? { base: 1, sm: 3 } : activeCount === 2 ? { base: 1, sm: 2 } : 1;

    return (
        <SimpleGrid cols={cols} spacing="md">
            {showBatchSize && (
                <Select
                    label={renderInfoLabel(
                        t('translation_page.translation_limit'),
                        t('translation_page.translation_limit_tooltip', { defaultValue: '限制单次请求发送的条目数量（Chunk 大小）。如果模型经常截断，请尝试降低此值。' })
                    )}
                    data={batchSizeOpts || defaultBatchSizeOptions}
                    value={batchSize}
                    onChange={onChangeBatchSize}
                />
            )}

            {showConcurrency && (
                <Select
                    label={renderInfoLabel(
                        t('translation_page.translation_concurrency'),
                        t('translation_page.translation_concurrency_tooltip', { defaultValue: '同时进行的并发请求数量。本地部署的模型请设为 1，云端模型可适当调高。' })
                    )}
                    data={concurrencyOpts || defaultConcurrencyOptions}
                    value={concurrency}
                    onChange={onChangeConcurrency}
                />
            )}

            {showRpm && (
                <Select
                    label={renderInfoLabel(
                        t('incremental_translation.rpm_limit'),
                        t('translation_page.translation_rpm_tooltip', { defaultValue: '限制每分钟请求数。只对本次翻译生效，可用于避免接口限流或本地服务过载。' })
                    )}
                    data={rpmOpts || defaultRpmOptions}
                    value={rpm}
                    onChange={onChangeRpm}
                />
            )}
        </SimpleGrid>
    );
};

export default PerformanceControlPanel;
