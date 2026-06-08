import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import translationEN from './locales/en/translation.json';

const localeLoaders = {
  de: () => import('./locales/de/translation.json'),
  en: () => Promise.resolve({ default: translationEN }),
  es: () => import('./locales/es/translation.json'),
  fr: () => import('./locales/fr/translation.json'),
  ja: () => import('./locales/ja/translation.json'),
  ko: () => import('./locales/ko/translation.json'),
  pl: () => import('./locales/pl/translation.json'),
  'pt-BR': () => import('./locales/pt-BR/translation.json'),
  ru: () => import('./locales/ru/translation.json'),
  tr: () => import('./locales/tr/translation.json'),
  zh: () => import('./locales/zh/translation.json'),
  'zh-CN': () => import('./locales/zh/translation.json'),
};

const normalizeLanguage = (language) => {
  if (language === 'zh-CN' || language?.startsWith('zh-')) {
    return 'zh';
  }
  if (language === 'pt-BR') {
    return 'pt-BR';
  }
  return language?.split('-')[0] || 'en';
};

const lazyLocaleBackend = {
  type: 'backend',
  read(language, _namespace, callback) {
    const normalizedLanguage = normalizeLanguage(language);
    const loader = localeLoaders[language] || localeLoaders[normalizedLanguage] || localeLoaders.en;

    loader()
      .then((module) => callback(null, module.default || module))
      .catch((error) => callback(error, false));
  },
};

i18n
  .use(lazyLocaleBackend)
  .use(LanguageDetector) // 探测浏览器语言
  .use(initReactI18next) // 将 i18n 实例传递给 react-i18next
  .init({
    resources: {
      en: {
        translation: translationEN,
      },
    },
    supportedLngs: Object.keys(localeLoaders),
    fallbackLng: 'en', // 如果当前语言没有对应的翻译，则使用英文
    partialBundledLanguages: true,
    interpolation: {
      escapeValue: false, // React已经可以防范XSS
    },
  });

export default i18n;
