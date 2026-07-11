import React from 'react';
import { Card, Stack, Switch, Text } from '@mantine/core';
import { IconClockHour4 } from '@tabler/icons-react';

import CollapsibleSettingsCard from './CollapsibleSettingsCard';

export default function ResumeSettingsCard({
  checkpointHintInfo,
  form,
  t,
}) {
  const [showResumeDetails, setShowResumeDetails] = React.useState(false);

  return (
    <CollapsibleSettingsCard
      accent="orange"
      icon={<IconClockHour4 size={18} />}
      isOpen={showResumeDetails}
      onToggle={() => setShowResumeDetails((value) => !value)}
      t={t}
      title={t('translation_page.resume_detail_title', { defaultValue: '断点续传详情' })}
      description={t('translation_page.resume_detail_subtitle', { defaultValue: '默认收起。展开后可查看上次工作进行到什么时间、什么批次。' })}
      action={(
        <Switch
          id="use-resume-switch"
          label={t('form_label_use_resume')}
          description={t('form_desc_use_resume')}
          checked={form.values.use_resume}
          onChange={(event) => form.setFieldValue('use_resume', event.currentTarget.checked)}
        />
      )}
    >
      {checkpointHintInfo ? (
        <Stack gap="xs">
          {(checkpointHintInfo.targets || []).map((target) => (
            <Card key={target.target_lang_code} withBorder p="sm" radius="md" bg="rgba(255,255,255,0.03)">
              <Stack gap={4}>
                <Text size="sm" fw={600} c="var(--text-main)">{target.target_lang_code}</Text>
                <Text size="sm">
                  {t('translation_page.resume_detail_completed', {
                    defaultValue: '已完成文件：{{count}}',
                    count: target.completed_count ?? 0,
                  })}
                </Text>
                <Text size="sm">
                  {t('translation_page.resume_detail_batch', {
                    defaultValue: '上次批次：{{current}} / {{total}}',
                    current: target.metadata?.current_batch ?? 0,
                    total: target.metadata?.total_batches ?? 0,
                  })}
                </Text>
                <Text size="sm">
                  {t('translation_page.resume_detail_time', {
                    defaultValue: '上次保存：{{time}}',
                    time: target.last_saved_at || target.metadata?.last_saved_at || '--',
                  })}
                </Text>
                <Text size="sm">
                  {t('translation_page.resume_detail_file', {
                    defaultValue: '最后完成文件：{{file}}',
                    file: target.last_completed_file || target.metadata?.last_completed_file || '--',
                  })}
                </Text>
              </Stack>
            </Card>
          ))}
          {(!checkpointHintInfo.targets || checkpointHintInfo.targets.length === 0) && (
            <Text size="sm" c="dimmed">
              {t('translation_page.resume_detail_empty', { defaultValue: '当前没有可展示的断点详情。' })}
            </Text>
          )}
        </Stack>
      ) : (
        <Text size="sm" c="dimmed">
          {t('translation_page.resume_detail_none', { defaultValue: '没有未完成的工作。' })}
        </Text>
      )}
    </CollapsibleSettingsCard>
  );
}
