import { useMemo, useState } from 'react'
import { AventineBenchmarkCharts, AventineBrandMark } from '../components/AventineBenchmarkCharts'
import { ButtonLink, SiteShell, TextLink } from '../components/SiteShell'
import { formatPilotCost, pilotMeta, pilotRecipes } from '../aventinePilotData'
import { useI18n } from '../i18n/context'
import { links } from '../site'

const copy = {
  en: {
    eyebrow: 'AVENTINE / TRANSLATION RECIPE BENCHMARK',
    title: 'Which LLM actually translates best?',
    intro: 'Nine API recipes. One frozen Remis workload. Three runs per model, blinded pairwise judging, hard validation, and costs measured beside quality.',
    updated: 'Pilot Score v0.1 · 01 AUG 2026',
    recipes: 'RECIPES',
    cases: 'HARD TASKS / RECIPE',
    matchups: 'PAIRWISE REPORTS',
    directions: 'LANGUAGE DIRECTION',
    explore: 'Explore every result',
    exploreIntro: 'Select any model to inspect the exact recipe, reliability, coverage, tokens, cost, and pilot interpretation behind its rank.',
    selected: 'SELECTED RECIPE',
    qualityScore: 'PILOT QUALITY SCORE',
    softPreference: 'Soft preference',
    winRate: 'Raw win rate',
    hardReliability: 'Hard reliability',
    resolved: 'Decision coverage',
    wins: 'Wins',
    losses: 'Losses',
    ties: 'Ties',
    unresolved: 'Unresolved',
    parameters: 'Recipe parameters',
    runSignals: 'Measured run telemetry',
    elapsed: 'Three-run wall time',
    estimatedCost: 'Contestant cost',
    throughput: 'Tasks per hour',
    outputTokens: 'Output tokens',
    reasoningTokens: 'Reasoning tokens',
    hardPass: 'Hard passes',
    voice: 'Translation style / pilot interpretation',
    parameterModel: 'Model ID',
    parameterProvider: 'Provider',
    parameterReasoning: 'Reasoning',
    parameterFixture: 'Fixture',
    parameterDirection: 'Direction',
    parameterJudge: 'Judge',
    parameterContract: 'Decision contract',
    fixture: '5 translation + 2 repair × 3 runs',
    direction: 'English → Simplified Chinese',
    judge: 'DeepSeek V4 Flash · low reasoning · 8k',
    contract: 'hard veto + A/B position swap',
    costNote: 'Free tier means the provider benefit used during this run—not permanent zero-cost inference.',
    whyTitle: 'A benchmark for the system that ships the translation.',
    whyBody: 'A model name alone cannot explain production quality. Aventine compares complete recipes: model, provider, reasoning effort, prompt, terminology context, validators, repair, cost, and latency.',
    principleProduction: 'Production-grounded',
    principleProductionBody: 'Recipes execute the frozen Remis translation and repair workflow rather than isolated chat prompts.',
    principleComparable: 'Directly comparable',
    principleComparableBody: 'Every recipe receives the same 21 hard samples and the same blinded decision contract.',
    principleOperational: 'Operationally measurable',
    principleOperationalBody: 'Quality remains separate from speed, cost, token use, failures, and decision coverage.',
    principleVersioned: 'Versioned evidence',
    principleVersionedBody: 'Scores carry their aggregate ID, fixture hash, score version, reasoning label, and policy revision.',
    methodology: 'One frozen contract. No hidden rescue.',
    methodologyBody: 'Recoverable translation contract failures retain 67% of the sample value; unrecoverable, execution, alignment, and repair failures score zero. Only position-consistent A/B judge decisions enter language preference.',
    source: 'View Aventine source',
    aggregate: 'Inspect aggregate artifact',
    roadmap: 'Open scoring roadmap',
  },
  zh: {
    eyebrow: 'AVENTINE / 翻译方案基准测试',
    title: '哪一个大模型，真的更会翻译？',
    intro: '九套 API 翻译方案，同一份冻结 Remis 工作负载。每个模型正式运行三轮，盲化成对裁决、硬校验、成本与质量同时记录。',
    updated: 'Pilot Score v0.1 · 2026 年 8 月 1 日',
    recipes: '参赛方案',
    cases: '每套方案硬样本',
    matchups: '成对裁决报告',
    directions: '语言方向',
    explore: '查看每一项结果',
    exploreIntro: '选择任意模型，检查其排名背后的 recipe、可靠性、覆盖率、Tokens、成本与本轮评价。',
    selected: '当前方案',
    qualityScore: 'PILOT QUALITY SCORE',
    softPreference: '软偏好得分',
    winRate: '真实胜率',
    hardReliability: '硬可靠性',
    resolved: '有效裁决覆盖率',
    wins: '胜',
    losses: '负',
    ties: '平',
    unresolved: '未裁决',
    parameters: '测试参数',
    runSignals: '真实运行指标',
    elapsed: '三轮总耗时',
    estimatedCost: '选手推理成本',
    throughput: '每小时任务数',
    outputTokens: '输出 Tokens',
    reasoningTokens: '推理 Tokens',
    hardPass: '硬通过样本',
    voice: '翻译风格 / 本轮评价',
    parameterModel: '模型 ID',
    parameterProvider: 'Provider',
    parameterReasoning: '推理强度',
    parameterFixture: '测试集',
    parameterDirection: '语言方向',
    parameterJudge: '裁判模型',
    parameterContract: '裁决规则',
    fixture: '5 个翻译 + 2 个修复 × 3 轮',
    direction: '英文 → 简体中文',
    judge: 'DeepSeek V4 Flash · low reasoning · 8k',
    contract: '硬失败否决 + A/B 换位复判',
    costNote: '“免费”表示本轮使用了服务商免费端点或额度，不代表永久零成本推理。',
    whyTitle: '评估真正交付译文的完整系统。',
    whyBody: '只看模型名称无法解释生产质量。Aventine 比较完整 recipe：模型、Provider、推理强度、Prompt、术语上下文、验证器、修复、成本与延迟。',
    principleProduction: '来自真实生产',
    principleProductionBody: '参赛方案执行冻结的 Remis 翻译与修复工作流，而不是孤立聊天提示词。',
    principleComparable: '可以直接比较',
    principleComparableBody: '每套方案面对相同的 21 个硬样本与同一套盲化裁决规则。',
    principleOperational: '记录运行表现',
    principleOperationalBody: '质量与速度、成本、Token、失败类型和裁决覆盖率保持独立。',
    principleVersioned: '版本化证据',
    principleVersionedBody: '每项分数都携带 aggregate ID、fixture hash、score version、推理标签与策略版本。',
    methodology: '一套冻结规则，不为任何模型暗中补救。',
    methodologyBody: '翻译阶段可恢复的契约失败保留该样本 67% 分值；不可恢复、执行、条目错位与修复失败归零。只有 A/B 换位结论一致的裁决才进入语言偏好。',
    source: '查看 Aventine 源码',
    aggregate: '检查 aggregate artifact',
    roadmap: '打开评分路线图',
  },
}

function formatDuration(seconds) {
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.round(seconds % 60)
  return `${minutes}m ${remainder.toString().padStart(2, '0')}s`
}

function formatTokens(tokens) {
  return new Intl.NumberFormat('en-US').format(tokens)
}

function MetricBar({ label, value, color }) {
  return (
    <div className="recipe-metric">
      <div><span>{label}</span><strong>{value.toFixed(1)}%</strong></div>
      <span className="recipe-metric__track"><span style={{ '--metric': `${value}%`, '--metric-color': color }} /></span>
    </div>
  )
}
export function AventinePage() {
  const { locale } = useI18n()
  const labels = copy[locale] ?? copy.en
  const [selectedId, setSelectedId] = useState('gemini36')
  const selected = useMemo(
    () => pilotRecipes.find((recipe) => recipe.id === selectedId) ?? pilotRecipes[0],
    [selectedId],
  )

  return (
    <SiteShell activePage="aventine">
      <div className="aventine-benchmark">
        <section className="benchmark-hero">
          <div className="container benchmark-hero__inner">
            <header className="benchmark-title">
              <div>
                <p>{labels.eyebrow}</p>
                <h1>{labels.title}</h1>
                <span>{labels.intro}</span>
                <small className="benchmark-title__version">{labels.updated} · {pilotMeta.aggregateId}</small>
              </div>
              <div className="benchmark-facts" aria-label="Benchmark parameters">
                <div><strong>{pilotMeta.recipes}</strong><span>{labels.recipes}</span></div>
                <div><strong>{pilotMeta.hardTasksPerRecipe}</strong><span>{labels.cases}</span></div>
                <div><strong>{pilotMeta.pairwiseReports}</strong><span>{labels.matchups}</span></div>
                <div><strong>1</strong><span>{labels.directions}</span></div>
              </div>
            </header>
            <AventineBenchmarkCharts locale={locale} onSelect={setSelectedId} />
          </div>
        </section>

        <section className="benchmark-detail" id="explore-results">
          <div className="container">
            <div className="benchmark-section-title">
              <div>
                <p>{labels.explore}</p>
                <span>{labels.exploreIntro}</span>
              </div>
              <div className="recipe-tabs" role="tablist" aria-label={labels.explore}>
                {pilotRecipes.map((recipe) => (
                  <button
                    aria-selected={recipe.id === selectedId}
                    className={recipe.id === selectedId ? 'is-active' : ''}
                    key={recipe.id}
                    onClick={() => setSelectedId(recipe.id)}
                    role="tab"
                    type="button"
                  >
                    <AventineBrandMark recipe={recipe} />
                    {recipe.model}
                  </button>
                ))}
              </div>
            </div>

            <div className="recipe-dashboard">
              <div className="recipe-summary">
                <span>{labels.selected} / 0{selected.rank}</span>
                <div className="recipe-summary__name">
                  <AventineBrandMark recipe={selected} />
                  <div><h2>{selected.model}</h2><p>{selected.provider} · {selected.reasoning}</p></div>
                </div>
                <div className="recipe-score">
                  <strong style={{ color: selected.color }}>{selected.score.toFixed(2)}</strong>
                  <span>{labels.qualityScore}</span>
                </div>
                <dl>
                  <div><dt>{labels.wins}</dt><dd>{selected.wins}</dd></div>
                  <div><dt>{labels.losses}</dt><dd>{selected.losses}</dd></div>
                  <div><dt>{labels.ties}</dt><dd>{selected.ties}</dd></div>
                  <div><dt>{labels.unresolved}</dt><dd>{selected.unresolved}</dd></div>
                </dl>
              </div>

              <div className="recipe-performance">
                <MetricBar label={labels.softPreference} value={selected.softPreference} color={selected.color} />
                <MetricBar label={labels.hardReliability} value={selected.hardReliability} color={selected.color} />
                <MetricBar label={labels.winRate} value={selected.winRate} color={selected.color} />
                <MetricBar label={labels.resolved} value={selected.coverage} color={selected.color} />
              </div>

              <div className="recipe-parameters">
                <h3>{labels.parameters}</h3>
                <dl>
                  <div><dt>{labels.parameterModel}</dt><dd>{selected.modelId}</dd></div>
                  <div><dt>{labels.parameterProvider}</dt><dd>{selected.provider}</dd></div>
                  <div><dt>{labels.parameterReasoning}</dt><dd>{selected.reasoning}</dd></div>
                  <div><dt>{labels.parameterFixture}</dt><dd>{labels.fixture}</dd></div>
                  <div><dt>{labels.parameterDirection}</dt><dd>{labels.direction}</dd></div>
                  <div><dt>{labels.parameterJudge}</dt><dd>{labels.judge}</dd></div>
                  <div><dt>{labels.parameterContract}</dt><dd>{labels.contract}</dd></div>
                </dl>
              </div>

              <div className="recipe-diagnostics">
                <div className="recipe-diagnostics__head">
                  <h3>{labels.runSignals}</h3>
                  <span>{pilotMeta.scoreVersion} · {pilotMeta.stagePolicy}</span>
                </div>
                <div className="recipe-kpis">
                  {[
                    [labels.elapsed, formatDuration(selected.elapsedSeconds)],
                    [labels.estimatedCost, formatPilotCost(selected)],
                    [labels.throughput, selected.tasksPerHour.toFixed(1)],
                    [labels.outputTokens, formatTokens(selected.outputTokens)],
                    [labels.reasoningTokens, formatTokens(selected.reasoningTokens)],
                    [labels.hardPass, `${selected.hardPass}/${selected.hardSamples}`],
                  ].map(([label, value]) => (
                    <div key={label}><span>{label}</span><strong>{value}</strong></div>
                  ))}
                </div>
                <div className="recipe-voice">
                  <span>{labels.voice}</span>
                  <div><p>{selected.style[locale] ?? selected.style.en}</p><small>{labels.costNote}</small></div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="benchmark-positioning">
          <div className="container benchmark-positioning__grid">
            <div>
              <p>WHY AVENTINE</p>
              <h2>{labels.whyTitle}</h2>
              <span>{labels.whyBody}</span>
            </div>
            <div className="benchmark-principles">
              {[
                [labels.principleProduction, labels.principleProductionBody],
                [labels.principleComparable, labels.principleComparableBody],
                [labels.principleOperational, labels.principleOperationalBody],
                [labels.principleVersioned, labels.principleVersionedBody],
              ].map(([title, body], index) => (
                <article key={title}>
                  <small>0{index + 1}</small>
                  <div><strong>{title}</strong><span>{body}</span></div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="benchmark-method">
          <div className="container benchmark-method__inner">
            <div>
              <h2>{labels.methodology}</h2>
              <p>{labels.methodologyBody}</p>
            </div>
            <div className="benchmark-method__links">
              <ButtonLink href={links.aventinePilotAggregate} tone="accent" external>{labels.aggregate}</ButtonLink>
              <TextLink href={links.aventine} external>{labels.source}</TextLink>
              <TextLink href={links.aventineScoringRoadmap} external>{labels.roadmap}</TextLink>
            </div>
          </div>
        </section>
      </div>
    </SiteShell>
  )
}
