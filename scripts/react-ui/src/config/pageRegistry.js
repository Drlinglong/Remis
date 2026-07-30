export const PAGE_DOMAINS = Object.freeze({
  HOME: 'home',
  PROJECTS: 'projects',
  TRANSLATION: 'translation',
  QUALITY: 'quality',
  TASKS: 'tasks',
  TOOLS: 'tools',
  ASSISTANT: 'assistant',
  SETTINGS: 'settings',
  INTERNAL: 'internal',
});

export const ENTRY_MODES = Object.freeze({
  PRIMARY: 'primary',
  CONTEXTUAL: 'contextual',
  GLOBAL: 'global',
  HIDDEN: 'hidden',
});

export const PAGE_REGISTRY = Object.freeze([
  {
    id: 'home',
    routePaths: ['/'],
    match: /^\/$/,
    domain: PAGE_DOMAINS.HOME,
    navigation: { entryMode: ENTRY_MODES.PRIMARY, section: 'home', label: 'page_title_home', icon: 'home', order: 0 },
    tutorialContext: 'home',
    guide: 'docs/zh/user-guides/getting-started.md',
    copilot: { pageName: '主页 / Home', helpSkillId: 'getting_started' },
  },
  {
    id: 'project-management',
    routePaths: ['/project-management', '/project-management/:projectId'],
    match: /^\/project-management(?:\/[^/]+)?$/,
    domain: PAGE_DOMAINS.PROJECTS,
    navigation: { entryMode: ENTRY_MODES.PRIMARY, section: 'projects', label: 'page_title_project_management', icon: 'briefcase', order: 10 },
    tutorialContext: 'project-management',
    guide: 'docs/zh/user-guides/getting-started.md',
    copilot: { pageName: '项目管理 / Project Management', helpSkillId: 'getting_started' },
  },
  {
    id: 'project-tracking',
    routePaths: ['/project-tracking'],
    match: /^\/project-tracking$/,
    domain: PAGE_DOMAINS.PROJECTS,
    navigation: { entryMode: ENTRY_MODES.PRIMARY, section: 'projects', label: 'nav_mod_monitor', icon: 'radar', order: 20 },
    tutorialContext: 'project-tracking',
    guide: 'docs/zh/user-guides/project-tracking.md',
    copilot: { pageName: '项目追踪 / Project Tracking', helpSkillId: 'project_tracking' },
  },
  {
    id: 'initial-translation',
    routePaths: ['/translation'],
    match: /^\/translation$/,
    domain: PAGE_DOMAINS.TRANSLATION,
    navigation: { entryMode: ENTRY_MODES.PRIMARY, section: 'translation', label: 'page_title_translation', icon: 'language', order: 10 },
    tutorialContext: 'initial-translation-step-0',
    guide: 'docs/zh/user-guides/getting-started.md',
    copilot: { pageName: '初次翻译 / Initial Translation', helpSkillId: 'getting_started' },
  },
  {
    id: 'incremental-translation',
    routePaths: ['/incremental-translation'],
    match: /^\/incremental-translation$/,
    domain: PAGE_DOMAINS.TRANSLATION,
    enabledBy: 'ENABLE_INCREMENTAL_TRANSLATION',
    navigation: { entryMode: ENTRY_MODES.PRIMARY, section: 'translation', label: 'incremental_translation.title', icon: 'rocket', order: 20 },
    tutorialContext: 'incremental-translation-step-0',
    guide: 'docs/zh/user-guides/incremental-update.md',
    copilot: { pageName: '增量翻译 / Incremental Translation', helpSkillId: 'incremental_translation' },
  },
  {
    id: 'model-arena',
    routePaths: ['/model-arena'],
    match: /^\/model-arena$/,
    domain: PAGE_DOMAINS.TRANSLATION,
    navigation: { entryMode: ENTRY_MODES.PRIMARY, section: 'translation', label: 'page_title_model_arena', icon: 'trophy', order: 30 },
    guide: 'docs/zh/user-guides/model-arena.md',
    copilot: { pageName: '模型竞技场 / Model Arena', helpSkillId: 'model_arena' },
  },
  {
    id: 'proofreading',
    routePaths: ['/proofreading'],
    match: /^\/proofreading$/,
    domain: PAGE_DOMAINS.QUALITY,
    navigation: { entryMode: ENTRY_MODES.PRIMARY, section: 'quality', label: 'page_title_proofreading', icon: 'checklist', order: 10 },
    tutorialContext: 'proofreading',
    guide: 'docs/zh/user-guides/proofreading.md',
    copilot: { pageName: '校对 / Proofreading', helpSkillId: 'proofreading' },
  },
  {
    id: 'glossary-manager',
    routePaths: ['/glossary-manager'],
    match: /^\/glossary-manager$/,
    domain: PAGE_DOMAINS.QUALITY,
    navigation: { entryMode: ENTRY_MODES.PRIMARY, section: 'quality', label: 'page_title_glossary_manager', icon: 'vocabulary', order: 20 },
    tutorialContext: 'glossary-manager',
    guide: 'docs/zh/user-guides/glossary.md',
    copilot: { pageName: '词典管理 / Glossary Manager', helpSkillId: 'glossary' },
  },
  {
    id: 'neologism-review',
    routePaths: ['/neologism-review'],
    match: /^\/neologism-review$/,
    domain: PAGE_DOMAINS.QUALITY,
    enabledBy: 'ENABLE_NEOLOGISM_TRIBUNAL',
    navigation: { entryMode: ENTRY_MODES.PRIMARY, section: 'quality', label: 'neologism_review.title', icon: 'sparkles', order: 30 },
    tutorialContext: 'neologism-mining',
    guide: 'docs/zh/user-guides/neologism-tribunal.md',
    copilot: { pageName: '术语法庭 / Neologism Tribunal', helpSkillId: 'neologism_tribunal' },
  },
  {
    id: 'agent-workshop',
    routePaths: ['/agent-workshop'],
    match: /^\/agent-workshop$/,
    domain: PAGE_DOMAINS.QUALITY,
    enabledBy: 'ENABLE_AGENT_WORKSHOP',
    navigation: { entryMode: ENTRY_MODES.PRIMARY, section: 'quality', label: 'page_title_agent_workshop', icon: 'robot', order: 40 },
    tutorialContext: 'agent-workshop-step-0',
    guide: 'docs/zh/user-guides/agent-workshop.md',
    copilot: { pageName: '格式修复台 / Format Repair', helpSkillId: 'agent_workshop' },
  },
  {
    id: 'task-history',
    routePaths: ['/task-history'],
    match: /^\/task-history$/,
    domain: PAGE_DOMAINS.TASKS,
    navigation: { entryMode: ENTRY_MODES.CONTEXTUAL },
    tutorialContext: 'task-history',
    copilot: { pageName: '任务日志 / Task History', helpSkillId: 'task_center' },
  },
  {
    id: 'task-detail',
    routePaths: ['/tasks/:taskId'],
    match: /^\/tasks\/[^/]+$/,
    domain: PAGE_DOMAINS.TASKS,
    navigation: { entryMode: ENTRY_MODES.CONTEXTUAL },
    tutorialContext: 'task-detail',
    copilot: { pageName: '任务详情 / Task Detail', helpSkillId: 'task_center' },
  },
  {
    id: 'glossary-health-review',
    routePaths: ['/tasks/:taskId/glossary-health'],
    match: /^\/tasks\/[^/]+\/glossary-health$/,
    domain: PAGE_DOMAINS.QUALITY,
    navigation: { entryMode: ENTRY_MODES.CONTEXTUAL },
    tutorialContext: 'glossary-health-review',
    copilot: { pageName: '词典巡检 / Glossary Health Review', helpSkillId: 'glossary' },
  },
  {
    id: 'tools',
    routePaths: ['/tools'],
    match: /^\/tools$/,
    domain: PAGE_DOMAINS.TOOLS,
    navigation: { entryMode: ENTRY_MODES.PRIMARY, section: 'tools', label: 'page_title_tools', icon: 'tools', order: 0 },
    tutorialContext: 'tools',
    guide: 'docs/zh/user-guides/tools-thumbnail-generator.md',
    copilot: { pageName: '工具箱 / Tools', helpSkillId: 'thumbnail_generator' },
  },
  {
    id: 'settings',
    routePaths: ['/settings'],
    match: /^\/settings$/,
    domain: PAGE_DOMAINS.SETTINGS,
    navigation: { entryMode: ENTRY_MODES.PRIMARY, section: 'settings', label: 'page_title_settings', icon: 'settings', order: 0 },
    tutorialContext: 'settings',
    guide: 'docs/zh/user-guides/settings.md',
    copilot: { pageName: '设置 / Settings', helpSkillId: 'settings' },
  },
  {
    id: 'documentation',
    routePaths: ['/docs'],
    match: /^\/docs$/,
    domain: PAGE_DOMAINS.TOOLS,
    enabledBy: 'ENABLE_DOCS',
    navigation: { entryMode: ENTRY_MODES.PRIMARY, section: 'documentation', label: 'page_title_docs', icon: 'book', order: 0 },
    copilot: { pageName: '使用文档 / Documentation', helpSkillId: 'faq' },
  },
  {
    id: 'copilot',
    routePaths: ['/copilot'],
    match: /^\/copilot$/,
    domain: PAGE_DOMAINS.ASSISTANT,
    enabledBy: 'ENABLE_REMIS_COPILOT',
    navigation: { entryMode: ENTRY_MODES.GLOBAL },
    copilot: { pageName: 'Remis 小助手 / Copilot', helpSkillId: 'remis_assistant' },
  },
  {
    id: 'archives',
    routePaths: ['/archives'],
    match: /^\/archives$/,
    domain: PAGE_DOMAINS.PROJECTS,
    navigation: { entryMode: ENTRY_MODES.CONTEXTUAL },
    copilot: { pageName: '归档 / Archives', helpSkillId: 'project_tracking' },
  },
  {
    id: 'cicd',
    routePaths: ['/cicd'],
    match: /^\/cicd$/,
    domain: PAGE_DOMAINS.INTERNAL,
    navigation: { entryMode: ENTRY_MODES.HIDDEN },
    copilot: { pageName: 'CI/CD', helpSkillId: 'faq' },
  },
  {
    id: 'under-development',
    routePaths: ['/under-development'],
    match: /^\/under-development$/,
    domain: PAGE_DOMAINS.INTERNAL,
    navigation: { entryMode: ENTRY_MODES.HIDDEN },
  },
  {
    id: 'under-construction',
    routePaths: ['/under-construction'],
    match: /^\/under-construction$/,
    domain: PAGE_DOMAINS.INTERNAL,
    navigation: { entryMode: ENTRY_MODES.HIDDEN },
  },
  {
    id: 'in-conception',
    routePaths: ['/in-conception'],
    match: /^\/in-conception$/,
    domain: PAGE_DOMAINS.INTERNAL,
    navigation: { entryMode: ENTRY_MODES.HIDDEN },
  },
]);

export const NAVIGATION_SECTIONS = Object.freeze([
  { id: 'home', type: 'link', pageIds: ['home'] },
  { id: 'projects', type: 'menu', label: 'nav_projects', icon: 'briefcase', pageIds: ['project-management', 'project-tracking'] },
  { id: 'translation', type: 'menu', label: 'nav_translation_workflow', icon: 'language', pageIds: ['initial-translation', 'incremental-translation', 'model-arena'] },
  { id: 'quality', type: 'menu', label: 'nav_quality_terminology', icon: 'shield-check', pageIds: ['proofreading', 'glossary-manager', 'neologism-review', 'agent-workshop'] },
  { id: 'task-center', type: 'task-center', pageIds: [] },
  { id: 'tools', type: 'link', pageIds: ['tools'] },
]);

export function isPageEnabled(page, features) {
  return !page.enabledBy || Boolean(features[page.enabledBy]);
}

export function getPageById(pageId) {
  return PAGE_REGISTRY.find((page) => page.id === pageId) || null;
}

export function getNavigationSections(features) {
  return NAVIGATION_SECTIONS.map((section) => ({
    ...section,
    pages: section.pageIds
      .map(getPageById)
      .filter((page) => page && isPageEnabled(page, features))
      .sort((left, right) => (left.navigation?.order || 0) - (right.navigation?.order || 0)),
  }));
}

export function buildAppRouteConfig(pageElements, features) {
  return PAGE_REGISTRY
    .filter((page) => isPageEnabled(page, features))
    .flatMap((page) => page.routePaths.map((path) => ({
      path,
      element: pageElements[page.id],
    })));
}

export function resolveRegisteredPage(pathname) {
  const normalizedPath = pathname || '/';
  return PAGE_REGISTRY.find((page) => page.match?.test(normalizedPath)) || null;
}
