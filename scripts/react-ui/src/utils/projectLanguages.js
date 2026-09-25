export function getSourceLanguageOptions(availableLanguages, isMars, marsLanguageCodes, t) {
  if (!isMars || !Array.isArray(marsLanguageCodes)) return availableLanguages;
  return availableLanguages
    .filter((language) => marsLanguageCodes.includes(language.value))
    .map((language) => ({
      ...language,
      label: language.value === 'es'
        ? t('mars_pipeline.language_es_spain', 'Spanish (Spain)')
        : language.value === 'pt-BR'
          ? t('mars_pipeline.language_pt_br', 'Portuguese (Brazil)')
          : language.label,
    }));
}

export function resolveSupportedSourceLanguage(currentCode, supportedCodes = []) {
  if (supportedCodes.includes(currentCode)) return currentCode;
  if (supportedCodes.includes('en')) return 'en';
  return supportedCodes[0] || 'en';
}
