export const INCREMENTAL_STATE_STORAGE_KEY = 'incremental_translation_state_v1';

export const LOCAL_PROVIDERS = ['ollama', 'lm_studio', 'vllm', 'koboldcpp', 'oobabooga', 'text-generation-webui'];

export { normalizeArrayPayload } from '../utils/payload';

export const getArchivedTargetLanguages = (info) => {
  if (!info) return [];
  if (Array.isArray(info.archived_languages)) {
    return info.archived_languages.filter(Boolean);
  }
  if (Array.isArray(info.target_languages)) {
    return info.target_languages.filter(Boolean);
  }
  return info.target_language ? [info.target_language] : [];
};

const optionalNumber = (value) => (value ? Number(value) : null);

export const buildIncrementalUpdatePayload = ({
  batchSizeLimit,
  concurrencyLimit,
  customSourcePath,
  dryRun,
  embeddedWorkshopBatchSize,
  embeddedWorkshopConcurrency,
  embeddedWorkshopEnabled,
  embeddedWorkshopFollowPrimary,
  embeddedWorkshopModel,
  embeddedWorkshopProvider,
  embeddedWorkshopRpm,
  projectId,
  referenceLocalizationPath = '',
  referenceReuseExcludedEntries = [],
  referenceReuseEnabled = true,
  rpmLimit,
  selectedModel,
  selectedProvider,
  targetLangCodes,
  useResume,
}) => ({
  project_id: projectId,
  target_lang_codes: targetLangCodes,
  dry_run: dryRun,
  api_provider: selectedProvider,
  model: selectedModel,
  batch_size_limit: optionalNumber(batchSizeLimit),
  concurrency_limit: Number(concurrencyLimit),
  rpm_limit: Number(rpmLimit),
  custom_source_path: customSourcePath,
  use_resume: useResume,
  reference_reuse: {
    enabled: referenceReuseEnabled !== false,
    localization_path: referenceLocalizationPath || '',
    excluded_entries: referenceReuseExcludedEntries,
  },
  embedded_workshop: {
    enabled: embeddedWorkshopEnabled,
    follow_primary_settings: embeddedWorkshopFollowPrimary,
    api_provider: embeddedWorkshopFollowPrimary ? null : embeddedWorkshopProvider,
    api_model: embeddedWorkshopFollowPrimary ? null : embeddedWorkshopModel,
    batch_size_limit: embeddedWorkshopFollowPrimary
      ? optionalNumber(batchSizeLimit)
      : Number(embeddedWorkshopBatchSize),
    concurrency_limit: embeddedWorkshopFollowPrimary
      ? Number(concurrencyLimit)
      : Number(embeddedWorkshopConcurrency),
    rpm_limit: embeddedWorkshopFollowPrimary
      ? Number(rpmLimit)
      : Number(embeddedWorkshopRpm),
  },
});
