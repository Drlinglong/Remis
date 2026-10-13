import { useState } from 'react';
import { Alert, Button, Checkbox, Paper, Select, Stack, Text, Textarea, TextInput, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import PublicationPreview, { PublicationOutcome } from './PublicationPreview';
import { useWorkshopPublication } from './useWorkshopPublication';
import PublicationRecoveryForm from './PublicationRecoveryForm';
import PublicationTagsInput from './PublicationTagsInput';
import PublicationGameSelect from './PublicationGameSelect';
import PublicationSetupGuide from './PublicationSetupGuide';

const initialValues = {
  output_folder_name: '', app_id: null, mode: 'create', published_file_id: '', title: '',
  change_note: '', visibility: 'private', language: 'english', tags: [],
};

export default function WorkshopPublicationPanel({ workspaceId }) {
  const { t } = useTranslation();
  const controller = useWorkshopPublication(workspaceId);
  const [values, setValues] = useState(initialValues);
  const [approved, setApproved] = useState(false);
  const appId = values.app_id ?? controller.options?.default_app_id ?? '';
  const change = (key, value) => {
    setValues((current) => ({ ...current, [key]: value }));
    setApproved(false);
    controller.invalidate();
  };
  const request = () => ({
    ...values, app_id: Number(appId),
    published_file_id: values.mode === 'update' ? values.published_file_id : null,
    tags: values.tags,
  });
  const outputs = controller.options?.outputs || [];
  const loadingOutputs = controller.options === null && !controller.error;
  const canPreview = !!values.output_folder_name && !!values.title.trim()
    && Number(appId) > 0 && (values.mode !== 'update' || /^[1-9][0-9]*$/.test(values.published_file_id));
  return (
    <Stack data-remis-surface="surface">
      <Title order={3}>{t('workshop_publication.title')}</Title>
      <Text c="dimmed">{t('workshop_publication.intro')}</Text>
      <PublicationSetupGuide runtime={controller.options?.runtime} />
      {controller.error && <Alert color="red">{controller.error}</Alert>}
      <Paper withBorder p="md" data-remis-surface="paper">
        <Stack>
          <Select label={t('workshop_publication.output')} value={values.output_folder_name || null}
            data={outputs.map((item) => ({ value: item.output_folder_name, label: item.output_folder_name }))}
            placeholder={loadingOutputs ? t('workshop_publication.output_loading', 'Loading output packages…')
              : t('workshop_publication.output_placeholder', 'Select an existing translation output')}
            description={outputs.length ? null : t('workshop_publication.output_empty',
              'No existing translation output was found. Generate an output for the linked project, or check its output directory in Project Management.')}
            onChange={(value) => change('output_folder_name', value || '')}
            disabled={controller.busy || loadingOutputs || !outputs.length} />
          <PublicationGameSelect value={appId} games={controller.options?.game_options || []}
            onChange={(value) => change('app_id', value)} disabled={controller.busy} />
          <Select label={t('workshop_publication.mode_label')} value={values.mode} allowDeselect={false}
            data={['create', 'update'].map((value) => ({ value, label: t(`workshop_publication.mode.${value}`) }))}
            onChange={(value) => change('mode', value)} disabled={controller.busy} />
          {values.mode === 'update' && <TextInput label={t('workshop_publication.item_id')} description={t('workshop_publication.target_warning')}
            value={values.published_file_id} onChange={(event) => change('published_file_id', event.currentTarget.value)} disabled={controller.busy} />}
          <TextInput label={t('workshop_publication.mod_title')} value={values.title} onChange={(event) => change('title', event.currentTarget.value)} disabled={controller.busy} />
          <Select label={t('workshop_publication.visibility_label')} value={values.visibility} allowDeselect={false}
            data={['private', 'public', 'friends_only', 'unlisted'].map((value) => ({ value, label: t(`workshop_publication.visibility.${value}`) }))}
            onChange={(value) => change('visibility', value)} disabled={controller.busy} />
          <TextInput label={t('workshop_publication.language')} value={values.language} onChange={(event) => change('language', event.currentTarget.value)} disabled={controller.busy} />
          <PublicationTagsInput value={values.tags} onChange={(tags) => change('tags', tags)} disabled={controller.busy} />
          <Textarea label={t('workshop_publication.change_note')} value={values.change_note} onChange={(event) => change('change_note', event.currentTarget.value)} disabled={controller.busy} />
          <Button disabled={!canPreview || controller.busy} loading={controller.busy}
            id="workshop-publication-preview"
            onClick={() => { setApproved(false); controller.createPreview(request()); }}>{t('workshop_publication.preview')}</Button>
        </Stack>
      </Paper>
      {controller.preview && <>
        <PublicationPreview plan={controller.preview} />
        {controller.preview.status === 'preview' && <>
          <Checkbox label={t('workshop_publication.approval')} checked={approved} onChange={(event) => setApproved(event.currentTarget.checked)} />
          <Button color="orange" loading={controller.busy}
            disabled={!approved || controller.busy || !controller.preview.allowed_actions.includes('approve_publication')}
            onClick={controller.submit}>{t('workshop_publication.submit')}</Button>
        </>}
      </>}
      <Title order={4}>{t('workshop_publication.history')}</Title>
      <Button variant="default" onClick={controller.refresh}>{t('workshop_publication.refresh')}</Button>
      {controller.history.map((plan) => <Paper key={plan.plan_id} withBorder p="md" data-remis-surface="paper">
        <PublicationOutcome plan={plan} />
        {plan.allowed_actions?.includes('verify_remote_outcome') && <PublicationRecoveryForm
          plan={plan} busy={controller.busy} onVerify={controller.verify}
          onRecovered={(request) => {
            if (request.resolution === 'item_present') setValues((current) => ({ ...current, mode: 'update', published_file_id: request.published_file_id }));
            setApproved(false);
          }} />}
      </Paper>)}
    </Stack>
  );
}
