import React from 'react';
import { Box, Card, Group, Stack, Switch, Text, TextInput } from '@mantine/core';
import ShellLanguageNotice from '../shared/ShellLanguageNotice';

export default function ShellLanguageSettingsCard({ form, disguiseOptions, renderNativeSelect, t }) {
  return (
              <Card withBorder p="md" radius="md" bg="var(--mantine-color-body)">
                <Stack gap="xs">
                  <Switch
                    label={t('form_label_disguise_mode')}
                    description={t('form_desc_disguise_mode')}
                    {...form.getInputProps('english_disguise', { type: 'checkbox' })}
                    onChange={(event) => {
                        form.setFieldValue('english_disguise', event.currentTarget.checked);
                        if (event.currentTarget.checked) {
                          form.setFieldValue('target_lang_codes', []);
                        } else {
                          form.setFieldValue('custom_name', '');
                          form.setFieldValue('custom_key', '');
                          form.setFieldValue('custom_prefix', '');
                          form.setFieldValue('disguise_target_key', '');
                        }
                    }}
                  />

                  {form.values.english_disguise && (
                    <>
                      <ShellLanguageNotice t={t} />
                      <Text size="sm" fw={500} mt="xs">{t('form_title_custom_config')}</Text>
                      <TextInput
                        label={t('form_label_custom_name')}
                        placeholder={t('form_placeholder_custom_name')}
                        description={t('form_desc_custom_name')}
                        {...form.getInputProps('custom_name')}
                      />
                      <Group grow>
                        <Box style={{ flex: 1 }}>
                          {renderNativeSelect({
                            label: t('form_label_disguise_target'),
                            value: form.values.disguise_target_key,
                            options: disguiseOptions,
                            onChange: (event) => {
                              const value = event.currentTarget.value;
                              form.setFieldValue('disguise_target_key', value);
                              form.setFieldValue('custom_key', value);
                            },
                          })}
                        </Box>
                        <TextInput
                          label={t('form_label_folder_prefix')}
                          placeholder={t('form_placeholder_folder_prefix')}
                          {...form.getInputProps('custom_prefix')}
                        />
                      </Group>
                    </>
                  )}
                </Stack>
              </Card>
  );
}
