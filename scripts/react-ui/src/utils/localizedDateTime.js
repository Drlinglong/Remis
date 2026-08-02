import i18n from '../i18n/i18n';

const SUPPORTED_INTERFACE_LOCALES = new Set([
  'de', 'en', 'es', 'fr', 'ja', 'ko', 'pl', 'pt-BR', 'ru', 'tr', 'zh-CN',
]);

const LOCALE_ALIASES = {
  pt: 'pt-BR',
  'pt-br': 'pt-BR',
  zh: 'zh-CN',
};

export const resolveInterfaceLocale = (language) => {
  const normalizedLanguage = language?.replace('_', '-').toLowerCase();
  if (!normalizedLanguage) return 'en';
  if (normalizedLanguage.startsWith('zh-')) return 'zh-CN';
  if (normalizedLanguage.startsWith('pt-')) return 'pt-BR';

  const alias = LOCALE_ALIASES[normalizedLanguage];
  if (alias) return alias;

  const baseLanguage = normalizedLanguage.split('-')[0];
  return SUPPORTED_INTERFACE_LOCALES.has(baseLanguage) ? baseLanguage : 'en';
};

export const getResolvedInterfaceLocale = (i18n) => resolveInterfaceLocale(
  i18n?.resolvedLanguage || i18n?.language,
);

export const formatLocalizedDateTime = (value, language, options) => {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return 'Invalid Date';

  return new Intl.DateTimeFormat(resolveInterfaceLocale(language), options).format(date);
};

export const formatCurrentLocalizedDateTime = (value, options) => formatLocalizedDateTime(
  value,
  getResolvedInterfaceLocale(i18n),
  options,
);
