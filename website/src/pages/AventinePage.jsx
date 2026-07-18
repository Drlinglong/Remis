import { useMemo, useState } from 'react'
import { ButtonLink, SiteShell, TextLink } from '../components/SiteShell'
import { useI18n } from '../i18n/context'
import { links } from '../site'

// PREVIEW TELEMETRY:
// compositeScore, elapsed, cost, throughput, outputTokens, termDiscovery, errorRate,
// and style are presentation fixtures until the Remis workflow exports these fields.
// Tournament rank, wins/losses/ties, unresolved counts, and hard-pass counts are recorded results.
const recipes = [
  {
    id: 'qwen',
    rank: 1,
    vendor: 'Alibaba',
    vendorMark: 'Q',
    model: 'Qwen 3.6',
    spec: '27B · Q4_K_M',
    color: '#20d7b5',
    compositeScore: 91.2,
    wins: 15,
    losses: 1,
    ties: 2,
    unresolved: 3,
    hardPass: 7,
    elapsed: '02:41',
    cost: '¥0.38',
    throughput: '31.8 tok/s',
    outputTokens: '18.4k',
    termDiscovery: 94,
    errorRate: 1.8,
    style: {
      en: 'Restrained, natural, and terminologically stable. Dialogue preserves character identity; long sentences are split with care. Closest to release-ready Simplified Chinese.',
      zh: '克制、自然、术语稳定。对白保留人物身份感，长句会谨慎拆分，整体最接近可直接发布的简体中文。',
    },
  },
  {
    id: 'gemma',
    rank: 2,
    vendor: 'Google',
    vendorMark: 'G',
    model: 'Gemma 4',
    spec: '31B · QAT Q4_0',
    color: '#4d8dff',
    compositeScore: 84.6,
    wins: 11,
    losses: 4,
    ties: 2,
    unresolved: 4,
    hardPass: 7,
    elapsed: '02:18',
    cost: '¥0.44',
    throughput: '28.6 tok/s',
    outputTokens: '19.1k',
    termDiscovery: 91,
    errorRate: 2.6,
    style: {
      en: 'Fluent and slightly literary, with more expressive phrasing. Strong for narrative text, though occasional proactive polishing can expand the original meaning.',
      zh: '流畅而略偏文学化，措辞更有表现力。适合叙事文本，但偶尔会主动润色，需要留意对原意的扩写。',
    },
  },
  {
    id: 'translate-gemma',
    rank: 3,
    vendor: 'Google',
    vendorMark: 'G',
    model: 'TranslateGemma',
    spec: '27B Instruct · Q6_K',
    color: '#f1aa28',
    compositeScore: 68.4,
    wins: 4,
    losses: 7,
    ties: 2,
    unresolved: 6,
    hardPass: 5,
    elapsed: '01:56',
    cost: '¥0.31',
    throughput: '34.1 tok/s',
    outputTokens: '17.7k',
    termDiscovery: 88,
    errorRate: 5.4,
    style: {
      en: 'Faithful and direct, often retaining the source sentence structure. Terminology is consistent, but long passages can feel rigid and need rhythm-focused editing.',
      zh: '忠实、直接，倾向保留原句结构。术语一致性良好，但长文本略显生硬，局部需要人工调整行文节奏。',
    },
  },
  {
    id: 'nemotron',
    rank: 4,
    vendor: 'NVIDIA',
    vendorMark: 'N',
    model: 'Nemotron Cascade 2',
    spec: '30B A3B · Q4_K_M',
    color: '#ef5b78',
    compositeScore: 32.1,
    wins: 0,
    losses: 18,
    ties: 0,
    unresolved: 1,
    hardPass: 1,
    elapsed: '01:34',
    cost: '¥0.27',
    throughput: '38.7 tok/s',
    outputTokens: '16.9k',
    termDiscovery: 72,
    errorRate: 18.9,
    style: {
      en: 'Neutral and mechanical. Short lines remain readable, but complex formatting and long context weaken constraint retention and voice consistency.',
      zh: '语气中性但较机械，短句尚可；复杂格式与长上下文中容易丢失约束，整体风格一致性较弱。',
    },
  },
].map((recipe) => ({
  ...recipe,
  resolved: 21 - recipe.unresolved,
  winRate: Math.round((recipe.wins / (21 - recipe.unresolved)) * 1000) / 10,
  resolvedRate: Math.round(((21 - recipe.unresolved) / 21) * 1000) / 10,
  hardPassRate: Math.round((recipe.hardPass / 7) * 1000) / 10,
}))

const judges = [
  { name: 'DeepSeek V4 Pro', color: '#20d7b5', accuracy: 83.3, position: 95.8, falseGood: 22.2, cost: '¥1.06' },
  { name: 'Grok 4.5', color: '#f1aa28', accuracy: 83.3, position: 100, falseGood: 11.1, cost: '$0.48' },
  { name: 'Gemma 4 31B', color: '#4d8dff', accuracy: 72.9, position: 82.6, falseGood: 77.8, cost: '$0' },
]

const copy = {
  en: {
    eyebrow: 'AVENTINE / TRANSLATION RECIPE BENCHMARK',
    title: 'Which local LLM actually translates best?',
    intro: 'Four production recipes. One frozen Remis test pack. Every model runs the same translation and repair workload.',
    updated: 'Pilot 01 · 16 JUL 2026',
    metric: 'Aventine composite score',
    metricNote: 'PREVIEW · composite formula pending',
    scoreContext: 'Preview values · rank follows the recorded pilot result',
    recipes: 'RECIPES',
    cases: 'FROZEN CASES',
    matchups: 'HEAD-TO-HEADS',
    directions: 'LANGUAGE DIRECTIONS',
    champion: 'CHAMPION',
    winRate: 'WIN RATE',
    record: 'W–L–T',
    hardPass: 'HARD PASS',
    unresolved: 'UNRESOLVED',
    explore: 'Explore every result',
    exploreIntro: 'Select a recipe to inspect the signals behind its rank.',
    whyTitle: 'A benchmark for the system that ships the translation.',
    whyBody: 'Model names alone do not explain production quality. Prompt design, terminology context, decoding, validation, and repair can change the result as much as the base model. Aventine compares those complete recipes under one frozen workload.',
    principleProduction: 'Production-grounded',
    principleProductionBody: 'Recipes come from the real Remis workflow, not isolated chat prompts.',
    principleComparable: 'Directly comparable',
    principleComparableBody: 'Every recipe receives the same translation and repair cases.',
    principleOperational: 'Operationally measurable',
    principleOperationalBody: 'Quality is read alongside time, cost, throughput, terminology, and errors.',
    principleRelease: 'Release-oriented',
    principleReleaseBody: 'Structural safety and voice matter alongside linguistic preference.',
    selected: 'SELECTED RECIPE',
    resolved: 'Resolved coverage',
    termDiscovery: 'Terminology discovery · PREVIEW',
    errorControl: 'Error-free rate · PREVIEW',
    wins: 'Wins',
    losses: 'Losses',
    ties: 'Ties',
    parameters: 'Recipe parameters',
    runSignals: 'Workflow telemetry',
    previewSignals: 'PREVIEW DATA · awaiting workflow instrumentation',
    elapsed: 'Total elapsed',
    estimatedCost: 'Estimated cost',
    throughput: 'Throughput',
    outputTokens: 'Output tokens',
    termDiscoveryShort: 'Terms found',
    errorRate: 'Error rate',
    voice: 'Translation style / voice',
    parameterModel: 'Model',
    parameterQuant: 'Quantization',
    parameterFixture: 'Fixture',
    parameterDirection: 'Directions',
    parameterJudge: 'Judge',
    parameterContract: 'Decision contract',
    fixture: '5 translation + 2 repair',
    direction: 'EN → ZH-CN / ZH-CN → EN',
    judge: 'DeepSeek V4 Pro · high thinking',
    contract: 'hard veto + A/B swap',
    calibration: 'JUDGE CALIBRATION',
    calibrationTitle: 'The evaluator is benchmarked too.',
    calibrationIntro: '48 known-answer cases compare accuracy, position consistency, false-good risk, and run cost across three judge providers.',
    accuracy: 'BASE ACCURACY',
    consistency: 'POSITION CONSISTENCY',
    falseGood: 'FALSE-GOOD',
    cost: 'RUN COST',
    lower: 'lower is better',
    methodology: 'One contract, no hidden rescue.',
    methodologyBody: 'Hard validator failures are decided before LLM judging. Eligible quality comparisons run in both A/B orders. Inconsistent decisions stay unresolved.',
    source: 'View source & schemas',
    report: 'Read tournament report',
    comparison: 'Inspect judge comparison',
  },
  zh: {
    eyebrow: 'AVENTINE / 翻译方案基准测试',
    title: '哪一个本地大模型，真的更会翻译？',
    intro: '四套生产级翻译方案，同一份冻结测试集。每个模型面对完全相同的翻译与修复任务。',
    updated: '首轮测试 · 2026 年 7 月 16 日',
    metric: 'Aventine 综合评分',
    metricNote: 'PREVIEW · 综合分算法待接入',
    scoreContext: '当前为展示值 · 排名依据首轮真实对局结果',
    recipes: '参赛方案',
    cases: '冻结案例',
    matchups: '模型对局',
    directions: '语言方向',
    champion: '冠军',
    winRate: '胜率',
    record: '胜–负–平',
    hardPass: '硬校验通过',
    unresolved: '未裁决',
    explore: '查看每个模型的测评结果',
    exploreIntro: '选择一个翻译方案，查看排名背后的性能信号。',
    whyTitle: '评估真正交付译文的完整系统。',
    whyBody: '只看模型名称，无法解释生产质量。提示词、术语上下文、解码参数、校验与修复流程，都可能像基础模型一样改变最终结果。Aventine 让这些完整 translation recipe 在同一份冻结任务中直接竞争。',
    principleProduction: '来自真实生产',
    principleProductionBody: '参赛方案源于 Remis 实际工作流，而不是孤立的聊天提示词。',
    principleComparable: '可以直接比较',
    principleComparableBody: '每套方案面对完全相同的翻译与修复案例。',
    principleOperational: '记录运行表现',
    principleOperationalBody: '质量与耗时、成本、吞吐量、术语发现和错误率同时呈现。',
    principleRelease: '面向真实发布',
    principleReleaseBody: '除了语言偏好，也测试结构安全、术语稳定与翻译语气。',
    selected: '当前模型',
    resolved: '有效裁决覆盖率',
    termDiscovery: '术语发现率 · PREVIEW',
    errorControl: '无错误率 · PREVIEW',
    wins: '胜',
    losses: '负',
    ties: '平',
    parameters: '测试参数',
    runSignals: '工作流运行记录',
    previewSignals: 'PREVIEW DATA · 等待工作流埋点接入',
    elapsed: '总耗时',
    estimatedCost: '估算成本',
    throughput: '生成速度',
    outputTokens: '输出 Tokens',
    termDiscoveryShort: '发现术语',
    errorRate: '错误率',
    voice: '翻译风格 / 语气',
    parameterModel: '模型',
    parameterQuant: '量化',
    parameterFixture: '测试集',
    parameterDirection: '语言方向',
    parameterJudge: '裁判模型',
    parameterContract: '裁决规则',
    fixture: '5 个翻译 + 2 个修复案例',
    direction: '英文 → 简中 / 简中 → 英文',
    judge: 'DeepSeek V4 Pro · 高思考',
    contract: '硬失败否决 + A/B 换位',
    calibration: '裁判模型校准',
    calibrationTitle: '连裁判，也必须先接受测试。',
    calibrationIntro: '使用 48 个已知答案案例，对比三个裁判模型的准确率、位置一致性、误放行率与运行成本。',
    accuracy: '基础准确率',
    consistency: '位置一致性',
    falseGood: '误放行率',
    cost: '运行成本',
    lower: '越低越好',
    methodology: '一套规则，不为任何模型暗中补救。',
    methodologyBody: '硬校验失败先于 LLM 裁判决定胜负。合格的软质量对局执行 A/B 换位复判；结论不一致则保留为未裁决。',
    source: '查看源码与数据结构',
    report: '阅读完整赛事报告',
    comparison: '查看裁判对比',
  },
}

function BrandMark({ recipe }) {
  return (
    <span className={`benchmark-brand benchmark-brand--${recipe.id}`} aria-label={recipe.vendor}>
      {recipe.vendorMark}
    </span>
  )
}

function Leaderboard({ labels, selectedId, onSelect }) {
  return (
    <div className="benchmark-board" aria-label={labels.metric}>
      <div className="benchmark-board__head">
        <div>
          <strong>{labels.metric}</strong>
          <span>{labels.metricNote}</span>
        </div>
        <span>{labels.updated}</span>
      </div>
      <div className="benchmark-axis" aria-hidden="true">
        <span>0</span><span>20</span><span>40</span><span>60</span><span>80%</span>
      </div>
      <div className="benchmark-bars">
        {recipes.map((recipe) => (
          <button
            className={`benchmark-bar ${selectedId === recipe.id ? 'is-selected' : ''}`}
            key={recipe.id}
            onClick={() => onSelect(recipe.id)}
            type="button"
          >
            <span className="benchmark-bar__rank">0{recipe.rank}</span>
            <span className="benchmark-bar__identity">
              <BrandMark recipe={recipe} />
              <span><strong>{recipe.model}</strong><small>{recipe.spec}</small></span>
            </span>
            <span className="benchmark-bar__track">
              <span style={{ '--score': `${recipe.compositeScore}%`, '--bar-color': recipe.color }} />
            </span>
            <strong className="benchmark-bar__score">{recipe.compositeScore.toFixed(1)}</strong>
            <span className="benchmark-bar__record">{recipe.wins}–{recipe.losses}–{recipe.ties}</span>
          </button>
        ))}
      </div>
      <div className="benchmark-board__legend">
        <span><b>PREVIEW</b> {labels.scoreContext}</span>
        <span><b>{labels.record}</b> {labels.wins}–{labels.losses}–{labels.ties}</span>
      </div>
    </div>
  )
}

function MetricBar({ label, value, color, suffix = '%' }) {
  return (
    <div className="recipe-metric">
      <div><span>{label}</span><strong>{value}{suffix}</strong></div>
      <span className="recipe-metric__track"><span style={{ '--metric': `${value}%`, '--metric-color': color }} /></span>
    </div>
  )
}

export function AventinePage() {
  const { locale } = useI18n()
  const labels = copy[locale] ?? copy.en
  const [selectedId, setSelectedId] = useState('qwen')
  const selected = useMemo(() => recipes.find((recipe) => recipe.id === selectedId) ?? recipes[0], [selectedId])
  const [quantization] = selected.spec.split(' · ').slice(-1)

  return (
    <SiteShell activePage="aventine">
      <main className="aventine-benchmark">
        <section className="benchmark-hero">
          <div className="container benchmark-hero__inner">
            <header className="benchmark-title">
              <div>
                <p>{labels.eyebrow}</p>
                <h1>{labels.title}</h1>
                <span>{labels.intro}</span>
              </div>
              <div className="benchmark-facts" aria-label="Benchmark parameters">
                <div><strong>4</strong><span>{labels.recipes}</span></div>
                <div><strong>7</strong><span>{labels.cases}</span></div>
                <div><strong>42</strong><span>{labels.matchups}</span></div>
                <div><strong>2</strong><span>{labels.directions}</span></div>
              </div>
            </header>
            <Leaderboard labels={labels} selectedId={selectedId} onSelect={setSelectedId} />
          </div>
        </section>

        <section className="benchmark-detail">
          <div className="container">
            <div className="benchmark-section-title">
              <div>
                <p>{labels.explore}</p>
                <span>{labels.exploreIntro}</span>
              </div>
              <div className="recipe-tabs" role="tablist" aria-label={labels.explore}>
                {recipes.map((recipe) => (
                  <button
                    aria-selected={recipe.id === selectedId}
                    className={recipe.id === selectedId ? 'is-active' : ''}
                    key={recipe.id}
                    onClick={() => setSelectedId(recipe.id)}
                    role="tab"
                    type="button"
                  >
                    <BrandMark recipe={recipe} />
                    {recipe.model}
                  </button>
                ))}
              </div>
            </div>

            <div className="recipe-dashboard">
              <div className="recipe-summary">
                <span>{labels.selected} / 0{selected.rank}</span>
                <div className="recipe-summary__name">
                  <BrandMark recipe={selected} />
                  <div><h2>{selected.model}</h2><p>{selected.spec}</p></div>
                </div>
                <div className="recipe-score">
                  <strong style={{ color: selected.color }}>{selected.winRate.toFixed(1)}%</strong>
                  <span>{labels.winRate}</span>
                </div>
                <dl>
                  <div><dt>{labels.wins}</dt><dd>{selected.wins}</dd></div>
                  <div><dt>{labels.losses}</dt><dd>{selected.losses}</dd></div>
                  <div><dt>{labels.ties}</dt><dd>{selected.ties}</dd></div>
                  <div><dt>{labels.unresolved}</dt><dd>{selected.unresolved}</dd></div>
                </dl>
              </div>

              <div className="recipe-performance">
                <MetricBar label={labels.winRate} value={selected.winRate} color={selected.color} />
                <MetricBar label={labels.hardPass} value={selected.hardPassRate} color={selected.color} />
                <MetricBar label={labels.resolved} value={selected.resolvedRate} color={selected.color} />
                <MetricBar label={labels.termDiscovery} value={selected.termDiscovery} color={selected.color} />
                <MetricBar label={labels.errorControl} value={100 - selected.errorRate} color={selected.color} />
              </div>

              <div className="recipe-parameters">
                <h3>{labels.parameters}</h3>
                <dl>
                  <div><dt>{labels.parameterModel}</dt><dd>{selected.model}</dd></div>
                  <div><dt>{labels.parameterQuant}</dt><dd>{quantization}</dd></div>
                  <div><dt>{labels.parameterFixture}</dt><dd>{labels.fixture}</dd></div>
                  <div><dt>{labels.parameterDirection}</dt><dd>{labels.direction}</dd></div>
                  <div><dt>{labels.parameterJudge}</dt><dd>{labels.judge}</dd></div>
                  <div><dt>{labels.parameterContract}</dt><dd>{labels.contract}</dd></div>
                </dl>
              </div>

              <div className="recipe-diagnostics">
                <div className="recipe-diagnostics__head">
                  <h3>{labels.runSignals}</h3>
                  <span>{labels.previewSignals}</span>
                </div>
                <div className="recipe-kpis">
                  {[
                    [labels.elapsed, selected.elapsed],
                    [labels.estimatedCost, selected.cost],
                    [labels.throughput, selected.throughput],
                    [labels.outputTokens, selected.outputTokens],
                    [labels.termDiscoveryShort, `${selected.termDiscovery}%`],
                    [labels.errorRate, `${selected.errorRate}%`],
                  ].map(([label, value]) => (
                    <div key={label}><span>{label}</span><strong>{value}</strong></div>
                  ))}
                </div>
                <div className="recipe-voice">
                  <span>{labels.voice}</span>
                  <p>{selected.style[locale] ?? selected.style.en}</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="judge-benchmark">
          <div className="container">
            <div className="benchmark-section-title">
              <div>
                <small>{labels.calibration}</small>
                <p>{labels.calibrationTitle}</p>
                <span>{labels.calibrationIntro}</span>
              </div>
              <TextLink href={links.aventineJudgeComparison} external>{labels.comparison}</TextLink>
            </div>
            <div className="judge-chart" role="table" aria-label={labels.calibration}>
              <div className="judge-chart__head" role="row">
                <span role="columnheader">MODEL</span>
                <span role="columnheader">{labels.accuracy}</span>
                <span role="columnheader">{labels.consistency}</span>
                <span role="columnheader">{labels.falseGood}<small>{labels.lower}</small></span>
                <span role="columnheader">{labels.cost}</span>
              </div>
              {judges.map((judge) => (
                <div className="judge-chart__row" role="row" key={judge.name}>
                  <strong role="cell"><i style={{ background: judge.color }} />{judge.name}</strong>
                  <span role="cell"><b style={{ '--judge-value': `${judge.accuracy}%`, '--judge-color': judge.color }} />{judge.accuracy}%</span>
                  <span role="cell"><b style={{ '--judge-value': `${judge.position}%`, '--judge-color': judge.color }} />{judge.position}%</span>
                  <span role="cell"><b style={{ '--judge-value': `${judge.falseGood}%`, '--judge-color': judge.color }} />{judge.falseGood}%</span>
                  <span role="cell">{judge.cost}</span>
                </div>
              ))}
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
                [labels.principleRelease, labels.principleReleaseBody],
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
              <ButtonLink href={links.aventine} tone="accent" external>{labels.source}</ButtonLink>
              <TextLink href={links.aventineTournament} external>{labels.report}</TextLink>
            </div>
          </div>
        </section>
      </main>
    </SiteShell>
  )
}
