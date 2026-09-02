import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Code,
  Group,
  NumberInput,
  Progress,
  SimpleGrid,
  Slider,
  Stack,
  Text,
  Textarea,
  Title,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconArrowLeft,
  IconArrowRight,
  IconCheck,
  IconEqual,
  IconEye,
  IconLock,
  IconPlayerSkipForward,
  IconQuestionMark,
  IconThumbUp,
} from '@tabler/icons-react';

const ERROR_TAGS = [
  'wrong_referent',
  'broken_causality',
  'inconsistent_entity',
  'branch_misread',
  'missing_story_context',
  'invented_information',
  'terminology_inconsistency',
  'fluency_problem',
];

const label = (t, key, fallback, values = {}) => t(`archive_ab_review.${key}`, { ...values, defaultValue: fallback });

const WRAPPED_CODE_STYLE = {
  whiteSpace: 'pre-wrap',
  overflowWrap: 'anywhere',
  wordBreak: 'break-word',
  maxWidth: '100%',
};

const emptyResultCounts = () => ({ archive: 0, control: 0, tie: 0, uncertain: 0, skip: 0 });

const countResults = (cases) => cases.reduce((counts, item) => {
  const selection = item.review?.selection;
  if (['tie', 'uncertain', 'skip'].includes(selection)) {
    counts[selection] += 1;
    return counts;
  }
  const condition = item.reveal?.semantic_identity?.[selection]?.condition;
  if (condition === 'archive_enabled') counts.archive += 1;
  if (condition === 'control_without_archive') counts.control += 1;
  return counts;
}, emptyResultCounts());

const sameReview = (item, selection, errorTags, confidence, note) => {
  const review = item?.review;
  if (!review || review.selection !== selection) return false;
  if (Number(review.confidence ?? 0.5) !== Number(confidence)) return false;
  if ((review.note || '') !== note.trim()) return false;
  const savedTags = [...(review.error_tags || [])].sort();
  const nextTags = [...errorTags].sort();
  return savedTags.length === nextTags.length && savedTags.every((tag, index) => tag === nextTags[index]);
};

export default function ArchiveABReviewPanel({ t, cases, activeIndex, onChangeCase, onSubmit, saving }) {
  const item = cases[activeIndex];
  const [selection, setSelection] = useState('');
  const [errorTags, setErrorTags] = useState([]);
  const [confidence, setConfidence] = useState(0.5);
  const [note, setNote] = useState('');
  const [batchRevealed, setBatchRevealed] = useState(false);
  const caseHeadingRef = useRef(null);
  const revealRef = useRef(null);

  useEffect(() => {
    const review = item?.review;
    setSelection(review?.selection || '');
    setErrorTags(review?.error_tags || []);
    setConfidence(Number(review?.confidence ?? 0.5));
    setNote(review?.note || '');
  }, [item]);

  useEffect(() => {
    const target = batchRevealed && item?.revealed ? revealRef.current : caseHeadingRef.current;
    if (target) target.focus();
  }, [batchRevealed, item?.case_id, item?.revealed]);

  const canSubmit = Boolean(item && selection);
  const sourceCount = item?.source_entries?.length || 0;
  const progress = cases.length ? ((activeIndex + 1) / cases.length) * 100 : 0;
  const reveal = batchRevealed && item?.revealed ? item.reveal : null;
  const outputCards = useMemo(() => item?.anonymous_outputs || [], [item]);
  const resultCounts = useMemo(() => countResults(cases), [cases]);
  const isLastCase = activeIndex === cases.length - 1;

  if (!item) {
    return <Alert color="yellow">{label(t, 'no_cases', '当前筛选没有可抽检案例。')}</Alert>;
  }

  const submit = async (nextSelection = selection) => {
    if (!nextSelection) return;
    if (sameReview(item, nextSelection, errorTags, confidence, note)) return item;
    return onSubmit({
      manifest_id: item.manifest_id,
      case_id: item.case_id,
      selection: nextSelection,
      error_tags: errorTags,
      confidence,
      note: note.trim(),
    });
  };

  const saveAndContinue = async () => {
    await submit();
    onChangeCase(activeIndex + 1);
  };

  const saveAndGoBack = async () => {
    if (selection) await submit();
    onChangeCase(activeIndex - 1);
  };

  const finishAndReveal = async () => {
    await submit();
    setBatchRevealed(true);
  };

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <div>
          <Title order={3}>{label(t, 'review_title', '整链人工抽检')}</Title>
          <Text c="dimmed">{label(t, 'review_description', '先盲评左右候选，提交后才显示模型竞技场与 Luna 判定。')}</Text>
        </div>
        <Badge size="lg" variant="light">
          {label(t, 'case_progress', `案例 ${activeIndex + 1} / ${cases.length}`, { current: activeIndex + 1, total: cases.length })}
        </Badge>
      </Group>
      <Progress value={progress} aria-label={label(t, 'progress', '抽检进度')} />
      <Alert icon={<IconLock size={18} />} color="blue" variant="light">
        {label(t, 'identity_hidden', '提交前不显示 A/B arm、模型身份或 Luna 结论。请按完整事件链判断。')}
      </Alert>

      <Card data-remis-surface="paper" withBorder radius="md" padding="lg">
        <Group justify="space-between" mb="md">
          <div>
            <Badge variant="outline">{item.case_kind}</Badge>
            <Title ref={caseHeadingRef} tabIndex={-1} aria-live="polite" order={4} mt="xs" data-testid="archive-ab-case-title">
              {item.chain_id || item.reference_batch_id || item.case_id}
            </Title>
          </div>
          <Text size="sm" c="dimmed">{sourceCount} {label(t, 'source_entries', '条原文')}</Text>
        </Group>
        <Stack gap="xs">
          {item.source_entries.map((entry) => (
            <Code block key={entry.source_id} style={WRAPPED_CODE_STYLE} data-testid="archive-ab-wrapped-code">
              {entry.source_id}: {entry.text}
            </Code>
          ))}
        </Stack>
      </Card>

      <Card data-remis-surface="paper" withBorder radius="md" padding="lg">
        <Group gap="xs" mb="xs"><IconEye size={18} /><Text fw={700}>{label(t, 'story_facts', '故事事实')}</Text></Group>
        <Stack gap={4}>
          {(item.story_facts || []).map((fact) => <Text key={fact} size="sm">• {fact}</Text>)}
        </Stack>
      </Card>

      <div style={{ maxHeight: '34rem', overflowY: 'auto', overflowX: 'hidden' }} data-testid="archive-ab-candidate-viewport">
        <SimpleGrid cols={{ base: 1, md: 2 }}>
          {outputCards.map((output) => {
          const selected = selection === output.anonymous_label;
          return (
            <Card
              key={output.anonymous_label}
              className="model-arena-choice-card"
              data-remis-surface="paper"
              data-selected={selected || undefined}
              withBorder
              radius="md"
              padding="lg"
            >
              <Stack justify="space-between" h="100%">
                <div>
                  <Badge variant="filled" color="gray" mb="md">{output.anonymous_label}</Badge>
                  <Stack gap="xs">
                    {(output.entries || []).map((entry) => (
                      <Code block key={entry.source_id} style={WRAPPED_CODE_STYLE} data-testid="archive-ab-wrapped-code">
                        {entry.source_id}: {entry.text}
                      </Code>
                    ))}
                  </Stack>
                </div>
                <Button
                  className="model-arena-decision-button"
                  data-remis-action={selected ? 'paper-primary' : 'paper-secondary'}
                  variant={selected ? 'filled' : 'outline'}
                  leftSection={<IconThumbUp size={17} />}
                  aria-pressed={selected}
                  fullWidth
                  onClick={() => setSelection(output.anonymous_label)}
                >
                  {label(t, 'choose', `选择 ${output.anonymous_label}`, { side: output.anonymous_label })}
                </Button>
              </Stack>
            </Card>
          );
          })}
        </SimpleGrid>
      </div>

      <SimpleGrid cols={{ base: 1, sm: 4 }}>
        {[
          ['tie', <IconEqual size={18} />, label(t, 'tie', '平局')],
          ['uncertain', <IconQuestionMark size={18} />, label(t, 'uncertain', '无法判断')],
          ['skip', <IconPlayerSkipForward size={18} />, label(t, 'skip', '跳过')],
        ].map(([value, icon, text]) => (
          <Button
            key={value}
            className="model-arena-decision-button"
            data-remis-action={selection === value ? 'primary' : 'secondary'}
            variant={selection === value ? 'filled' : 'outline'}
            leftSection={icon}
            aria-pressed={selection === value}
            onClick={() => setSelection(value)}
          >
            {text}
          </Button>
        ))}
        <Button
          className="model-arena-decision-button"
          data-remis-action="secondary"
          variant="outline"
          leftSection={<IconAlertTriangle size={18} />}
          onClick={() => setErrorTags(ERROR_TAGS)}
        >
          {label(t, 'mark_all_errors', '标记错误')}</Button>
      </SimpleGrid>

      <Card data-remis-surface="paper" withBorder radius="md" padding="lg">
        <Stack gap="md">
          <Text fw={700}>{label(t, 'evidence_title', '审查证据')}</Text>
          <Checkbox.Group value={errorTags} onChange={setErrorTags} label={label(t, 'error_tags', '错误标签')}>
            <SimpleGrid cols={{ base: 1, sm: 2 }} mt="xs">
              {ERROR_TAGS.map((tag) => <Checkbox key={tag} value={tag} label={label(t, `error_${tag}`, tag)} />)}
            </SimpleGrid>
          </Checkbox.Group>
          <Group align="flex-end">
            <div style={{ flex: 1 }}>
              <Text size="sm" fw={600}>{label(t, 'confidence', '置信度')} {Math.round(confidence * 100)}%</Text>
              <Slider value={confidence} onChange={setConfidence} min={0} max={1} step={0.05} mt="xs" aria-label={label(t, 'confidence', '置信度')} />
            </div>
            <NumberInput value={Math.round(confidence * 100)} onChange={(value) => setConfidence(Math.max(0, Math.min(100, Number(value) || 0)) / 100)} min={0} max={100} suffix="%" w={90} aria-label={label(t, 'confidence', '置信度')} />
          </Group>
          <Textarea value={note} onChange={(event) => setNote(event.currentTarget.value)} label={label(t, 'note', '备注')} placeholder={label(t, 'note_placeholder', '记录整链级判断依据')} autosize minRows={3} />
        </Stack>
      </Card>

      {reveal && (
        <Alert ref={revealRef} tabIndex={-1} aria-live="polite" data-testid="archive-ab-reveal" icon={<IconCheck size={18} />} color="green" title={label(t, 'revealed_title', '已提交并 reveal')}>
          {label(t, 'revealed_order', '实际顺序')}: {reveal.actual_order?.join(' → ')} · {label(t, 'luna_winner', 'Luna 判定')}: {reveal.llm_winner}
          {reveal.semantic_identity && (
            <Stack gap={2} mt="xs">
              {['left', 'right'].map((side) => (
                <Text size="sm" key={side}>
                  {label(t, `reveal_${side}`, side)}: {reveal.semantic_identity[side]?.label || label(t, 'reveal_identity_unknown', 'unknown')}
                </Text>
              ))}
            </Stack>
          )}
          {reveal.llm_evidence?.length ? <Text size="sm" mt="xs">{reveal.llm_evidence.join(' ')}</Text> : null}
        </Alert>
      )}

      {batchRevealed && (
        <Alert color="green" title={label(t, 'batch_result_title', '本轮最终结果')} data-testid="archive-ab-batch-result">
          {label(t, 'archive_votes', '使用项目档案')}: {resultCounts.archive} · {' '}
          {label(t, 'control_votes', '不使用项目档案')}: {resultCounts.control} · {' '}
          {label(t, 'tie', '平局')}: {resultCounts.tie} · {' '}
          {label(t, 'uncertain', '无法判断')}: {resultCounts.uncertain} · {' '}
          {label(t, 'skip', '跳过')}: {resultCounts.skip}
        </Alert>
      )}

      <Group justify="space-between">
        <Button variant="default" leftSection={<IconArrowLeft size={17} />} disabled={activeIndex === 0 || saving} onClick={saveAndGoBack}>
          {label(t, 'previous', '上一条')}
        </Button>
        <Group>
          {!isLastCase && (
            <Button data-remis-action="paper-primary" disabled={!canSubmit} loading={saving} rightSection={<IconArrowRight size={17} />} onClick={saveAndContinue}>
              {label(t, 'save_next', '保存并下一条')}
            </Button>
          )}
          {isLastCase && (
            <Button data-remis-action="paper-primary" disabled={!canSubmit} loading={saving} rightSection={<IconEye size={17} />} onClick={finishAndReveal}>
              {label(t, 'submit_all_reveal', '提交全部并查看结果')}
            </Button>
          )}
        </Group>
      </Group>
    </Stack>
  );
}

export { ERROR_TAGS };
