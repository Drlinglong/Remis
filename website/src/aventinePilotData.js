import aggregate from './aventinePilotAggregate.json'
import anchoredPlacement from './aventineAnchoredPlacement.json'

const HARD_TASKS_PER_RECIPE = aggregate.sample_design.hard_cases_per_profile
const PAIRWISE_DECISIONS_PER_RECIPE = 56

const displayProfiles = {
  gemini36: {
    shortName: 'Gemini 3.6 Flash',
    vendor: 'Google',
    vendorId: 'google',
    vendorMark: 'G',
    color: '#4285f4',
    costUsd: 0.41429,
    style: {
      en: 'The most complete pilot result: it leads blind preference while preserving a perfect hard-validation record. Quality is excellent; Standard-tier inference cost is the obvious trade-off.',
      zh: '本轮最完整的表现：盲裁偏好第一，同时保持满分硬校验。质量非常优秀，但 Standard 计价下的推理成本是最明显的代价。',
    },
  },
  hy3: {
    shortName: 'HY3',
    vendor: 'Tencent',
    vendorId: 'tencent',
    vendorMark: 'T',
    color: '#18a999',
    costUsd: 0.05295,
    style: {
      en: 'Frequently preferred by the language judge and capable of strong prose, but less stable on hard constraints. Its extreme wall-clock time makes the recipe difficult to recommend operationally.',
      zh: '语言裁判经常偏好它，说明行文能力很强，但硬约束稳定性稍弱。极端的端到端耗时让这套 recipe 很难直接作为部署首选。',
    },
  },
  deepseek: {
    shortName: 'DeepSeek V4 Flash',
    vendor: 'DeepSeek',
    vendorId: 'deepseek',
    vendorMark: 'D',
    color: '#4d6bfe',
    costUsd: 0.02630,
    style: {
      en: 'A strong instruction follower with better hard reliability than Luna. It reaches the same quality tier, but spends substantially more output and reasoning tokens to get there.',
      zh: '后训练与指令遵循表现扎实，硬可靠性高于 Luna。质量进入同一梯队，但为了达到这个结果消耗了明显更多的输出与推理 Tokens。',
    },
  },
  luna: {
    shortName: 'GPT-5.6 Luna',
    vendor: 'OpenAI',
    vendorId: 'openai',
    vendorMark: 'O',
    color: '#ece9e2',
    costUsd: 0.01066,
    style: {
      en: 'The clearest token-efficiency result in the pilot. Luna stays in the leading quality tier while using restrained reasoning, finishing second-fastest, and costing roughly one cent for all three runs.',
      zh: '本轮最清晰的 Token 效率样本。Luna 以克制推理留在第一梯队，同时完成速度第二快，三轮参赛推理成本约一美分。',
    },
  },
  gemini35: {
    shortName: 'Gemini 3.5 Lite',
    vendor: 'Google',
    vendorId: 'google',
    vendorMark: 'G',
    color: '#a676ff',
    costUsd: 0.13985,
    style: {
      en: 'Fast and competitive, but less reliable under the frozen contract than Gemini 3.6 Flash. Its quality remains respectable while its list-price cost lands well above Luna and DeepSeek.',
      zh: '速度快、总体有竞争力，但在冻结约束下不如 Gemini 3.6 Flash 稳定。质量仍然可观，不过标准价成本明显高于 Luna 与 DeepSeek。',
    },
  },
  gemma4: {
    shortName: 'Gemma 4 31B',
    vendor: 'Google',
    vendorId: 'google',
    vendorMark: 'G',
    color: '#34a853',
    costUsd: null,
    costKind: 'free-tier',
    style: {
      en: 'Engineering-safe but stylistically conservative. It passes every hard sample, yet loses most resolved language-quality comparisons to the upper tier.',
      zh: '工程安全性很强，但语言风格偏保守。所有硬样本全部通过，然而在已解决的语言质量对局中大多输给上位梯队。',
    },
  },
  nemotron: {
    shortName: 'Nemotron 3 Ultra',
    vendor: 'NVIDIA',
    vendorId: 'nvidia',
    vendorMark: 'N',
    color: '#76b900',
    costUsd: null,
    costKind: 'free-tier',
    style: {
      en: 'Structurally impeccable across five earlier stability runs and all three formal runs, but the blind judge consistently prefers more expressive alternatives. The engineering model does not win the poetry contest.',
      zh: '此前五轮稳定性测试和本次三轮正式测试的结构表现都无可挑剔，但盲裁持续偏好更有表现力的译文。卖显卡的工程模型没有赢下吟诗作对。',
    },
  },
  ling: {
    shortName: 'Ling 3.0 Flash',
    vendor: 'InclusionAI',
    vendorId: 'inclusionai',
    vendorMark: 'L',
    color: '#f2a541',
    costUsd: null,
    costKind: 'free-tier',
    style: {
      en: 'Usually respects the output contract, but produces the lowest decision coverage in the field. More of its comparisons remain unresolved or excluded by hard gates.',
      zh: '通常能够服从输出契约，但有效裁决覆盖率为全场最低；更多对局因未决或硬闸门而无法进入语言偏好统计。',
    },
  },
  mimo: {
    shortName: 'MiMo V2.5',
    vendor: 'Xiaomi',
    vendorId: 'xiaomi',
    vendorMark: 'M',
    color: '#ff6d3a',
    costUsd: 0.00795,
    style: {
      en: 'The least expensive paid recipe in the pilot and generally format-safe, but it finishes last on resolved language preference. A useful budget baseline rather than a quality leader.',
      zh: '本轮最便宜的付费 recipe，格式安全性也不错，但在有效语言偏好中排名最后。它更适合作为预算基线，而不是质量冠军。',
    },
  },
  qwen37: {
    shortName: 'Qwen 3.7 Plus',
    vendor: 'Qwen / Alibaba Cloud',
    vendorId: 'alibaba',
    vendorMark: 'Q',
    color: '#ff9f1c',
    costUsd: 0.06359,
    style: {
      en: 'Quality lands close to Luna and DeepSeek in the anchored placement, and it clearly beats the low anchor. The trade-off is older, less attractive pricing plus long high-reasoning traces that make it slower and more expensive.',
      zh: '锚点 placement 中的质量接近 Luna 与 DeepSeek，也明显胜过低位锚点。代价是较旧、吸引力稍弱的价格，以及很长的 high reasoning 轨迹，让它更慢也更贵。',
    },
  },
  translategemma: {
    shortName: 'TranslateGemma 27B',
    vendor: 'Google Translate',
    vendorId: 'google',
    vendorMark: 'G',
    color: '#fbbc04',
    costUsd: null,
    costKind: 'local-hardware',
    usageUnavailable: true,
    style: {
      en: 'A remarkably fast 27B translation specialist with appealing prose, but the generic Remis recipe exposes frequent formatting and glossary failures. The native result is preserved without model-specific rescue.',
      zh: '这是一位速度惊人的 27B 翻译专用模型，语言风格可圈可点，但通用 Remis recipe 暴露出频繁的格式与词典失败。本结果保留原生表现，没有为它安排模型专属补救。',
    },
  },
}

function round(value, digits = 1) {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

function buildRecipe(entry, sourceAggregate, anchored = false) {
  const display = displayProfiles[entry.profile_id]
  const usage = entry.telemetry.usage
  const resolved = entry.soft_preference.resolved_count
  const costPer100 = display.costUsd === null
    ? null
    : (display.costUsd / HARD_TASKS_PER_RECIPE) * 100

  return {
    ...display,
    id: entry.profile_id,
    sourceRank: entry.rank,
    label: entry.label,
    model: display.shortName,
    modelId: entry.model_id,
    provider: entry.provider,
    reasoning: entry.reasoning_label,
    recipeId: entry.recipe_id,
    aggregateId: sourceAggregate.aggregate_id,
    scoreVersion: entry.score.score_version,
    placementStatus: anchored ? entry.soft_preference.status : 'complete',
    anchoredPlacement: anchored,
    score: entry.score.score,
    softPreference: round(entry.soft_preference.value * 100),
    winRate: round((entry.soft_preference.wins / resolved) * 100),
    hardReliability: round(entry.hard_reliability.value * 100),
    coverage: entry.soft_preference.coverage.coverage_percent,
    wins: entry.soft_preference.wins,
    losses: entry.soft_preference.losses,
    ties: entry.soft_preference.ties,
    unresolved: entry.soft_preference.unresolved_count
      ?? (PAIRWISE_DECISIONS_PER_RECIPE - resolved),
    hardPass: entry.hard_reliability.hard_pass_count,
    hardSamples: entry.hard_reliability.sample_count,
    elapsedSeconds: entry.telemetry.elapsed_seconds,
    tasksPerHour: round((HARD_TASKS_PER_RECIPE / entry.telemetry.elapsed_seconds) * 3600),
    costPer100: costPer100 === null ? null : round(costPer100, 3),
    inputTokens: display.usageUnavailable ? null : usage.input_tokens,
    outputTokens: display.usageUnavailable ? null : usage.output_tokens,
    reasoningTokens: display.usageUnavailable ? null : usage.reasoning_tokens,
    totalTokens: display.usageUnavailable ? null : usage.total_tokens,
  }
}

export const pilotRecipes = [
  ...aggregate.entries.map((entry) => buildRecipe(entry, aggregate)),
  ...anchoredPlacement.entries.map((entry) => buildRecipe(entry, anchoredPlacement, true)),
]
  .sort((left, right) => right.score - left.score || left.id.localeCompare(right.id))
  .map((recipe, index) => ({ ...recipe, rank: index + 1 }))

export const pilotMeta = Object.freeze({
  aggregateId: `${aggregate.aggregate_id} + ${anchoredPlacement.aggregate_id}`,
  aggregateIds: [aggregate.aggregate_id, anchoredPlacement.aggregate_id],
  fixtureSha256: aggregate.fixture_sha256,
  scoreVersion: `${aggregate.score_version} + ${anchoredPlacement.score_version}`,
  stagePolicy: aggregate.policies.stage,
  translationFailureMultiplier: aggregate.policies.translation_failure_multiplier,
  updated: '02 AUG 2026',
  recipes: pilotRecipes.length,
  hardTasksPerRecipe: HARD_TASKS_PER_RECIPE,
  pairwiseReports: aggregate.judge_telemetry.report_count
    + anchoredPlacement.judge_telemetry.report_count,
  judgeAttempts: aggregate.judge_telemetry.http_attempt_count
    + anchoredPlacement.judge_telemetry.http_attempt_count,
  direction: 'EN → ZH-CN',
})

export function formatPilotCost(recipe, per100 = false, locale = 'en') {
  if (recipe.costKind === 'local-hardware') return locale === 'zh' ? '本地 GPU' : 'Local GPU'
  if (recipe.costUsd === null) return locale === 'zh' ? '免费档' : 'Free tier'
  const value = per100 ? recipe.costPer100 : recipe.costUsd
  return `$${value.toFixed(per100 ? 3 : 5)}`
}
