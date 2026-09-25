export const TARGET_LANGUAGE_OPTIONS = [
    { value: 'zh-CN', label: 'Simplified Chinese (简体中文)' },
    { value: 'zh-TW', label: 'Traditional Chinese (繁體中文)' },
    { value: 'en', label: 'English' },
    { value: 'ja', label: 'Japanese (日本語)' },
    { value: 'ko', label: 'Korean (한국어)' },
    { value: 'fr', label: 'French (Français)' },
    { value: 'de', label: 'German (Deutsch)' },
    { value: 'ru', label: 'Russian (Русский)' },
    { value: 'es', label: 'Spanish (Español)' },
    { value: 'pt-BR', label: 'Portuguese (Português)' },
    { value: 'pl', label: 'Polish (Polski)' },
    { value: 'tr', label: 'Turkish (Türkçe)' },
];

const LANGUAGE_ALIASES = {
    english: 'en',
    l_english: 'en',
    chinese: 'zh-CN',
    simp_chinese: 'zh-CN',
    l_simp_chinese: 'zh-CN',
    zh: 'zh-CN',
    'zh-cn': 'zh-CN',
    zh_cn: 'zh-CN',
    pt: 'pt-BR',
    'pt-br': 'pt-BR',
    pt_br: 'pt-BR',
};

export const normalizeLanguageCode = (value) => {
    const normalized = (value || '').trim().toLowerCase();
    return LANGUAGE_ALIASES[normalized] || normalized;
};
