import React from 'react';
import { Badge, Button, Group, Paper, Stack, Text } from '@mantine/core';

const TermVariantPicker = ({ candidate, disabled = false, onSelect, t }) => {
    const variants = candidate?.suggestion_variants || [];
    if (variants.length < 2) return null;

    return (
        <Stack gap="xs" data-testid="term-variant-picker">
            <Group justify="space-between">
                <Text fw={700} size="sm">
                    {t('neologism_review.court.ai_variants', { defaultValue: 'AI translation variants' })}
                </Text>
                <Badge variant="outline">{variants.length}</Badge>
            </Group>
            {variants.map((variant, index) => {
                const selected = (
                    candidate.suggestion === (variant.suggestion || '')
                    && candidate.reasoning === (variant.reasoning || '')
                );
                return (
                    <Paper
                        key={variant.variant_id || `${candidate.id}:variant:${index}`}
                        p="sm"
                        withBorder
                        data-testid="term-variant-option"
                    >
                        <Stack gap={4}>
                            <Group justify="space-between" align="flex-start" wrap="nowrap">
                                <Text fw={700} size="sm">{variant.suggestion || '—'}</Text>
                                <Button
                                    size="compact-xs"
                                    variant={selected ? 'filled' : 'light'}
                                    disabled={disabled || selected || !variant.variant_id}
                                    onClick={() => onSelect(variant)}
                                >
                                    {selected
                                        ? t('neologism_review.court.variant_selected', { defaultValue: 'Selected' })
                                        : t('neologism_review.court.select_variant', { defaultValue: 'Use this' })}
                                </Button>
                            </Group>
                            <Text size="xs" c="dimmed">{variant.reasoning || '—'}</Text>
                        </Stack>
                    </Paper>
                );
            })}
        </Stack>
    );
};

export default TermVariantPicker;
