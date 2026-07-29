import React, { useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  Progress,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  Title,
} from '@mantine/core';
import {
  IconAlertCircle,
  IconArrowLeft,
  IconArrowRight,
  IconCheck,
  IconEqual,
  IconLock,
  IconMoodSad,
  IconRefresh,
  IconThumbUp,
} from '@tabler/icons-react';

const REASONS = ['faithful', 'natural', 'style', 'concise', 'terminology', 'context'];

const sampleOutputs = (sample) => sample.outputs || sample.candidates || [];

const featureTagLabel = (tag, t) => {
  if (tag.startsWith('length:')) {
    return t(`model_arena.feature_length_${tag.slice('length:'.length)}`, {
      defaultValue: tag,
    });
  }
  if (tag.startsWith('file:')) {
    return t('model_arena.feature_file', {
      file: tag.slice('file:'.length),
      defaultValue: tag,
    });
  }
  return t(`model_arena.feature_${tag}`, { defaultValue: tag });
};

export default function ArenaVoting({
  t,
  run,
  votes,
  saving,
  onSaveVote,
  onComplete,
  onRetryFailures,
  retrying,
}) {
  const samples = run.samples || [];
  const firstUnvoted = Math.max(0, samples.findIndex((sample) => !votes[sample.sample_id]));
  const [activeIndex, setActiveIndex] = useState(firstUnvoted < 0 ? 0 : firstUnvoted);
  const sample = samples[activeIndex];
  const existingVote = votes[sample?.sample_id] || sample?.vote || {};
  const [selection, setSelection] = useState(existingVote.winner_output_id
    ? `winner:${existingVote.winner_output_id}`
    : existingVote.verdict || '');
  const [reasons, setReasons] = useState(existingVote.reason_codes || []);
  const [note, setNote] = useState(existingVote.note || '');
  const [reviewingCompletedVotes, setReviewingCompletedVotes] = useState(false);

  const comparable = sampleOutputs(sample).filter((output) => (
    output.translated_text || output.text
  )).length >= 2;
  const votedCount = samples.filter((item) => votes[item.sample_id] || item.vote).length;
  const allVoted = samples.length > 0 && votedCount === samples.length;
  const progress = samples.length ? (votedCount / samples.length) * 100 : 0;

  const changeSample = (nextIndex) => {
    const nextSample = samples[nextIndex];
    const nextVote = votes[nextSample?.sample_id] || nextSample?.vote || {};
    setActiveIndex(nextIndex);
    setSelection(nextVote.winner_output_id
      ? `winner:${nextVote.winner_output_id}`
      : nextVote.verdict || '');
    setReasons(nextVote.reason_codes || []);
    setNote(nextVote.note || '');
  };

  const votePayload = useMemo(() => {
    if (selection.startsWith('winner:')) {
      return {
        verdict: 'winner',
        winner_output_id: selection.slice('winner:'.length),
        reason_codes: reasons,
        note: note.trim() || null,
      };
    }
    return {
      verdict: selection || (comparable ? '' : 'unjudgeable'),
      winner_output_id: null,
      reason_codes: reasons,
      note: note.trim() || null,
    };
  }, [comparable, note, reasons, selection]);

  if (!sample) {
    return <Alert color="yellow">{t('model_arena.no_samples')}</Alert>;
  }

  const saveAndAdvance = async () => {
    await onSaveVote(sample.sample_id, votePayload);
    if (activeIndex < samples.length - 1) changeSample(activeIndex + 1);
  };

  if (allVoted && !reviewingCompletedVotes) {
    return (
      <Card
        data-remis-surface="paper"
        withBorder
        radius="md"
        padding="xl"
        className="model-arena-completion"
      >
        <Stack gap="lg" align="center">
          <IconCheck size={42} aria-hidden />
          <div>
            <Title order={3} ta="center">{t('model_arena.votes_complete_title')}</Title>
            <Text c="dimmed" ta="center" mt="xs">
              {t('model_arena.votes_complete_description', { count: samples.length })}
            </Text>
          </div>
          <Progress value={100} w="100%" aria-label={t('model_arena.vote_progress')} />
          <Group justify="center">
            <Button
              variant="default"
              onClick={() => setReviewingCompletedVotes(true)}
            >
              {t('model_arena.review_votes')}
            </Button>
            <Button
              data-remis-action="paper-primary"
              size="md"
              onClick={onComplete}
            >
              {t('model_arena.complete_reveal')}
            </Button>
          </Group>
        </Stack>
      </Card>
    );
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <div>
          <Title order={3}>{t('model_arena.voting_title')}</Title>
          <Text c="dimmed">{t('model_arena.voting_description')}</Text>
        </div>
        <Badge variant="light" size="lg">
          {t('model_arena.sample_progress', { current: activeIndex + 1, total: samples.length })}
        </Badge>
      </Group>

      <Progress value={progress} aria-label={t('model_arena.vote_progress')} />
      <Alert icon={<IconLock size={18} />} color="blue" variant="light">
        {t('model_arena.identity_hidden')}
      </Alert>
      {run.status === 'partial_failed' && (
        <Alert color="yellow" icon={<IconAlertCircle size={18} />} title={t('model_arena.partial_failed')}>
          <Group justify="space-between">
            <Text size="sm">{t('model_arena.partial_failed_description')}</Text>
            <Button
              variant="light"
              color="yellow"
              leftSection={<IconRefresh size={16} />}
              onClick={onRetryFailures}
              loading={retrying}
            >
              {t('model_arena.retry_failures')}
            </Button>
          </Group>
        </Alert>
      )}

      <Card data-remis-surface="paper" withBorder radius="md" padding="lg">
        <Text size="xs" fw={700} tt="uppercase" c="dimmed">{t('model_arena.source_text')}</Text>
        <Text mt="xs" className="model-arena-source">{sample.source_text}</Text>
        {Array.isArray(sample.feature_tags) && (
          <Group gap="xs" mt="md">
            {sample.feature_tags.map((tag) => (
              <Badge key={tag} variant="outline">
                {featureTagLabel(tag, t)}
              </Badge>
            ))}
          </Group>
        )}
      </Card>

      {!comparable && (
        <Alert color="yellow" icon={<IconAlertCircle size={18} />}>
          {t('model_arena.unjudgeable_description')}
        </Alert>
      )}

      <Stack gap="md">
        <SimpleGrid cols={{ base: 1, md: Math.min(3, sampleOutputs(sample).length || 2) }}>
          {sampleOutputs(sample).map((output, index) => {
            const outputId = output.output_id || output.id;
            const text = output.translated_text || output.text;
            const value = `winner:${outputId}`;
            const selected = selection === value;
            return (
              <Card
                key={outputId}
                className="model-arena-choice-card"
                data-remis-surface="paper"
                withBorder
                radius="md"
                padding="lg"
                data-selected={selected || undefined}
              >
                <Stack justify="space-between" h="100%">
                  <div>
                    <Badge variant="filled" color="gray" mb="md">
                      {output.anonymous_label || String.fromCharCode(65 + index)}
                    </Badge>
                    <Text>{text || t('model_arena.unavailable_output')}</Text>
                  </div>
                  <Button
                    className="model-arena-decision-button"
                    data-remis-action={selected ? 'paper-primary' : 'paper-secondary'}
                    variant={selected ? 'filled' : 'outline'}
                    leftSection={<IconThumbUp size={17} />}
                    aria-label={t('model_arena.choose_candidate')}
                    aria-pressed={selected}
                    disabled={!text}
                    fullWidth
                    onClick={() => setSelection(value)}
                  >
                    {t('model_arena.choose_candidate')}
                  </Button>
                </Stack>
              </Card>
            );
          })}
        </SimpleGrid>
        <SimpleGrid cols={{ base: 1, sm: comparable ? 2 : 1 }}>
          {comparable ? (
            <>
              <Button
                className="model-arena-decision-button"
                data-remis-action={selection === 'tie' ? 'primary' : 'secondary'}
                variant={selection === 'tie' ? 'filled' : 'outline'}
                leftSection={<IconEqual size={18} />}
                aria-label={t('model_arena.tie')}
                aria-pressed={selection === 'tie'}
                onClick={() => {
                  setSelection('tie');
                  setReasons([]);
                }}
              >
                {t('model_arena.tie')}
              </Button>
              <Button
                className="model-arena-decision-button"
                data-remis-action={selection === 'reject_all' ? 'primary' : 'secondary'}
                variant={selection === 'reject_all' ? 'filled' : 'outline'}
                leftSection={<IconMoodSad size={18} />}
                aria-label={t('model_arena.reject_all')}
                aria-pressed={selection === 'reject_all'}
                onClick={() => {
                  setSelection('reject_all');
                  setReasons([]);
                }}
              >
                {t('model_arena.reject_all')}
              </Button>
            </>
          ) : (
            <Button
              className="model-arena-decision-button"
              data-remis-action={selection === 'unjudgeable' ? 'primary' : 'secondary'}
              variant={selection === 'unjudgeable' ? 'filled' : 'outline'}
              leftSection={<IconAlertCircle size={18} />}
              aria-label={t('model_arena.unjudgeable')}
              aria-pressed={selection === 'unjudgeable'}
              onClick={() => {
                setSelection('unjudgeable');
                setReasons([]);
              }}
            >
              {t('model_arena.unjudgeable')}
            </Button>
          )}
        </SimpleGrid>
      </Stack>

      {selection.startsWith('winner:') && (
        <div>
          <Text fw={700} mb="xs">{t('model_arena.reasons')}</Text>
          <Group gap="md">
            {REASONS.map((reason) => (
              <Checkbox
                key={reason}
                label={t(`model_arena.reason_${reason}`)}
                checked={reasons.includes(reason)}
                onChange={(event) => {
                  const checked = event.currentTarget.checked;
                  setReasons((current) => (
                    checked
                    ? [...current, reason]
                    : current.filter((item) => item !== reason)
                  ));
                }}
              />
            ))}
          </Group>
        </div>
      )}
      <Textarea
        label={t('model_arena.note')}
        description={t('model_arena.note_description')}
        placeholder={t('model_arena.note_placeholder')}
        value={note}
        onChange={(event) => setNote(event.currentTarget.value)}
        minRows={2}
      />

      <Group justify="space-between">
        <Button
          variant="default"
          leftSection={<IconArrowLeft size={17} />}
          disabled={activeIndex === 0}
          onClick={() => changeSample(activeIndex - 1)}
        >
          {t('model_arena.previous')}
        </Button>
        <Group>
          <Button
            rightSection={<IconArrowRight size={17} />}
            onClick={saveAndAdvance}
            loading={saving}
            disabled={!votePayload.verdict}
          >
            {activeIndex === samples.length - 1
              ? t('model_arena.save_vote')
              : t('model_arena.save_and_next')}
          </Button>
          {allVoted && (
            <Button variant="light" onClick={() => setReviewingCompletedVotes(false)}>
              {t('model_arena.back_to_reveal')}
            </Button>
          )}
        </Group>
      </Group>
      {!allVoted && (
        <Text size="xs" c="dimmed" ta="right">
          {t('model_arena.all_votes_required', { remaining: samples.length - votedCount })}
        </Text>
      )}
    </Stack>
  );
}
