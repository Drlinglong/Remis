export const SITE_BASE = '/Remis/'

export const links = {
  github: 'https://github.com/Drlinglong/Remis',
  aventine: 'https://github.com/Drlinglong/remis-aventine',
  aventineTournament: 'https://github.com/Drlinglong/remis-aventine/blob/main/docs/zh/developer/first_remis_tournament_2026-07-16.md',
  aventineJudgeComparison: 'https://github.com/Drlinglong/remis-aventine/blob/main/docs/zh/developer/judge_provider_comparison_2026-07-15.md',
  releases: 'https://github.com/Drlinglong/Remis/releases/latest',
  issue132: 'https://github.com/Drlinglong/Remis/issues/132',
  discussions: 'https://github.com/Drlinglong/Remis/discussions',
  documentation: 'https://github.com/Drlinglong/Remis/tree/main/docs',
  architecture: 'https://github.com/Drlinglong/Remis/blob/main/docs/en/developer/architecture.md',
  agentQuickstart: 'https://github.com/Drlinglong/Remis/blob/codex/build-week-remis-for-codex/docs/en/developer/agent-api-quickstart.md',
  agentSkill: 'https://github.com/Drlinglong/Remis/tree/codex/build-week-remis-for-codex/.agents/skills/remis-agent',
  agentApi: 'http://127.0.0.1:1453/docs',
  codex: 'https://chatgpt.com/codex',
}

export const pages = [
  { key: 'home', label: 'Product', path: '' },
  { key: 'codex', label: 'Use with Codex', path: 'codex/' },
  { key: 'engineering', label: 'AI Engineering', path: 'engineering/' },
  { key: 'aventine', label: 'Aventine', path: 'aventine/' },
  { key: 'guide', label: 'Beginner Guide', path: 'guide/' },
  { key: 'roadmap', label: 'Roadmap', path: 'roadmap/' },
]

export function sitePath(path = '') {
  return `${import.meta.env?.BASE_URL ?? SITE_BASE}${path}`
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
  if (segment === 'aventine') return 'aventine'
  if (segment === 'codex') return 'codex'
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
    status: 'In development',
    title: 'A contextual Copilot that knows where you are',
    body: 'The 3.0.7 branch adds session memory, route-aware help, agent-selected read tools, and persistent task handoff across the Remis interface.',
    code: 'observe → retrieve → explain → hand off',
  },
  {
    index: '03',
    eyebrow: 'AUTOMATION LAYER',
    status: 'In development',
    title: 'Approval-gated agents over native workflows',
    body: 'PydanticAI plans typed localization work, Remis validates every tool and argument, and the user approves the workflow inline before execution.',
    code: 'plan → preview → approve → execute',
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
    name: 'Contextual help and read tools',
    status: 'In development',
    description: 'The 3.0.7 branch grounds answers in the current route, packaged product guides, session history, and agent-selected read-only skills.',
  },
  {
    eyebrow: 'SCHEMA-BOUND REASONING LAYER',
    name: 'PydanticAI Copilot',
    status: 'In development',
    description: 'PydanticAI produces typed help responses and localization workflow proposals. Unknown tools, invalid arguments, and free-form executable behaviour are rejected.',
  },
  {
    eyebrow: 'DETERMINISTIC EXECUTION LAYER',
    name: 'Remis workflow engine',
    status: 'Foundation shipped',
    description: 'Owns validation, UI previews, confirmation gates, native handlers, logging, and every write to project or game directories.',
  },
]

export const agentMilestones = [
  {
    index: '01',
    title: 'A persistent Copilot surface',
    body: 'Sessions, a dedicated thread view, and a floating assistant make help continuous instead of resetting at every page.',
    evidence: 'sessions · floating widget · context budget',
  },
  {
    index: '02',
    title: 'Grounded in the live product',
    body: 'The assistant receives the current route and page context, then chooses bounded read tools for product-specific answers.',
    evidence: 'route context · read tools · packaged guides',
  },
  {
    index: '03',
    title: 'Structured work, approved inline',
    body: 'Translation requests become typed plans with visible steps. The user approves inside the conversation before Remis hands work to the native workflow.',
    evidence: 'PydanticAI · schema validation · approval gate',
  },
  {
    index: '04',
    title: 'Handoff that survives navigation',
    body: 'Workflow context and translation task state persist across the handoff, so the assistant can guide work without pretending it executed hidden actions.',
    evidence: 'session store · task handoff · regression tests',
  },
]

export const aventineProofPoints = [
  { value: '4', label: 'Real recipes', note: 'production-backed Remis artifacts in the first tournament' },
  { value: '7', label: 'Frozen cases', note: 'five translation cases and two repair cases under one contract' },
  { value: '42', label: 'Head-to-head matchups', note: 'hard-veto and position-consistent judge decisions' },
  { value: '48', label: 'Calibration cases', note: 'MQM, ACES, and Remis evidence across three judge providers' },
]

export const aventineRecipeStages = [
  {
    index: '01',
    eyebrow: 'RECIPE CONTRACT',
    title: 'The whole translation system enters the arena.',
    body: 'Provider, model revision, prompt, decoding, context, glossary, post-processing, repair, and validators are versioned as one recipe.',
    code: 'model + prompt + context + glossary + repair',
  },
  {
    index: '02',
    eyebrow: 'HARD VETO',
    title: 'Unsafe output cannot win on style points.',
    body: 'Execution, schema, and deterministic validator failures are resolved before an LLM judge sees eligible soft-quality comparisons.',
    code: 'execute → validate → veto',
  },
  {
    index: '03',
    eyebrow: 'CALIBRATED EVIDENCE',
    title: 'Human gold, metrics, and judges meet in one report.',
    body: 'MQM anchors, ACES contrastive cases, automatic metrics, and structured judges expose agreement, disagreement, and unresolved evidence.',
    code: 'gold ↔ metric ↔ judge',
  },
]

export const aventineRanking = [
  { rank: '01', recipe: 'Qwen 3.6 27B Q4_K_M', hardPass: '7/7', record: '15–1–2', unresolved: '3', result: 'Champion' },
  { rank: '02', recipe: 'Gemma 4 31B QAT Q4_0', hardPass: '7/7', record: '11–4–2', unresolved: '4', result: 'Runner-up' },
  { rank: '03', recipe: 'TranslateGemma 27B Instruct Q6_K', hardPass: '5/7', record: '4–7–2', unresolved: '6', result: 'Third' },
  { rank: '04', recipe: 'Nemotron Cascade 2 30B A3B Q4_K_M', hardPass: '1/7', record: '0–18–0', unresolved: '1', result: 'Fourth' },
]

export const aventineEvidence = [
  {
    index: '01',
    title: 'Hard validators keep authority.',
    body: 'The judge scores soft quality only. It cannot rescue structurally unsafe output.',
  },
  {
    index: '02',
    title: 'Position bias is measured, not ignored.',
    body: 'Eligible comparisons run in both A/B orders. Inconsistent judgments remain unresolved.',
  },
  {
    index: '03',
    title: 'Repair restraint is a first-class metric.',
    body: 'A recipe earns credit for fixing the error without rewriting text that was already correct.',
  },
  {
    index: '04',
    title: 'Infrastructure failures stay visible.',
    body: 'Malformed JSON, retry starvation, and request-budget exhaustion remain benchmark failures, not contestant losses.',
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

export const guideQuestions = [
  {
    question: 'Do I need to know Python?',
    answer: 'No. Use the Windows installer and the guided desktop interface. The source code is there for contributors, not as an installation requirement.',
  },
  {
    question: 'Do I need an AI API key?',
    answer: 'Usually, yes. You can use a supported cloud provider or a compatible local model. Remis stores provider configuration locally.',
  },
  {
    question: 'Why does my translation not appear in game?',
    answer: 'The most common cause is fake localization in the original mod or the wrong launcher load order. The translated mod should load after the original mod.',
  },
  {
    question: 'Will Remis replace my existing translation?',
    answer: 'Incremental workflows are designed to preserve existing work and process new text. Always review the selected mode before starting a run.',
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
    status: 'Shipped',
    title: 'Deeper quality and context systems',
    version: 'v3.0.6',
    summary: 'Project glossary binding, validation sidecars, stronger proofreading boundaries, neologism workflows, and safer recovery paths.',
  },
  {
    status: 'In development',
    title: 'Contextual, session-based Help Copilot',
    version: 'v3.0.8',
    summary: 'Route-aware help, packaged product knowledge, persistent sessions, agent-selected read tools, and a floating assistant across the app.',
  },
  {
    status: 'In development',
    title: 'Approval-gated localization workflows',
    version: 'v3.0.8',
    summary: 'PydanticAI turns user intent into typed workflow plans. Remis validates, previews, and waits for inline approval before handing off work.',
  },
  {
    status: 'Shipped',
    title: 'Translation recipe benchmark foundation',
    version: 'Aventine V0',
    summary: 'Frozen fixtures, hard vetoes, pairwise judging, metric alignment, and a recorded four-recipe Remis tournament.',
  },
  {
    status: 'Research track',
    title: 'Translation QA Copilot',
    version: 'QA agent',
    summary: 'Read-only format, terminology, parent-child context, glossary, and style assessment with evidence, confidence, and no silent mutation.',
  },
]
