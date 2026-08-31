import React from 'react';
import { Alert } from '@mantine/core';
import { IconAlertTriangle } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import {
  getTaskFailurePresentation,
  getTaskNextStep,
} from '../../utils/taskPresentation';

export function TaskFailureAlert({ hidden = false, task }) {
  const { t } = useTranslation();
  const visible = task?.attention_reason || ['failed', 'interrupted'].includes(task?.status);
  if (hidden || !visible) return null;

  const presentation = getTaskFailurePresentation(task, t);
  return (
    <Alert
      color="red"
      icon={<IconAlertTriangle size={18} />}
      mb="md"
      title={presentation?.title}
    >
      {presentation?.message || getTaskNextStep(task, t)}
    </Alert>
  );
}
