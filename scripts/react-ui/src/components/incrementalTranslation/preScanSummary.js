const toFiniteNumber = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
};

const getArchiveLanguages = (archiveInfo) => {
  if (Array.isArray(archiveInfo?.archived_languages)) {
    return archiveInfo.archived_languages.filter(Boolean);
  }
  if (Array.isArray(archiveInfo?.target_languages)) {
    return archiveInfo.target_languages.filter(Boolean);
  }
  return archiveInfo?.target_language ? [archiveInfo.target_language] : [];
};

const summarizeValues = (values) => {
  if (values.length === 0) {
    return { min: 0, max: 0, uniform: true };
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  return { min, max, uniform: min === max };
};

export const buildPreScanLanguageSummary = ({ scanResults, selectedLangs = [], archiveInfo = null }) => {
  const fileSummaries = Array.isArray(scanResults?.file_summaries) ? scanResults.file_summaries : [];
  const configuredLanguages = (Array.isArray(selectedLangs) && selectedLangs.length > 0
    ? selectedLangs
    : getArchiveLanguages(archiveInfo)).filter(Boolean);
  const summaryLanguages = fileSummaries
    .map((file) => file.target_lang)
    .filter(Boolean);
  const languages = Array.from(new Set([...configuredLanguages, ...summaryLanguages]));
  const languageCount = languages.length || 1;

  const perLanguageMap = new Map(languages.map((language) => [
    language,
    { language, total: 0, reusable: 0, dirty: 0 },
  ]));

  fileSummaries.forEach((file) => {
    const language = file.target_lang;
    if (!language) return;
    const current = perLanguageMap.get(language) || { language, total: 0, reusable: 0, dirty: 0 };
    current.total += toFiniteNumber(file.total);
    current.reusable += toFiniteNumber(file.unchanged);
    current.dirty += toFiniteNumber(file.new) + toFiniteNumber(file.changed);
    perLanguageMap.set(language, current);
  });

  let perLanguage = Array.from(perLanguageMap.values()).filter((item) => item.total > 0 || item.reusable > 0 || item.dirty > 0);
  if (perLanguage.length === 0) {
    perLanguage = [{
      language: languages[0] || 'default',
      total: toFiniteNumber(scanResults?.total),
      reusable: toFiniteNumber(scanResults?.unchanged),
      dirty: toFiniteNumber(scanResults?.new) + toFiniteNumber(scanResults?.changed),
    }];
  }

  return {
    languages,
    languageCount,
    perLanguage,
    perLanguageTotal: summarizeValues(perLanguage.map((item) => item.total)),
    perLanguageReusable: summarizeValues(perLanguage.map((item) => item.reusable)),
    perLanguageDirty: summarizeValues(perLanguage.map((item) => item.dirty)),
    aggregateTotal: toFiniteNumber(scanResults?.total),
    aggregateReusable: toFiniteNumber(scanResults?.unchanged),
    aggregateDirty: toFiniteNumber(scanResults?.new) + toFiniteNumber(scanResults?.changed),
  };
};
