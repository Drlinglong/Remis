import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Box,
  Button,
  Group,
  LoadingOverlay,
  Paper,
  ScrollArea,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconAlertTriangle,
  IconCheck,
  IconExternalLink,
  IconSparkles,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import api from '../../utils/api';
import { normalizeGlossaryContentPayload } from '../../utils/glossaryPayload';
import styles from './GlossaryHealthWorkbench.module.css';

const caseKey = (item) => `${item.issueCode}:${item.entry_id || item.source}`;

const buildGlossaryRoute = (item, targetLang) => {
  const params = new URLSearchParams();
  if (item.game_id) params.set('game_id', item.game_id);
  if (item.glossary_id != null) params.set('glossary_id', String(item.glossary_id));
  if (item.entry_id) params.set('focus_entry_id', item.entry_id);
  if (targetLang) params.set('target_lang', targetLang);
  return `/glossary-manager?${params.toString()}`;
};

const GlossaryHealthWorkbench = ({ report }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const cases = useMemo(() => (
    (report.issues || []).flatMap((issue) => (issue.items || []).map((item) => ({
      ...item,
      issueCode: issue.code,
      issueMessage: t(`glossary_health_issue_${issue.code}`, {
        defaultValue: issue.message || issue.code,
      }),
      severity: issue.severity,
    })))
  ), [report.issues, t]);
  const adviceByCase = useMemo(() => new Map(
    (report.ai_advice || []).map((advice) => [
      advice.case_id || advice.issue_code,
      advice,
    ]),
  ), [report.ai_advice]);

  const [selectedKey, setSelectedKey] = useState(() => (cases[0] ? caseKey(cases[0]) : null));
  const [currentEntry, setCurrentEntry] = useState(null);
  const [draftSource, setDraftSource] = useState('');
  const [draftTranslation, setDraftTranslation] = useState('');
  const [draftNotes, setDraftNotes] = useState('');
  const [aiDraftApplied, setAiDraftApplied] = useState(false);
  const [loadingEntry, setLoadingEntry] = useState(false);
  const [saving, setSaving] = useState(false);
  const [handledEntries, setHandledEntries] = useState(() => new Set());

  const selectedCase = cases.find((item) => caseKey(item) === selectedKey) || cases[0] || null;
  const selectedAdvice = selectedCase
    ? (
      adviceByCase.get(caseKey(selectedCase))
      || adviceByCase.get(selectedCase.issueCode)
    )
    : null;
  const hasApplicableAiDraft = Boolean(
    selectedAdvice?.case_id
    && (selectedAdvice.suggested_source || selectedAdvice.suggested_translation),
  );
  const targetLang = report.target_lang || currentEntry?.metadata?.target_lang || '';

  useEffect(() => {
    if (!selectedCase?.entry_id || selectedCase.glossary_id == null) {
      setCurrentEntry(null);
      return;
    }

    let active = true;
    const fetchEntry = async () => {
      setLoadingEntry(true);
      try {
        const response = await api.post('/api/glossary/search', {
          scope: 'file',
          query: selectedCase.entry_id,
          page: 1,
          pageSize: 25,
          game_id: null,
          file_name: `${selectedCase.game_id || 'unknown'}|${selectedCase.glossary_id}|${selectedCase.glossary_name || ''}`,
        });
        const entry = normalizeGlossaryContentPayload(response.data).entries
            .find((item) => item.id === selectedCase.entry_id);
        if (!active) return;
        setCurrentEntry(entry || null);
        const existingSource = entry?.source || selectedCase.source || '';
        setDraftSource(existingSource);
        const language = report.target_lang || entry?.metadata?.target_lang || '';
        const existingTranslation = language ? (entry?.translations?.[language] || '') : '';
        setDraftTranslation(existingTranslation);
        setDraftNotes((entry?.notes || '').trim());
        setAiDraftApplied(false);
      } catch {
        if (!active) return;
        setCurrentEntry(null);
        notifications.show({
          title: t('neologism_review.common.error', { defaultValue: 'Error' }),
          message: t('glossary_health_entry_load_failed', { defaultValue: 'Could not load the current glossary entry.' }),
          color: 'red',
        });
      } finally {
        if (active) setLoadingEntry(false);
      }
    };

    fetchEntry();
    return () => { active = false; };
  }, [
    report.target_lang,
    selectedAdvice?.case_id,
    selectedAdvice?.rationale,
    selectedAdvice?.recommendation,
    selectedAdvice?.suggested_source,
    selectedAdvice?.suggested_translation,
    selectedCase?.entry_id,
    selectedCase?.game_id,
    selectedCase?.glossary_id,
    selectedCase?.glossary_name,
    selectedCase?.source,
    t,
  ]);

  const moveToNextCase = (entryId) => {
    const next = cases.find((item) => item.entry_id !== entryId && !handledEntries.has(item.entry_id));
    if (next) setSelectedKey(caseKey(next));
  };

  const applyAiSuggestion = () => {
    if (!hasApplicableAiDraft) return;
    if (selectedAdvice.suggested_source) {
      setDraftSource(selectedAdvice.suggested_source);
    }
    if (selectedAdvice.suggested_translation) {
      setDraftTranslation(selectedAdvice.suggested_translation);
    }
    setAiDraftApplied(true);
  };

  const saveEntry = async () => {
    if (!currentEntry || !selectedCase) return;
    setSaving(true);
    try {
      const translations = { ...(currentEntry.translations || {}) };
      if (targetLang) translations[targetLang] = draftTranslation;
      await api.put(`/api/glossary/entry/${encodeURIComponent(currentEntry.id)}`, {
        id: currentEntry.id,
        source: draftSource,
        translations,
        notes: draftNotes,
        variants: currentEntry.variants || {},
        abbreviations: currentEntry.abbreviations || {},
        metadata: currentEntry.metadata || {},
      });
      setCurrentEntry((entry) => ({
        ...entry,
        source: draftSource,
        translations,
        notes: draftNotes,
      }));
      setHandledEntries((current) => new Set([...current, selectedCase.entry_id]));
      notifications.show({
        title: t('glossary_health_entry_saved', { defaultValue: 'Glossary entry updated' }),
        message: t('glossary_health_rerun_required', { defaultValue: 'Run the health check again to verify the issue is resolved.' }),
        color: 'green',
      });
      moveToNextCase(selectedCase.entry_id);
    } catch {
      notifications.show({
        title: t('neologism_review.common.error', { defaultValue: 'Error' }),
        message: t('glossary_health_entry_save_failed', { defaultValue: 'Could not update the glossary entry.' }),
        color: 'red',
      });
    } finally {
      setSaving(false);
    }
  };

  if (!cases.length) return null;

  return (
    <Box className={styles.root} data-testid="glossary-health-workbench">
      <Box component="aside" className={styles.queue}>
        <Group justify="space-between" className={styles.queueHeader}>
          <Text size="sm" fw={700}>{t('glossary_health_issues', { defaultValue: 'Issues' })}</Text>
          <Badge variant="light" color="gray">{cases.length}</Badge>
        </Group>
        <ScrollArea className={styles.queueScroll} type="auto" offsetScrollbars>
          <Stack gap="xs" className={styles.queueList}>
              {cases.map((item) => {
                const key = caseKey(item);
                const handled = handledEntries.has(item.entry_id);
                return (
                  <Paper
                    key={key}
                    component="button"
                    type="button"
                    p="sm"
                    radius="md"
                    onClick={() => setSelectedKey(key)}
                    aria-pressed={key === selectedKey}
                    className={styles.queueItem}
                    data-selected={key === selectedKey}
                  >
                    <Group justify="space-between" wrap="nowrap">
                      <Text fw={700} lineClamp={2} className={styles.queueTerm}>
                        {item.source || item.entry_id}
                      </Text>
                      {handled && <IconCheck size={16} color="var(--mantine-color-teal-5)" />}
                    </Group>
                    <Text size="xs" c="dimmed" lineClamp={2}>{item.issueMessage}</Text>
                  </Paper>
                );
              })}
          </Stack>
        </ScrollArea>
      </Box>

      <Box component="section" className={styles.review}>
        <LoadingOverlay visible={loadingEntry || saving} />
        <ScrollArea className={styles.reviewScroll} type="auto" offsetScrollbars>
          {selectedCase && (
            <Stack gap="lg" className={styles.reviewContent}>
              <Group justify="space-between" align="flex-start" gap="md" wrap="wrap">
                <Box className={styles.caseHeading}>
                  <Text size="xs" c="dimmed" tt="uppercase" fw={700}>{selectedCase.issueMessage}</Text>
                  <Title order={2}>{selectedCase.source || selectedCase.entry_id}</Title>
                </Box>
                <Badge
                  color={selectedCase.severity === 'error' ? 'red' : selectedCase.severity === 'warning' ? 'orange' : 'blue'}
                  className={styles.issueCode}
                  title={selectedCase.issueCode}
                >
                  {selectedCase.issueCode}
                </Badge>
              </Group>

              <Alert icon={<IconAlertTriangle size={16} />} color="orange">
                {selectedCase.detail}
              </Alert>

              {selectedAdvice && (
                <Paper withBorder radius="md" className={styles.advice}>
                  <Group gap="xs" mb={6}>
                    <IconSparkles size={16} />
                    <Text fw={700}>{t('glossary_health_ai_advice', { defaultValue: 'AI advice' })}</Text>
                    <Badge variant="light" color="teal">
                      {t('glossary_health_ai_suggestion_badge', { defaultValue: 'Suggestion — review required' })}
                    </Badge>
                  </Group>
                  {(report.ai_provider || report.ai_model) && (
                    <Text size="xs" c="dimmed" mb={8}>
                      {[
                        report.ai_provider
                          ? `${t('glossary_health_provider', { defaultValue: 'Provider' })}: ${report.ai_provider}`
                          : null,
                        report.ai_model
                          ? `${t('glossary_health_model', { defaultValue: 'Model' })}: ${report.ai_model}`
                          : null,
                      ].filter(Boolean).join(' · ')}
                    </Text>
                  )}
                  <Text size="xs" c="dimmed" fw={700} tt="uppercase">
                    {t('glossary_health_ai_note_prefix', { defaultValue: 'AI review suggestion' })}
                  </Text>
                  <Text size="sm">{selectedAdvice.recommendation}</Text>

                  {hasApplicableAiDraft && (
                    <>
                      <Box className={styles.suggestionValues}>
                        {selectedAdvice.suggested_source && (
                          <Box>
                            <Text size="xs" c="dimmed" fw={700}>
                              {t('glossary_source_text')}
                            </Text>
                            <Text size="sm">{selectedAdvice.suggested_source}</Text>
                          </Box>
                        )}
                        {selectedAdvice.suggested_translation && (
                          <Box>
                            <Text size="xs" c="dimmed" fw={700}>
                              {t('glossary_translation')} {targetLang ? `(${targetLang})` : ''}
                            </Text>
                            <Text size="sm">{selectedAdvice.suggested_translation}</Text>
                          </Box>
                        )}
                      </Box>
                      <Button
                        size="xs"
                        variant={aiDraftApplied ? 'light' : 'filled'}
                        color="teal"
                        onClick={applyAiSuggestion}
                      >
                        {aiDraftApplied
                          ? t('glossary_health_ai_suggestion_applied', { defaultValue: 'Applied to editable draft' })
                          : t('glossary_health_apply_ai_suggestion', { defaultValue: 'Apply suggestion to editable draft' })}
                      </Button>
                    </>
                  )}

                  <Box className={styles.rationale}>
                    <Text size="xs" c="dimmed" fw={700} tt="uppercase">
                      {t('glossary_health_ai_reason_prefix', { defaultValue: 'Rationale' })}
                    </Text>
                    <Text size="sm">{selectedAdvice.rationale}</Text>
                  </Box>
                </Paper>
              )}

              {currentEntry ? (
                <Box className={styles.editor}>
                  <Stack gap="md">
                    <Box>
                      <Text fw={700}>
                        {t('glossary_health_editable_values', { defaultValue: 'Editable glossary values' })}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {t(
                          'glossary_health_editable_values_help',
                          { defaultValue: 'Only the values in this section are saved. AI rationale is not added to notes automatically.' },
                        )}
                      </Text>
                    </Box>
                    <TextInput
                      label={t('glossary_source_text')}
                      value={draftSource}
                      onChange={(event) => setDraftSource(event.currentTarget.value)}
                      required
                    />
                    {targetLang ? (
                      <TextInput
                        label={`${t('glossary_translation')} (${targetLang})`}
                        value={draftTranslation}
                        onChange={(event) => setDraftTranslation(event.currentTarget.value)}
                        required
                      />
                    ) : (
                      <Alert color="blue">
                        {t('glossary_health_choose_language', { defaultValue: 'Open the glossary editor to choose which translation language to change.' })}
                      </Alert>
                    )}
                    <Textarea
                      label={t('glossary_notes')}
                      value={draftNotes}
                      onChange={(event) => setDraftNotes(event.currentTarget.value)}
                      minRows={4}
                      autosize
                    />
                    <Group justify="space-between" gap="sm" className={styles.actions}>
                      <Button
                        variant="default"
                        leftSection={<IconExternalLink size={16} />}
                        onClick={() => navigate(buildGlossaryRoute(selectedCase, targetLang))}
                      >
                        {t('glossary_health_open_full_editor', { defaultValue: 'Open full editor' })}
                      </Button>
                      <Button
                        color="teal"
                        onClick={saveEntry}
                        loading={saving}
                        disabled={!draftSource.trim() || (targetLang && !draftTranslation.trim())}
                      >
                        {t('glossary_health_save_and_next', { defaultValue: 'Save and review next' })}
                      </Button>
                    </Group>
                  </Stack>
                </Box>
              ) : !loadingEntry && (
                <Alert color="red">
                  {t('glossary_health_entry_missing', { defaultValue: 'This entry no longer exists or could not be loaded.' })}
                </Alert>
              )}
            </Stack>
          )}
        </ScrollArea>
      </Box>
    </Box>
  );
};

export default GlossaryHealthWorkbench;
