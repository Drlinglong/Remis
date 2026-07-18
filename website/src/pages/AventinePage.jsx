import { MeasuredText } from '../components/MeasuredText'
import { ButtonLink, SiteShell, StatusPill, TextLink } from '../components/SiteShell'
import { translateDeep, useI18n } from '../i18n/context'
import {
  aventineEvidence,
  aventineProofPoints,
  aventineRanking,
  aventineRecipeStages,
  links,
  sitePath,
} from '../site'

function EvidenceStrip() {
  const { t } = useI18n()
  const proofPoints = translateDeep(aventineProofPoints, t)
  return (
    <section className="proof-strip proof-strip--aventine" aria-label={t('Aventine project evidence')}>
      <div className="container proof-grid">
        {proofPoints.map((point) => (
          <article key={point.label} className="proof-item">
            <strong>{point.value}</strong>
            <span>{point.label}</span>
            <p>{point.note}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

function RecipeContract() {
  const { t } = useI18n()
  const stages = translateDeep(aventineRecipeStages, t)
  return (
    <div className="aventine-contract" role="list" aria-label={t('Aventine translation recipe evaluation pipeline')}>
      {stages.map((stage) => (
        <article key={stage.title} className="aventine-contract__stage" role="listitem">
          <div className="aventine-contract__identity">
            <span>{stage.index}</span>
            <p>{stage.eyebrow}</p>
          </div>
          <div>
            <h3>{stage.title}</h3>
            <p>{stage.body}</p>
          </div>
          <code>{stage.code}</code>
        </article>
      ))}
    </div>
  )
}

function TournamentTable() {
  const { t } = useI18n()
  const ranking = translateDeep(aventineRanking, t)
  return (
    <div className="tournament-table" role="table" aria-label={t('First Remis tournament ranking')}>
      <div className="tournament-table__row tournament-table__header" role="row">
        <span role="columnheader">{t('Rank')}</span>
        <span role="columnheader">{t('Recipe')}</span>
        <span role="columnheader">{t('Hard pass')}</span>
        <span role="columnheader">{t('Record')}</span>
        <span role="columnheader">{t('Unresolved')}</span>
        <span role="columnheader">{t('Result')}</span>
      </div>
      {ranking.map((entry, index) => (
        <div className={`tournament-table__row ${index === 0 ? 'is-champion' : ''}`} role="row" key={entry.recipe}>
          <span role="cell">{entry.rank}</span>
          <strong role="cell">{entry.recipe}</strong>
          <span role="cell">{entry.hardPass}</span>
          <span role="cell">{entry.record}</span>
          <span role="cell">{entry.unresolved}</span>
          <span role="cell">{entry.result}</span>
        </div>
      ))}
    </div>
  )
}

export function AventinePage() {
  const { t } = useI18n()
  const evidence = translateDeep(aventineEvidence, t)

  return (
    <SiteShell activePage="aventine">
      <section className="page-hero page-hero--aventine">
        <div className="container aventine-hero-grid">
          <div className="aventine-hero__copy">
            <div className="runtime-status" role="status">
              <span aria-hidden="true"></span>
              {t('AVENTINE · TRANSLATION RECIPE EVALUATION')}
            </div>
            <MeasuredText className="display-heading display-heading--aventine">
              {t('Turn translation quality into evidence.')}
            </MeasuredText>
            <p className="hero-lead">
              {t('Born from Remis, Aventine compares the complete system that produces a translation: model, provider, prompt, context, glossary, decoding, validators, repair, and post-processing. Every result is versioned, inspectable, and built for regression.')}
            </p>
            <div className="hero-actions">
              <ButtonLink href={links.aventine} tone="accent" external>Open Aventine on GitHub</ButtonLink>
              <ButtonLink href={links.aventineTournament} tone="dark" external>Read the first tournament</ButtonLink>
            </div>
          </div>

          <div className="aventine-instrument" aria-label={t('Aventine evidence instrument')}>
            <div className="aventine-instrument__header">
              <span>AVENTINE / RUN 001</span>
              <StatusPill>Shipped</StatusPill>
            </div>
            <div className="aventine-instrument__winner">
              <span>{t('FIRST REMIS RECIPE PILOT')}</span>
              <strong>QWEN 3.6</strong>
              <p>{t('Champion · 15 wins · 7/7 hard pass')}</p>
            </div>
            <div className="aventine-instrument__trace" aria-hidden="true">
              <span>recipe</span><b>→</b><span>veto</span><b>→</b><span>judge × 2</span><b>→</b><span>report</span>
            </div>
            <dl>
              <div><dt>{t('Fixture')}</dt><dd>SHA-256 / 4fad…a47335</dd></div>
              <div><dt>{t('Decision contract')}</dt><dd>{t('hard veto + A/B swap')}</dd></div>
              <div><dt>{t('Repair restraint')}</dt><dd>{t('no recorded over-editing')}</dd></div>
            </dl>
          </div>
        </div>
      </section>

      <EvidenceStrip />

      <section className="section section--paper">
        <div className="container">
          <div className="section-heading section-heading--split">
            <div>
              <p className="eyebrow eyebrow--dark">{t('THE UNIT OF COMPETITION')}</p>
              <MeasuredText as="h2" className="section-title">
                {t('The recipe, not the model name.')}
              </MeasuredText>
            </div>
            <p>
              {t('A model name cannot explain why a translation succeeded. Aventine evaluates the complete recipe and preserves the exact inputs, policies, and evidence behind every result.')}
            </p>
          </div>
          <RecipeContract />
        </div>
      </section>

      <section className="section section--ink tournament-section" id="tournament">
        <div className="container">
          <div className="section-heading section-heading--split">
            <div>
              <p className="eyebrow">{t('THE FIRST TOURNAMENT · 2026-07-16')}</p>
              <MeasuredText as="h2" className="section-title">
                {t('Four real recipes entered. Qwen 3.6 finished first.')}
              </MeasuredText>
            </div>
            <p>
              {t('Four Remis-produced recipe artifacts ran against the same seven-case frozen fixture. The result is a reproducible engineering comparison with explicit limits, not a model-brand popularity poll.')}
            </p>
          </div>
          <TournamentTable />
          <div className="tournament-note">
            <span>{t('Evidence note')}</span>
            <p>
              {t('Every recipe faced 21 case-level matchups. Hard failures were resolved before judging; eligible soft-quality cases ran in both A/B orders; position-inconsistent outputs stayed unresolved.')}
            </p>
          </div>
        </div>
      </section>

      <section className="section section--signal aventine-evidence-section">
        <div className="container">
          <div className="section-heading section-heading--split">
            <div>
              <p className="eyebrow">{t('WHAT AVENTINE PROVED')}</p>
              <MeasuredText as="h2" className="section-title">
                {t('The result is strong because the contract is strict.')}
              </MeasuredText>
            </div>
            <p>
              {t('Aventine does not compress uncertainty into one decorative score. It preserves vetoes, judge disagreement, repair behaviour, failures, cost, and latency as evidence a developer can inspect.')}
            </p>
          </div>
          <div className="aventine-evidence-grid">
            {evidence.map((item) => (
              <article key={item.title}>
                <span>{item.index}</span>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section section--paper judge-section" id="judge-calibration">
        <div className="container judge-grid">
          <div>
            <p className="eyebrow eyebrow--dark">{t('JUDGE CALIBRATION')}</p>
            <MeasuredText as="h2" className="section-title">
              {t('Three judges. One 48-case pack. No invented certainty.')}
            </MeasuredText>
            <p className="section-intro">
              {t('DeepSeek and Grok both reached 83.3% base accuracy. Gemma delivered a free baseline and exposed a different failure profile. Aventine turns those differences into an evidence portfolio instead of pretending one score settles every translation task.')}
            </p>
            <TextLink href={links.aventineJudgeComparison} external>Inspect the judge comparison</TextLink>
          </div>
          <div className="judge-ledger" role="table" aria-label={t('Judge calibration results')}>
            <div className="judge-ledger__row judge-ledger__header" role="row">
              <span role="columnheader">{t('Judge')}</span>
              <span role="columnheader">{t('Base accuracy')}</span>
              <span role="columnheader">{t('Position consistency')}</span>
              <span role="columnheader">{t('False-good')}</span>
            </div>
            <div className="judge-ledger__row" role="row">
              <strong role="cell">DeepSeek V4 Pro</strong><span role="cell">83.3%</span><span role="cell">95.8%</span><span role="cell">22.2%</span>
            </div>
            <div className="judge-ledger__row" role="row">
              <strong role="cell">Grok 4.5</strong><span role="cell">83.3%</span><span role="cell">100%</span><span role="cell">11.1%</span>
            </div>
            <div className="judge-ledger__row" role="row">
              <strong role="cell">Gemma 4 31B</strong><span role="cell">72.9%</span><span role="cell">82.6%</span><span role="cell">77.8%</span>
            </div>
          </div>
        </div>
      </section>

      <section className="section section--ink aventine-bridge">
        <div className="container closing-grid">
          <div>
            <p className="eyebrow">{t('FROM PRODUCT TO EVALUATION SYSTEM')}</p>
            <MeasuredText as="h2" className="section-title">
              {t('Remis ships the workflow. Aventine makes its quality claims falsifiable.')}
            </MeasuredText>
          </div>
          <div>
            <p>
              {t('Together, the projects form an end-to-end AI engineering story: a desktop product that generates, validates, repairs, and reviews localization, plus an independent evaluation system that tests complete translation recipes under explicit trust boundaries.')}
            </p>
            <div className="inline-links">
              <TextLink href={sitePath('engineering/')}>Explore the Remis engineering system</TextLink>
              <TextLink href={links.aventine} external>View Aventine source</TextLink>
            </div>
          </div>
        </div>
      </section>

      <section className="section section--paper">
        <div className="container closing-grid closing-grid--dark-text">
          <div>
            <p className="eyebrow eyebrow--dark">{t('WHAT COMES NEXT')}</p>
            <h2>{t('A regression layer for every model, prompt, validator, and repair decision.')}</h2>
          </div>
          <div>
            <p>
              {t('Aventine can become the evidence layer behind release gates, provider changes, prompt revisions, model selection, and project-specific A/B trials, without turning judge output into automatic production authority.')}
            </p>
            <div className="inline-links">
              <TextLink href={links.aventineTournament} external>Reproduce the experiment</TextLink>
              <TextLink href={links.issue132} external>Read the product vision</TextLink>
            </div>
          </div>
        </div>
      </section>
    </SiteShell>
  )
}
