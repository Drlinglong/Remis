import React, { useState } from 'react';
import { open } from '@tauri-apps/plugin-dialog';
import {
  Accordion, Alert, Button, Checkbox, Code, Group, Modal, Radio, ScrollArea, Stack, Text, TextInput,
} from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useMarsPipelineImport } from '../../hooks/useMarsPipelineImport';
import modalStyles from '../projectManagement/CreateProjectModal.module.css';
import styles from './MarsPipelineImport.module.css';

function ImportChoice({ mode, onChange, t }) {
  return (
    <Radio.Group value={mode} onChange={onChange} name="mars-import-mode"
      label={t('mars_pipeline.import_outcome', 'How should Remis prepare this Mod?')}>
      <Stack gap="xs" mt="xs">
        <Radio value="text_only" label={t('mars_pipeline.text_only', 'Translation text only')} />
        <Radio value="source_copy" label={t('mars_pipeline.source_copy', 'Complete translated Mod copy')} />
      </Stack>
    </Radio.Group>
  );
}

function ModeRecommendation({ plan, mode, t }) {
  if (!plan) return null;
  const hasHardcoded = plan.hardcoded_entry_count > 0;
  return (
    <Alert color={hasHardcoded && mode === 'source_copy' ? 'blue' : 'yellow'}>
      <Text size="sm">{t('mars_pipeline.inventory', '{{files}} files · {{entries}} text entries', {
        files: plan.file_count, entries: plan.entry_count,
      })}</Text>
      <Text size="sm" mt="xs">{t('mars_pipeline.selected_inventory', '{{count}} entries selected for this preparation', {
        count: plan.selected_entry_count,
      })}</Text>
      {hasHardcoded && <Text size="sm" mt="xs">
        {mode === 'source_copy'
          ? t('mars_pipeline.full_copy_recommendation', '{{count}} text candidates are embedded in Lua. A complete copy includes all assets and is recommended so these strings can be translated in context.', {
            count: plan.hardcoded_entry_count,
          })
          : t('mars_pipeline.text_only_coverage', 'Text-only preparation leaves {{count}} Lua-embedded text candidates unchanged.', {
            count: plan.hardcoded_entry_count,
          })}
      </Text>}
      {plan.recommended_delivery_mode && <Text size="sm" mt="xs">
        {t('mars_pipeline.recommended_mode', 'Recommended: {{mode}}', {
          mode: plan.recommended_delivery_mode === 'source_copy'
            ? t('mars_pipeline.source_copy', 'Complete translated Mod copy')
            : t('mars_pipeline.text_only', 'Translation text only'),
        })}
      </Text>}
    </Alert>
  );
}

export default function MarsPipelineImport({ opened, onClose, onCreated, name, onUseExistingCsv, controller }) {
  const { t } = useTranslation();
  const hookFlow = useMarsPipelineImport(onCreated, name);
  const flow = controller || hookFlow;
  const [reviewSelection, setReviewSelection] = useState([]);
  const pending = flow.plan?.review_items || [];
  const browseArchive = async () => {
    const selected = await open({ multiple: false, directory: false,
      filters: [{ name: 'Surviving Mars archive', extensions: ['fpk'] }] });
    if (typeof selected === 'string') flow.update('path', selected);
  };

  return (
    <Modal opened={opened} onClose={onClose} title={t('mars_pipeline.import_title', 'Prepare a Surviving Mars Mod')}
      size="lg" centered classNames={{
        content: modalStyles.modalContent, header: modalStyles.modalHeader,
        title: modalStyles.modalTitle, body: modalStyles.modalBody, close: modalStyles.modalClose,
      }}>
      <Stack gap="md" data-remis-surface="paper" className={styles.importSurface}>
        <Text size="sm">{t('mars_pipeline.import_help', 'Remis extracts the complete FPK into an isolated project and reads English source text. It leaves the archive and installed Mods unchanged.')}</Text>
        <Group align="flex-end">
          <TextInput classNames={{ input: modalStyles.modalInput }}
            label={t('mars_pipeline.archive_path', 'ModContent.fpk path')} value={flow.path}
            disabled={flow.busy} onChange={(event) => {
              setReviewSelection([]);
              flow.update('path', event.currentTarget.value);
            }} style={{ flex: 1 }} />
          <Button variant="light" disabled={flow.busy} onClick={browseArchive}>
            {t('mars_pipeline.browse_archive', 'Browse')}
          </Button>
        </Group>
        {!name?.trim() && <Alert color="yellow">
          {t('mars_pipeline.name_required', 'Enter the project name in the previous window before inspecting this archive.')}
        </Alert>}
        <Accordion variant="contained">
          <Accordion.Item value="advanced">
            <Accordion.Control>{t('mars_pipeline.advanced_options', 'Advanced options')}</Accordion.Control>
            <Accordion.Panel>
              <TextInput classNames={{ input: modalStyles.modalInput }}
                label={t('mars_pipeline.previous_run', 'Previous preparation run (optional, for Mod updates)')}
                value={flow.previousRun} disabled={flow.busy}
                onChange={(event) => {
                  setReviewSelection([]);
                  flow.update('previousRun', event.currentTarget.value);
                }} />
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
        {flow.error && <Alert color="red" role="alert">{flow.error}</Alert>}
        <Group>
          <Button variant="light" loading={flow.busy} disabled={!flow.path || !name?.trim()}
            onClick={() => flow.preview()}>{t('mars_pipeline.inspect', 'Inspect archive and text')}</Button>
          <Button variant="subtle" disabled={flow.busy} onClick={onUseExistingCsv}>
            {t('mars_pipeline.use_csv_folder', 'Use an existing editable CSV folder instead')}
          </Button>
        </Group>
        {flow.inspection && <>
          <ImportChoice mode={flow.deliveryMode} t={t} onChange={(value) => {
            setReviewSelection([]);
            flow.preview([], value);
          }} />
          <Text size="xs" c="dimmed">{flow.deliveryMode === 'source_copy'
            ? t('mars_pipeline.source_copy_help', 'Includes every source asset and creates a new Mod ID. Disable the Workshop original before enabling this copy.')
            : t('mars_pipeline.text_only_help', 'Prepares the localization text as an independent Mod. It does not include the original assets or rewrite the original Lua.')}</Text>
          <ModeRecommendation plan={flow.inspection} mode={flow.deliveryMode} t={t} />
          {flow.busy && <Text size="sm" c="dimmed">
            {t('mars_pipeline.updating_inspection', 'Updating the preview for this choice…')}
          </Text>}
        </>}
        {pending.length > 0 && <Accordion variant="separated">
          <Accordion.Item value="review">
            <Accordion.Control>{t('mars_pipeline.review_count', 'Review {{count}} remaining text candidates', {
              count: pending.length,
            })}</Accordion.Control>
            <Accordion.Panel>
              <Text size="sm" mb="sm">{t('mars_pipeline.review_help', 'Select only text you have reviewed and want to include. Unselected or ambiguous candidates remain unchanged.')}</Text>
              <ScrollArea.Autosize mah={220}>
                {pending.map((item) => <Stack key={item.id} gap={2} my="sm">
                  <Checkbox checked={reviewSelection.includes(item.id)} label={item.text}
                    onChange={(event) => setReviewSelection((old) => event.currentTarget.checked
                      ? [...old, item.id] : old.filter((id) => id !== item.id))} />
                  <Code>{item.refs?.[0]?.path}:{item.refs?.[0]?.line}</Code>
                  {item.reason && <Text size="xs">{item.reason}</Text>}
                </Stack>)}
              </ScrollArea.Autosize>
              <Button mt="sm" variant="light" disabled={flow.busy || !reviewSelection.length}
                onClick={async () => {
                  await flow.preview([...flow.approved, ...reviewSelection]);
                  setReviewSelection([]);
                }}>
                {t('mars_pipeline.approve_candidates', 'Include selected reviewed text')}
              </Button>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>}
        {flow.plan && <Group justify="flex-end">
          <Button disabled={flow.busy || pending.length > 0} onClick={flow.execute}>
            {t('mars_pipeline.prepare', 'Create isolated translation project')}
          </Button>
        </Group>}
        {flow.error.includes('Do not repeat') && <Text size="sm">{flow.error}</Text>}
        {flow.error.includes('Do not repeat') && <Button variant="subtle" onClick={onClose}>
          {t('button_close', 'Close')}
        </Button>}
      </Stack>
    </Modal>
  );
}
