export const SITE_BASE = '/Remis/'

export const links = {
  github: 'https://github.com/Drlinglong/Remis',
  releases: 'https://github.com/Drlinglong/Remis/releases/latest',
  issue132: 'https://github.com/Drlinglong/Remis/issues/132',
  discussions: 'https://github.com/Drlinglong/Remis/discussions',
  documentation: 'https://github.com/Drlinglong/Remis/tree/main/docs',
  architecture: 'https://github.com/Drlinglong/Remis/blob/main/docs/en/developer/architecture.md',
}

export const pages = [
  { key: 'home', label: 'Product', path: '' },
  { key: 'engineering', label: 'AI Engineering', path: 'engineering/' },
  { key: 'guide', label: 'Beginner Guide', path: 'guide/' },
  { key: 'roadmap', label: 'Roadmap', path: 'roadmap/' },
]

export function sitePath(path = '') {
  return `${import.meta.env.BASE_URL}${path}`
}

export function assetPath(fileName) {
  return sitePath(`assets/${fileName}`)
}

export function pageFromPath(pathname, base = SITE_BASE) {
  const normalizedBase = base.endsWith('/') ? base : `${base}/`
  const relative = pathname.startsWith(normalizedBase)
    ? pathname.slice(normalizedBase.length)
    : pathname.replace(/^\//, '')
  const segment = relative.split('/').filter(Boolean)[0] ?? ''

  if (segment === 'engineering') return 'engineering'
  if (segment === 'guide') return 'guide'
  if (segment === 'roadmap') return 'roadmap'
  if (segment === '404.html') return 'notFound'
  return segment === '' || segment === 'index.html' ? 'home' : 'notFound'
}

export const proofPoints = [
  { value: '8,000+', label: 'Workshop reach', note: 'users and subscribers reached by released localization work' },
  { value: '27', label: 'Public releases', note: 'a maintained Windows desktop product, not a one-off demo' },
  { value: '300+', label: 'Installer downloads', note: 'public GitHub release downloads across shipped versions' },
  { value: '120+', label: 'Tracked test files', note: 'backend, workflow, validation, and frontend regression coverage' },
]

export const pipeline = [
  { index: '01', name: 'Parse', detail: 'Preserve Paradox keys, variables, tags, and encoding.' },
  { index: '02', name: 'Retrieve', detail: 'Assemble glossary terms and domain context for each batch.' },
  { index: '03', name: 'Generate', detail: 'Call cloud or local models behind a provider abstraction.' },
  { index: '04', name: 'Validate', detail: 'Check structured output and game-specific formatting rules.' },
  { index: '05', name: 'Repair', detail: 'Retry failed batches and run bounded reflection-based fixes.' },
  { index: '06', name: 'Review', detail: 'Keep a human proofreading gate before final deployment.' },
]

export const productLayers = [
  {
    index: '01',
    eyebrow: 'CORE WORKFLOW',
    status: 'Shipped',
    title: 'A governed localization pipeline',
    body: 'Parsing, context assembly, generation, validation, repair, proofreading, and deployment already run as visible product stages.',
    code: 'parse → retrieve → generate → validate → repair → review',
  },
  {
    index: '02',
    eyebrow: 'KNOWLEDGE LAYER',
    status: 'Planned',
    title: 'Project memory with explicit retrieval boundaries',
    body: 'Glossaries and prior decisions supply relevant context. The planned Micro-RAG extends that pattern to product help and project-aware retrieval.',
    code: 'retrieve → rank → cite → assemble',
  },
  {
    index: '03',
    eyebrow: 'AUTOMATION LAYER',
    status: 'Planned',
    title: 'Bounded agents over native Remis workflows',
    body: 'Specialized agents may diagnose, propose, and coordinate, while schemas, validators, native handlers, and human confirmation retain authority.',
    code: 'propose → validate → confirm → execute',
  },
]

export const workflowDiagrams = [
  {
    index: '01',
    eyebrow: 'SHIPPED WORKFLOW',
    title: 'Project management keeps the whole localization system legible.',
    asset: 'project-management-workflow.svg',
    alt: 'Animated Remis project management workflow connecting project files, assets, AI services, and the central project workspace',
    input: 'A Paradox mod folder, game profile, target language, glossary bindings, and project settings.',
    state: 'Project metadata, task status, file mappings, generated assets, and deployment state.',
    model: 'AI providers participate through explicit translation and analysis tasks rather than owning the project lifecycle.',
    recovery: 'The workspace preserves task state and exposes incomplete or failed work for retry, inspection, or manual continuation.',
  },
  {
    index: '02',
    eyebrow: 'SHIPPED WORKFLOW',
    title: 'Incremental updates reuse verified work before spending another model call.',
    asset: 'incremental-update-workflow.svg',
    alt: 'Animated Remis incremental update workflow comparing source changes, translation memory, and model generation',
    input: 'A changed source mod plus an earlier translated project and its stored translation history.',
    state: 'Source identity, reusable translations, changed entries, unmatched entries, and validation outcomes.',
    model: 'The model receives only entries that cannot be safely reused, together with glossary and project context.',
    recovery: 'Ambiguous matches and failed generations remain visible for retranslation or proofreading instead of silently overwriting prior work.',
  },
  {
    index: '03',
    eyebrow: 'AGENTIC WORKFLOW',
    title: 'Smart repair closes a bounded diagnose, patch, and verify loop.',
    asset: 'agentic-repair-workflow.svg',
    alt: 'Animated Remis agentic repair workflow showing diagnostics, context assembly, repair proposals, tests, and a verification feedback loop',
    input: 'Broken localization entries, validator diagnostics, source text, glossary terms, and relevant project context.',
    state: 'The original failure, diagnostic evidence, repair attempts, validator results, and review-ready output.',
    model: 'The repair agent proposes a constrained patch from a prepared context pack. It does not receive unrestricted filesystem authority.',
    recovery: 'Every proposal is revalidated. Failed attempts loop back with diagnostics; unresolved cases stop for human review.',
  },
]

export const shippedCapabilities = [
  {
    title: 'Context-aware generation',
    label: 'Shipped',
    body: 'Glossary term extraction and prompt injection add domain context without hiding where the context came from.',
    code: 'extract → assemble → inject',
  },
  {
    title: 'Structured output contracts',
    label: 'Shipped',
    body: 'Responses pass through JSON recovery and Pydantic validation before they can enter the localization pipeline.',
    code: 'parse → type-check → reject',
  },
  {
    title: 'Retry and repair loops',
    label: 'Shipped',
    body: 'Failed batches retry with diagnostics. The repair agent remains bounded by validators and source-aware constraints.',
    code: 'diagnose → repair → revalidate',
  },
  {
    title: 'Human review and history',
    label: 'Shipped',
    body: 'Side-by-side proofreading, archives, and incremental reuse keep model output inspectable and reversible.',
    code: 'draft → compare → approve',
  },
]

export const copilotLayers = [
  {
    eyebrow: 'READ-ONLY KNOWLEDGE LAYER',
    name: 'LlamaIndex Micro-RAG',
    status: 'Planned',
    description: 'Retrieves provider setup, troubleshooting, validation explanations, and product documentation. It does not index API keys or arbitrary user mods by default.',
  },
  {
    eyebrow: 'SCHEMA-BOUND REASONING LAYER',
    name: 'PydanticAI Copilot',
    status: 'Planned',
    description: 'Returns typed answers, confidence, sources, risk classifications, and whitelisted action suggestions. Free-form executable behaviour is rejected.',
  },
  {
    eyebrow: 'DETERMINISTIC EXECUTION LAYER',
    name: 'Remis workflow engine',
    status: 'Foundation shipped',
    description: 'Owns validation, UI previews, confirmation gates, native handlers, logging, and every write to project or game directories.',
  },
]

export const benchmarkMetrics = [
  ['scan_precision', 'Are reported problems real?'],
  ['fix_success_rate', 'Does a repair pass validation?'],
  ['rescan_clear_rate', 'Does the issue stay gone after a rescan?'],
  ['manual_intervention_rate', 'How much repetitive work still reaches the user?'],
  ['cost_per_fixed_issue', 'What does one verified fix cost in time and tokens?'],
  ['time_to_clean_project', 'How long until the project reaches zero open issues?'],
]

export const guideSteps = [
  {
    number: '01',
    title: 'Install Remis',
    summary: 'Download the latest Windows installer from GitHub Releases. No command line and no Python setup are required.',
    action: 'Download the installer',
    href: links.releases,
  },
  {
    number: '02',
    title: 'Choose an AI provider',
    summary: 'Use Gemini, OpenAI, DeepSeek, OpenRouter, Ollama, LM Studio, or another supported endpoint. Your key stays on your machine.',
    action: 'Read provider setup',
    href: links.documentation,
  },
  {
    number: '03',
    title: 'Create a project',
    summary: 'Point Remis at the original mod folder, choose the game and target language, then let it map the localization files.',
    action: 'Open project documentation',
    href: links.documentation,
  },
  {
    number: '04',
    title: 'Translate and validate',
    summary: 'Remis sends text in batches, injects relevant terminology, validates the result, and reports anything that needs attention.',
    action: 'Understand the workflow',
    href: sitePath('engineering/'),
  },
  {
    number: '05',
    title: 'Proofread and deploy',
    summary: 'Review source and translated text side by side. When you are satisfied, deploy the localization mod and enable it after the original mod in the launcher.',
    action: 'Read troubleshooting',
    href: links.documentation,
  },
]

export const roadmapPhases = [
  {
    status: 'Shipped',
    title: 'Release-grade localization workflow',
    version: 'v3.0.5',
    summary: 'Project management, glossary-aware translation, validation, incremental reuse, proofreading, deployment, and Windows packaging.',
  },
  {
    status: 'In development',
    title: 'Deeper quality and context systems',
    version: 'v3.0.6',
    summary: 'Project glossary binding, validation sidecars, stronger proofreading boundaries, neologism workflows, and safer recovery paths.',
  },
  {
    status: 'Planned',
    title: 'Help Copilot with Micro-RAG',
    version: 'Copilot v1',
    summary: 'Read-only product support for provider setup, logs, fake localization, validation errors, and troubleshooting.',
  },
  {
    status: 'Planned',
    title: 'Safe suggested actions',
    version: 'Copilot v2',
    summary: 'Typed action suggestions such as opening settings or running a connection test. Remis still decides whether and how to execute.',
  },
  {
    status: 'Research track',
    title: 'Translation QA Copilot',
    version: 'QA agent',
    summary: 'Read-only format, terminology, parent-child context, glossary, and style assessment with evidence, confidence, and no silent mutation.',
  },
]
