import { getVendorLogo } from '../vendorLogos'
import { formatPilotCost, pilotMeta, pilotRecipes } from '../aventinePilotData'

const chartCopy = {
  en: {
    nav: 'Benchmark charts', intelligence: 'Intelligence', speed: 'Speed', cost: 'Cost per 100 tasks', tradeoff: 'Intelligence vs. cost',
    intelligenceDesc: 'Blind language preference and hard reliability under Pilot Score v0.1 · Higher is better',
    recipesMeta: `${pilotRecipes.length} of ${pilotRecipes.length} recipes`, scoreRanking: 'Pilot Quality Score ranking',
    scoreFooter: '60% soft preference · 40% hard reliability', speedDesc: 'Completed frozen hard samples per wall-clock hour · Higher is better',
    runsMeta: '3 runs · 21 tasks each', speedRanking: 'Tasks per hour ranking', wallTime: 'End-to-end wall time includes provider queueing and transport.',
    costDesc: 'Estimated model inference cost (USD) for 100 Aventine tasks · Lower is better', pricingMeta: 'Standard/list price equivalent',
    costRanking: 'Cost per 100 tasks ranking', pricing: 'Google Standard pricing · OpenRouter run-date pricing', judgeExcluded: 'Judge cost excluded',
    scatterTitle: 'Intelligence Index vs. Cost per 100 Tasks', scatterDesc: 'Pilot Quality Score · Estimated inference cost (USD) per 100 tasks',
    attractiveMeta: 'Most attractive = upper left', attractiveLegend: 'Most attractive quadrant', paretoLegend: 'Pareto frontier',
    scatterLabel: 'Interactive Pilot Quality Score versus cost per 100 tasks chart', highQuality: 'HIGH QUALITY', lowCost: 'LOW COST',
    scoreAxis: 'Pilot Quality Score', costAxis: 'Cost per 100 Aventine tasks (USD)', freeTier: 'Free tier',
    freeTierMeaning: 'provider benefit used during this run', freeTierNote: 'Free-tier points represent the provider benefit used during this run—not permanent zero-cost inference.',
    higher: 'Higher is better →', lower: '← Lower is better',
  },
  zh: {
    nav: '基准图表', intelligence: '智力指数', speed: '速度', cost: '每 100 题成本', tradeoff: '智力指数 vs. 成本',
    intelligenceDesc: 'Pilot Score v0.1 下的盲裁语言偏好与硬可靠性 · 越高越好',
    recipesMeta: `${pilotRecipes.length} / ${pilotRecipes.length} 套方案`, scoreRanking: 'Pilot Quality Score 排名',
    scoreFooter: '60% 软偏好 · 40% 硬可靠性', speedDesc: '每小时完成的冻结硬样本数 · 越高越好',
    runsMeta: '3 轮 · 每轮 21 题', speedRanking: '每小时任务数排名', wallTime: '端到端耗时包含服务商排队与网络传输。',
    costDesc: '完成 100 个 Aventine 任务的模型推理估算成本（美元）· 越低越好', pricingMeta: '标准价 / 目录价等值',
    costRanking: '每 100 题成本排名', pricing: 'Google Standard 计价 · OpenRouter 测试当日计价', judgeExcluded: '不含裁判成本',
    scatterTitle: '智力指数 vs. 每 100 题成本', scatterDesc: 'Pilot Quality Score · 每 100 题模型推理估算成本（美元）',
    attractiveMeta: '越靠左上越有吸引力', attractiveLegend: '高质量低成本区', paretoLegend: '帕累托前沿',
    scatterLabel: 'Pilot Quality Score 与每 100 题成本的可交互图表', highQuality: '高质量', lowCost: '低成本',
    scoreAxis: 'Pilot Quality Score', costAxis: '每 100 个 Aventine 任务成本（美元）', freeTier: '免费档',
    freeTierMeaning: '本轮使用的服务商福利', freeTierNote: '免费档点位表示本轮使用了服务商福利，不代表永久零成本推理。',
    higher: '越高越好 →', lower: '← 越低越好',
  },
}

export function AventineBrandMark({ recipe }) {
  const logo = getVendorLogo(recipe.vendorId)

  return (
    <span className={`benchmark-brand benchmark-brand--${recipe.id}`} aria-label={recipe.vendor}>
      {logo
        ? <img alt="" aria-hidden="true" src={logo.src} />
        : recipe.vendorMark}
    </span>
  )
}

function ChartCard({ id, title, description, meta, children }) {
  return (
    <article className="aa-chart-card" id={id}>
      <header className="aa-chart-card__header">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <span>{meta}</span>
      </header>
      {children}
    </article>
  )
}

function RankingBars({ recipes, getValue, formatValue, label, labels, lowerIsBetter = false, freeTier = false, onSelect }) {
  const numericValues = recipes.map(getValue).filter((value) => value !== null)
  const maxValue = Math.max(...numericValues)

  return (
    <div className="aa-ranking-chart" role="list" aria-label={label}>
      <div className="aa-ranking-chart__grid" aria-hidden="true">
        <span /><span /><span /><span />
      </div>
      {recipes.map((recipe) => {
        const value = getValue(recipe)
        const height = value === null ? 4 : Math.max(7, (value / maxValue) * 100)
        const valueLabel = value === null ? labels.freeTier : formatValue(value)

        return (
          <button
            aria-label={`${recipe.model}: ${valueLabel}`}
            className={`aa-ranking-bar ${value === null ? 'is-free-tier' : ''}`}
            key={recipe.id}
            onClick={() => onSelect(recipe.id)}
            role="listitem"
            type="button"
          >
            <span className="aa-ranking-bar__value">{valueLabel}</span>
            <span className="aa-ranking-bar__plot">
              <span style={{ '--bar-height': `${height}%`, '--bar-color': recipe.color }} />
            </span>
            <span className="aa-ranking-bar__model">
              <AventineBrandMark recipe={recipe} />
              <strong>{recipe.model}</strong>
              <small>{recipe.reasoning}</small>
            </span>
          </button>
        )
      })}
      <p className="aa-ranking-chart__direction">
        {lowerIsBetter ? labels.lower : labels.higher}
        {freeTier && <span>{labels.freeTier} = {labels.freeTierMeaning}</span>}
      </p>
    </div>
  )
}

function getParetoFrontier(recipes) {
  const byCost = [...recipes].sort((left, right) => {
    const costDelta = (left.costPer100 ?? 0) - (right.costPer100 ?? 0)
    return costDelta || right.score - left.score
  })
  let bestScore = -Infinity
  return byCost.filter((recipe) => {
    if (recipe.score <= bestScore) return false
    bestScore = recipe.score
    return true
  })
}

function scatterPosition(recipe) {
  const maxCost = 2
  const minScore = 50
  const maxScore = 85
  const plottedCost = recipe.costPer100 ?? 0
  return {
    x: 4 + Math.min(plottedCost / maxCost, 1) * 92,
    y: 8 + Math.min(Math.max((recipe.score - minScore) / (maxScore - minScore), 0), 1) * 84,
  }
}

function ParetoFrontier() {
  const frontier = getParetoFrontier(pilotRecipes)
  const points = frontier.map((recipe) => {
    const position = scatterPosition(recipe)
    return `${position.x},${100 - position.y}`
  }).join(' ')
  return (
    <svg aria-hidden="true" className="aa-scatter__pareto" preserveAspectRatio="none" viewBox="0 0 100 100">
      <polyline points={points} />
    </svg>
  )
}

function IntelligenceCostScatter({ labels, onSelect }) {
  return (
    <div className="aa-scatter-wrap">
      <div className="aa-scatter__legend">
        <span><i /> {labels.attractiveLegend}</span>
        <span><b /> {labels.paretoLegend}</span>
      </div>
      <div className="aa-scatter" role="group" aria-label={labels.scatterLabel}>
        <div className="aa-scatter__attractive">{labels.highQuality}<br />{labels.lowCost}</div>
        <ParetoFrontier />
        {pilotRecipes.map((recipe, index) => {
          const position = scatterPosition(recipe)
          return (
            <button
              aria-label={`${recipe.model}: ${recipe.score} score, ${recipe.costUsd === null ? labels.freeTier : formatPilotCost(recipe, true)}`}
              className="aa-scatter__point"
              key={recipe.id}
              onClick={() => onSelect(recipe.id)}
              style={{
                '--point-color': recipe.color,
                '--x': `${position.x}%`,
                '--y': `${position.y}%`,
                '--label-shift': `${[-14, 20, 72, 10, -8, 20, 18, 42, -5][index]}px`,
                '--label-rise': `${[0, 18, 44, 0, 0, 32, 8, -14, -4][index]}px`,
              }}
              type="button"
            >
              <span>{recipe.model}<small>{recipe.costUsd === null ? labels.freeTier : `$${recipe.costPer100.toFixed(3)}`}</small></span>
              <i />
            </button>
          )
        })}
        <div className="aa-scatter__y-label">{labels.scoreAxis}</div>
        <div className="aa-scatter__x-label">{labels.costAxis}</div>
        <div className="aa-scatter__x-ticks" aria-hidden="true">
          <span>{labels.freeTier}</span><span>$0.50</span><span>$1.00</span><span>$1.50</span><span>$2.00</span>
        </div>
      </div>
      <p className="aa-scatter__note">{labels.freeTierNote}</p>
    </div>
  )
}

export function AventineBenchmarkCharts({ locale = 'en', onSelect }) {
  const labels = chartCopy[locale] ?? chartCopy.en
  const bySpeed = [...pilotRecipes].sort((left, right) => right.tasksPerHour - left.tasksPerHour)
  const byCost = [...pilotRecipes].sort((left, right) => {
    if (left.costUsd === null && right.costUsd !== null) return -1
    if (left.costUsd !== null && right.costUsd === null) return 1
    return (left.costPer100 ?? 0) - (right.costPer100 ?? 0)
  })

  return (
    <div className="aa-benchmark-charts">
      <nav className="aa-section-nav" aria-label={labels.nav}>
        <a href="#intelligence">{labels.intelligence}</a>
        <a href="#speed">{labels.speed}</a>
        <a href="#cost-per-100">{labels.cost}</a>
        <a href="#intelligence-vs-cost">{labels.tradeoff}</a>
      </nav>

      <ChartCard
        description={labels.intelligenceDesc}
        id="intelligence"
        meta={labels.recipesMeta}
        title={labels.intelligence}
      >
        <RankingBars
          formatValue={(value) => value.toFixed(2)}
          getValue={(recipe) => recipe.score}
          label={labels.scoreRanking}
          labels={labels}
          onSelect={onSelect}
          recipes={pilotRecipes}
        />
        <footer className="aa-chart-card__footer">
          <span><b>{pilotMeta.scoreVersion}</b> {labels.scoreFooter}</span>
          <span>{pilotMeta.updated}</span>
        </footer>
      </ChartCard>

      <ChartCard
        description={labels.speedDesc}
        id="speed"
        meta={labels.runsMeta}
        title={labels.speed}
      >
        <RankingBars
          formatValue={(value) => `${value.toFixed(1)}/h`}
          getValue={(recipe) => recipe.tasksPerHour}
          label={labels.speedRanking}
          labels={labels}
          onSelect={onSelect}
          recipes={bySpeed}
        />
        <footer className="aa-chart-card__footer"><span>{labels.wallTime}</span></footer>
      </ChartCard>

      <ChartCard
        description={labels.costDesc}
        id="cost-per-100"
        meta={labels.pricingMeta}
        title={labels.cost}
      >
        <RankingBars
          formatValue={(value) => `$${value.toFixed(3)}`}
          freeTier
          getValue={(recipe) => recipe.costPer100}
          label={labels.costRanking}
          labels={labels}
          lowerIsBetter
          onSelect={onSelect}
          recipes={byCost}
        />
        <footer className="aa-chart-card__footer">
          <span>{labels.pricing}</span>
          <span>{labels.judgeExcluded}</span>
        </footer>
      </ChartCard>

      <ChartCard
        description={labels.scatterDesc}
        id="intelligence-vs-cost"
        meta={labels.attractiveMeta}
        title={labels.scatterTitle}
      >
        <IntelligenceCostScatter labels={labels} onSelect={onSelect} />
      </ChartCard>
    </div>
  )
}
