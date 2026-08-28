import React from 'react';
import { Alert, Button, Group, Stack, Text } from '@mantine/core';
import { IconDatabaseOff } from '@tabler/icons-react';

import useReferenceLibraryAvailability from '../../hooks/useReferenceLibraryAvailability';

export default function ReferenceLibraryAvailabilityNotice({ enabled, gameId, onOpenSettings, t }) {
  const availability = useReferenceLibraryAvailability({ enabled, gameId });

  if (availability !== 'missing') return null;

  return (
    <Alert
      color="blue"
      icon={<IconDatabaseOff size={18} />}
      title={t('reference_prompt_title')}
      variant="light"
    >
      <Stack gap="xs">
        <Text size="sm">{t('reference_prompt_desc')}</Text>
        <Group>
          <Button size="xs" variant="light" onClick={onOpenSettings}>
            {t('reference_prompt_settings')}
          </Button>
        </Group>
      </Stack>
    </Alert>
  );
}
