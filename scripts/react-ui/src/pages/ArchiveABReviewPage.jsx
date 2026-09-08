import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Badge, Card, Group, Loader, Select, Stack, Text, Title } from '@mantine/core';
import { IconShieldCheck } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import { FEATURES } from '../config/features';
import ArchiveABReviewPanel from '../components/archiveABReview/ArchiveABReviewPanel';
import archiveABReviewService from '../services/archiveABReviewService';
import styles from './ModelArenaPage.module.css';

const text = (t, key, fallback) => t(`archive_ab_review.${key}`, { defaultValue: fallback });
const errorMessage = (error, fallback) => error?.response?.data?.detail || error?.message || fallback;
const DEFAULT_FILTERS = { manifest_id: '', dataset_id: '', case_kind: '', status: 'all' };

export default function ArchiveABReviewPage() {
  const { t } = useTranslation();
  const [status, setStatus] = useState(null);
  const [data, setData] = useState({ manifests: [], cases: [], total_count: 0, reviewed_count: 0, review_summary: {} });
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const requestRef = useRef({ id: 0, controller: null });

  const loadCases = useCallback(async (nextFilters) => {
    const requestId = requestRef.current.id + 1;
    requestRef.current.controller?.abort();
    const controller = new AbortController();
    requestRef.current = { id: requestId, controller };
    setLoading(true);
    try {
      const next = await archiveABReviewService.loadCases(nextFilters, { signal: controller.signal });
      if (requestRef.current.id !== requestId) return;
      setData(next);
      setActiveIndex(0);
      setError('');
    } catch (loadError) {
      if (controller.signal.aborted || requestRef.current.id !== requestId) return;
      setError(errorMessage(loadError, text(t, 'load_error', '无法读取 benchmark review batch。')));
    } finally {
      if (requestRef.current.id === requestId) setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    let cancelled = false;
    if (!FEATURES.ENABLE_ARCHIVE_AB_REVIEW) {
      setStatus({ enabled: false, reason: text(t, 'unavailable', '该 developer-only 页面未开启。') });
      setLoading(false);
      return undefined;
    }
    archiveABReviewService.getStatus()
      .then((nextStatus) => {
        if (cancelled) return;
        setStatus(nextStatus);
        if (nextStatus.enabled) loadCases(DEFAULT_FILTERS);
        else setLoading(false);
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(errorMessage(loadError, text(t, 'unavailable', '开发者抽检入口不可用。')));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
      requestRef.current.controller?.abort();
      requestRef.current = { id: requestRef.current.id + 1, controller: null };
    };
  }, [loadCases, t]);

  const manifestOptions = useMemo(() => (
    (data.manifests || []).map((item) => ({ value: item.manifest_id, label: `${item.manifest_id} (${item.reviewable_case_count})` }))
  ), [data.manifests]);
  const datasetOptions = useMemo(() => (
    [...new Set((data.cases || []).map((item) => item.dataset_id).filter(Boolean))]
      .map((value) => ({ value, label: value }))
  ), [data.cases]);

  const submitReview = async (payload) => {
    setSaving(true);
    try {
      const result = await archiveABReviewService.submitReview(payload);
      setData((current) => ({
        ...current,
        cases: current.cases.map((item) => item.case_id === payload.case_id ? result.case : item),
        reviewed_count: Math.max(current.reviewed_count, current.cases.some((item) => item.case_id === payload.case_id && item.review) ? current.reviewed_count : current.reviewed_count + 1),
      }));
      setError('');
      return result.case;
    } catch (submitError) {
      setError(errorMessage(submitError, text(t, 'submit_error', '提交抽检记录失败。')));
      throw submitError;
    } finally {
      setSaving(false);
    }
  };

  if (!FEATURES.ENABLE_ARCHIVE_AB_REVIEW || status?.enabled === false) {
    return <Alert color="yellow">{status?.reason || text(t, 'unavailable', '该 developer-only 页面未开启。')}</Alert>;
  }

  return (
    <div className={styles.page}>
      <div className={styles.shell}>
        <Stack gap="lg">
          <div className={styles.hero}>
            <Group className={styles.heroHeader} align="flex-start">
              <IconShieldCheck className={styles.heroIcon} size={40} aria-hidden />
              <div className={styles.heroCopy}>
                <Title className={styles.heroTitle}>{text(t, 'page_title', 'Archive A/B 人工抽检')}</Title>
                <Text className={styles.heroSubtitle}>{text(t, 'page_description', 'developer-only 本地 review queue；整条事件链或 reference batch 为一个判断单位。')}</Text>
              </div>
              <Badge variant="outline">{text(t, 'developer_only', 'Developer only')}</Badge>
            </Group>
          </div>
          {error && <Alert color="red">{error}</Alert>}
          <Card className={styles.stage} withBorder radius="md" padding="lg">
            <Group grow align="end">
              <Select label={text(t, 'manifest', 'Benchmark manifest')} data={manifestOptions} value={filters.manifest_id} onChange={(value) => { const next = { ...filters, manifest_id: value || '' }; setFilters(next); loadCases(next); }} placeholder={text(t, 'manifest_placeholder', '选择结果文件')} />
              <Select label={text(t, 'dataset', 'Dataset')} data={datasetOptions} value={filters.dataset_id} onChange={(value) => { const next = { ...filters, dataset_id: value || '' }; setFilters(next); loadCases(next); }} clearable />
              <Select label={text(t, 'case_kind', 'Case kind')} data={[{ value: 'event_chain', label: 'event_chain' }, { value: 'reference_batch', label: 'reference_batch' }]} value={filters.case_kind} onChange={(value) => { const next = { ...filters, case_kind: value || '' }; setFilters(next); loadCases(next); }} clearable />
              <Select label={text(t, 'status', '状态')} data={[{ value: 'unreviewed', label: text(t, 'unreviewed', '未抽检') }, { value: 'reviewed', label: text(t, 'reviewed', '已抽检') }, { value: 'all', label: text(t, 'all', '全部') }]} value={filters.status} onChange={(value) => { const next = { ...filters, status: value || 'all' }; setFilters(next); loadCases(next); }} />
            </Group>
            <Group mt="md" gap="lg">
              <Text size="sm">{text(t, 'visible_cases', '当前案例')}: {data.total_count}</Text>
              <Text size="sm">{text(t, 'reviewed_count', '已完成')}: {data.reviewed_count}</Text>
              <Text size="sm">{text(t, 'agreement', 'Agreement')}: {data.review_summary?.human_llm_agreement_rate == null ? '—' : `${Math.round(data.review_summary.human_llm_agreement_rate * 100)}%`}</Text>
            </Group>
          </Card>
          {loading ? <Loader mx="auto" /> : (
            <Card className={styles.stage} withBorder radius="md" padding="lg">
              <ArchiveABReviewPanel t={t} cases={data.cases || []} activeIndex={activeIndex} onChangeCase={setActiveIndex} onSubmit={submitReview} saving={saving} />
            </Card>
          )}
        </Stack>
      </div>
    </div>
  );
}
