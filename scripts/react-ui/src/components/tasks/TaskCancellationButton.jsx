import React, { useState } from 'react';
import { Button } from '@mantine/core';
import { IconPlayerStop } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import api from '../../utils/api';

export function TaskCancellationButton({ onError, onRefresh, task }) {
  const { t } = useTranslation();
  const [cancelling, setCancelling] = useState(false);

  const requestCancellation = async () => {
    const confirmed = window.confirm(t('task_detail.cancel_confirm', {
      defaultValue: 'Cancel this translation task? The current provider request may need a moment to stop safely.',
    }));
    if (!confirmed) return;
    setCancelling(true);
    onError('');
    try {
      await api.post(`/api/tasks/${encodeURIComponent(task.task_id)}/cancel`);
      await onRefresh();
    } catch (error) {
      onError(
        error.response?.data?.detail
        || error.message
        || t('task_detail.cancel_error', { defaultValue: 'Failed to cancel the task.' }),
      );
    } finally {
      setCancelling(false);
    }
  };

  if (!task.allowed_actions?.includes('cancel_task')) return null;
  return (
    <Button
      color="red"
      variant="light"
      leftSection={<IconPlayerStop size={17} />}
      loading={cancelling}
      onClick={requestCancellation}
    >
      {t('task_detail.cancel_task', { defaultValue: 'Cancel task' })}
    </Button>
  );
}
