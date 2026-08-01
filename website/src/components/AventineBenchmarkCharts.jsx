import { getVendorLogo } from '../vendorLogos'
import { formatPilotCost, pilotMeta, pilotRecipes } from '../aventinePilotData'

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

function RankingBars({ recipes, getValue, formatValue, label, lowerIsBetter = false, freeTier = false, onSelect }) {
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
        const valueLabel = value === null ? 'Free tier' : formatValue(value)

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
        {lowerIsBetter ? '← Lower is better' : 'Higher is better →'}
        {freeTier && <span>Free tier = provider benefit used during this run</span>}
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

function ParetoSegments() {
  const frontier = getParetoFrontier(pilotRecipes)
  return frontier.slice(0, -1).map((recipe, index) => {
    const start = scatterPosition(recipe)
    const end = scatterPosition(frontier[index + 1])
    const dx = end.x - start.x
    const dy = end.y - start.y
    const length = Math.sqrt((dx ** 2) + (dy ** 2))
    const angle = Math.atan2(-dy, dx) * (180 / Math.PI)
    return (
      <span
        className="aa-scatter__pareto-segment"
        key={`${recipe.id}-${frontier[index + 1].id}`}
        style={{ '--x': `${start.x}%`, '--y': `${start.y}%`, '--length': `${length}%`, '--angle': `${angle}deg` }}
      />
    )
  })
}

function IntelligenceCostScatter({ onSelect }) {
  return (
    <div className="aa-scatter-wrap">
      <div className="aa-scatter__legend">
        <span><i /> Most attractive quadrant</span>
        <span><b /> Pareto frontier</span>
      </div>
      <div className="aa-scatter" role="img" aria-label="Pilot Quality Score versus cost per 100 tasks">
        <div className="aa-scatter__attractive">HIGH QUALITY<br />LOW COST</div>
        <ParetoSegments />
        {pilotRecipes.map((recipe, index) => {
          const position = scatterPosition(recipe)
          return (
            <button
              aria-label={`${recipe.model}: ${recipe.score} score, ${formatPilotCost(recipe, true)} per 100 tasks`}
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
              <span>{recipe.model}<small>{recipe.costUsd === null ? 'Free tier' : `$${recipe.costPer100.toFixed(3)}`}</small></span>
              <i />
            </button>
          )
        })}
        <div className="aa-scatter__y-label">Pilot Quality Score</div>
        <div className="aa-scatter__x-label">Cost per 100 Aventine tasks (USD)</div>
        <div className="aa-scatter__x-ticks" aria-hidden="true">
          <span>Free tier</span><span>$0.50</span><span>$1.00</span><span>$1.50</span><span>$2.00</span>
        </div>
      </div>
      <p className="aa-scatter__note">Free-tier points represent the provider benefit used during this run—not permanent zero-cost inference.</p>
    </div>
  )
}

export function AventineBenchmarkCharts({ onSelect }) {
  const bySpeed = [...pilotRecipes].sort((left, right) => right.tasksPerHour - left.tasksPerHour)
  const byCost = [...pilotRecipes].sort((left, right) => {
    if (left.costUsd === null && right.costUsd !== null) return -1
    if (left.costUsd !== null && right.costUsd === null) return 1
    return (left.costPer100 ?? 0) - (right.costPer100 ?? 0)
  })

  return (
    <div className="aa-benchmark-charts">
      <nav className="aa-section-nav" aria-label="Benchmark charts">
        <a href="#intelligence">Intelligence</a>
        <a href="#speed">Speed</a>
        <a href="#cost-per-100">Cost per 100 tasks</a>
        <a href="#intelligence-vs-cost">Intelligence vs. cost</a>
      </nav>

      <ChartCard
        description="Blind language preference and hard reliability under Pilot Score v0.1 · Higher is better"
        id="intelligence"
        meta={`${pilotRecipes.length} of ${pilotRecipes.length} recipes`}
        title="Intelligence"
      >
        <RankingBars
          formatValue={(value) => value.toFixed(2)}
          getValue={(recipe) => recipe.score}
          label="Pilot Quality Score ranking"
          onSelect={onSelect}
          recipes={pilotRecipes}
        />
        <footer className="aa-chart-card__footer">
          <span><b>{pilotMeta.scoreVersion}</b> 60% soft preference · 40% hard reliability</span>
          <span>{pilotMeta.updated}</span>
        </footer>
      </ChartCard>

      <ChartCard
        description="Completed frozen hard samples per wall-clock hour · Higher is better"
        id="speed"
        meta="3 runs · 21 tasks each"
        title="Speed"
      >
        <RankingBars
          formatValue={(value) => `${value.toFixed(1)}/h`}
          getValue={(recipe) => recipe.tasksPerHour}
          label="Tasks per hour ranking"
          onSelect={onSelect}
          recipes={bySpeed}
        />
        <footer className="aa-chart-card__footer"><span>End-to-end wall time includes provider queueing and transport.</span></footer>
      </ChartCard>

      <ChartCard
        description="Estimated model inference cost (USD) for 100 Aventine tasks · Lower is better"
        id="cost-per-100"
        meta="Standard/list price equivalent"
        title="Cost per 100 tasks"
      >
        <RankingBars
          formatValue={(value) => `$${value.toFixed(3)}`}
          freeTier
          getValue={(recipe) => recipe.costPer100}
          label="Cost per 100 tasks ranking"
          lowerIsBetter
          onSelect={onSelect}
          recipes={byCost}
        />
        <footer className="aa-chart-card__footer">
          <span>Google Standard pricing · OpenRouter run-date pricing</span>
          <span>Judge cost excluded</span>
        </footer>
      </ChartCard>

      <ChartCard
        description="Pilot Quality Score · Estimated inference cost (USD) per 100 tasks"
        id="intelligence-vs-cost"
        meta="Most attractive = upper left"
        title="Intelligence Index vs. Cost per 100 Tasks"
      >
        <IntelligenceCostScatter onSelect={onSelect} />
      </ChartCard>
    </div>
  )
}
