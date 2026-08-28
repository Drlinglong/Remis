import React, { useMemo, useState } from 'react';
import {
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  ScrollArea,
  Stack,
  Switch,
  Text,
  TextInput,
} from '@mantine/core';
import { referenceEntryIdentity } from '../../utils/referenceReuse';

/**
 * Shared review controls for the persistent official reference library.
 */
export default function ReferenceReuseSettingsCard({
  enabled,
  onEnabledChange,
  onPreview = () => {},
  onToggleEntry = () => {},
  previewEntries = [],
  previewError = '',
  previewLoading = false,
  excludedEntries = [],
  t,
}) {
  const [query, setQuery] = useState('');
  const excludedIds = useMemo(
    () => new Set(excludedEntries.map(referenceEntryIdentity)),
    [excludedEntries],
  );
  const filteredEntries = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return previewEntries;
    return previewEntries.filter((entry) => [
      entry.key,
      entry.file_path,
      entry.source_text,
      entry.target_text,
      entry.target_lang_code,
    ].some((value) => String(value || '').toLocaleLowerCase().includes(normalized)));
  }, [previewEntries, query]);
  const selectedCount = previewEntries.length - excludedIds.size;

  return (
    <Card withBorder p="md" radius="md">
      <Stack gap="xs">
        <Switch
          checked={Boolean(enabled)}
          onChange={(event) => onEnabledChange(event.currentTarget.checked)}
          label={t('translation_config.reference_reuse')}
          description={t('translation_config.reference_reuse_desc')}
        />
        <Group justify="space-between" align="center">
          <Group gap="xs">
            <Badge variant="light">
              {t('translation_config.reference_matched_count', {
                count: previewEntries.length,
                defaultValue: `${previewEntries.length} exact matches`,
              })}
            </Badge>
            {excludedIds.size > 0 && (
              <Badge color="orange" variant="light">
                {t('translation_config.reference_deselected_count', {
                  count: excludedIds.size,
                  defaultValue: `${excludedIds.size} deselected`,
                })}
              </Badge>
            )}
          </Group>
          <Button
            size="xs"
            variant="light"
            loading={previewLoading}
            disabled={!enabled}
            onClick={onPreview}
          >
            {t('translation_config.reference_preview', { defaultValue: 'Scan exact matches' })}
          </Button>
        </Group>
        {previewError && <Text size="xs" c="red">{previewError}</Text>}
        {previewEntries.length > 0 && (
          <Stack gap="xs">
            <TextInput
              size="xs"
              value={query}
              onChange={(event) => setQuery(event.currentTarget.value)}
              placeholder={t('translation_config.reference_filter', { defaultValue: 'Filter by key, file, or text' })}
            />
            <Text size="xs" c="dimmed">
              {t('translation_config.reference_selected_count', {
                selected: selectedCount,
                total: previewEntries.length,
                defaultValue: `${selectedCount} of ${previewEntries.length} will reuse official translations`,
              })}
            </Text>
            <ScrollArea.Autosize mah={280} type="auto">
              <Stack gap={6} pr="xs">
                {filteredEntries.map((entry) => {
                  const identity = referenceEntryIdentity(entry);
                  return (
                    <Checkbox
                      key={identity}
                      checked={!excludedIds.has(identity)}
                      onChange={(event) => onToggleEntry(entry, event.currentTarget.checked)}
                      label={(
                        <Stack gap={1}>
                          <Text size="sm" fw={600}>{entry.key}</Text>
                          <Text size="xs" c="dimmed">
                            {entry.target_lang_code} · {entry.file_path}
                          </Text>
                          <Text size="xs">{entry.source_text} → {entry.target_text}</Text>
                        </Stack>
                      )}
                    />
                  );
                })}
              </Stack>
            </ScrollArea.Autosize>
          </Stack>
        )}
      </Stack>
    </Card>
  );
}
