import React from 'react';
import { Accordion, Alert, Code, Stack, Text } from '@mantine/core';

export default function MarsSourceReviewNotice({ items = [], t }) {
  if (!items.length) return null;
  return <Alert color="yellow">
    <Text>{t('mars_pipeline.pending_after_creation', '{{count}} text candidates need review. Your project is ready for the confirmed text; these candidates remain unchanged in the original Mod.', { count: items.length })}</Text>
    <Accordion mt="sm">
      <Accordion.Item value="review">
        <Accordion.Control>{t('mars_pipeline.review_count', 'Review {{count}} remaining text candidates', { count: items.length })}</Accordion.Control>
        <Accordion.Panel>
          <Stack gap="sm">
            {items.map((item) => <Stack key={item.id} gap={2}>
              <Text size="sm">{item.text}</Text>
              <Code>{item.refs?.[0]?.path}:{item.refs?.[0]?.line}</Code>
              {item.reason && <Text size="xs">{item.reason}</Text>}
            </Stack>)}
          </Stack>
          <Text size="sm" mt="sm">{t('mars_pipeline.review_later_help', 'Review these candidates before preparing Lua changes or claiming complete coverage. Keep the preparation run shown below when updating this project.')}</Text>
        </Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  </Alert>;
}
