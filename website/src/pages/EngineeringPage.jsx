import { MeasuredText } from '../components/MeasuredText'
import { ButtonLink, SiteShell, StatusPill, TextLink } from '../components/SiteShell'
import { translateDeep, useI18n } from '../i18n/context'
import {
  assetPath,
  agentMilestones,
  benchmarkMetrics,
  copilotLayers,
  links,
  sitePath,
  workflowDiagrams,
} from '../site'

function SystemMap() {
  const { t } = useI18n()
  return (
    <div className="system-map" aria-label={t('Remis localization intelligence system map')}>
      <div className="system-map__header">
        <span>{t('CONTEXT GRAPH / PRODUCT RUNTIME')}</span>
        <span>{t('READ · PROPOSE · VALIDATE · REVIEW')}</span>
      </div>
      <svg
        className="system-map__visual"
        viewBox="0 0 1200 720"
        role="img"
        aria-labelledby="system-map-title system-map-description"
      >
        <title id="system-map-title">{t('Remis localization intelligence system map')}</title>
        <desc id="system-map-description">{t('Model output crosses a validation boundary before it can become product state.')}</desc>
        <defs>
          <pattern id="system-map-grid" width="44" height="44" patternUnits="userSpaceOnUse">
            <path d="M 44 0 L 0 0 0 44" className="system-map__grid-line" />
          </pattern>
          <marker id="system-map-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" />
          </marker>
          <marker id="system-map-arrow-gold" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" />
          </marker>
          <filter id="system-map-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        <rect className="system-map__backdrop" width="1200" height="720" />
        <rect className="system-map__grid" width="1200" height="720" />
        <rect className="system-map__boundary" x="350" y="278" width="500" height="388" rx="12" />
        <text className="system-map__boundary-label" x="374" y="308">{t('REMIS VALIDATES')}</text>

        <path className="system-map__flow system-map__flow--one" d="M 340 155 C 405 155 423 349 480 365" />
        <path className="system-map__flow system-map__flow--two" d="M 600 180 L 600 320" />
        <path className="system-map__flow system-map__flow--three" d="M 860 155 C 795 155 777 349 720 365" />
        <path className="system-map__flow system-map__flow--four" d="M 600 470 L 600 565" />

        <g className="system-map__node system-map__node--source">
          <rect x="70" y="95" width="270" height="120" rx="8" />
          <foreignObject x="90" y="115" width="230" height="80">
            <div xmlns="http://www.w3.org/1999/xhtml" className="system-map__node-card">
              <b>{t('GAME FILES')}</b><span>{t('keys · structure · source text')}</span>
            </div>
          </foreignObject>
        </g>
        <g className="system-map__node system-map__node--context">
          <rect x="465" y="60" width="270" height="120" rx="8" />
          <foreignObject x="485" y="80" width="230" height="80">
            <div xmlns="http://www.w3.org/1999/xhtml" className="system-map__node-card">
              <b>{t('PROJECT CONTEXT')}</b><span>{t('glossary · history · parent entries')}</span>
            </div>
          </foreignObject>
        </g>
        <g className="system-map__node system-map__node--model">
          <rect x="860" y="95" width="270" height="120" rx="8" />
          <foreignObject x="880" y="115" width="230" height="80">
            <div xmlns="http://www.w3.org/1999/xhtml" className="system-map__node-card">
              <b>{t('MODEL PROVIDER')}</b><span>{t('cloud API · Ollama · compatible endpoint')}</span>
            </div>
          </foreignObject>
        </g>
        <g className="system-map__node system-map__node--control">
          <rect x="390" y="320" width="420" height="150" rx="10" />
          <foreignObject x="420" y="350" width="360" height="92">
            <div xmlns="http://www.w3.org/1999/xhtml" className="system-map__node-card system-map__node-card--control">
              <b>{t('REMIS CONTROL PLANE')}</b><span>{t('schemas · validators · native handlers')}</span>
            </div>
          </foreignObject>
        </g>
        <g className="system-map__node system-map__node--review">
          <rect x="465" y="565" width="270" height="100" rx="8" />
          <foreignObject x="485" y="582" width="230" height="66">
            <div xmlns="http://www.w3.org/1999/xhtml" className="system-map__node-card">
              <b>{t('HUMAN REVIEW')}</b><span>{t('compare · approve · deploy')}</span>
            </div>
          </foreignObject>
        </g>

        <circle className="system-map__pulse system-map__pulse--one" cx="340" cy="155" r="5" />
        <circle className="system-map__pulse system-map__pulse--two" cx="600" cy="180" r="5" />
        <circle className="system-map__pulse system-map__pulse--three" cx="860" cy="155" r="5" />
        <circle className="system-map__pulse system-map__pulse--four" cx="600" cy="565" r="6" />
      </svg>
      <p>{t('Model output crosses a validation boundary before it can become product state.')}</p>
    </div>
  )
}

function WorkflowChapter({ workflow }) {
  const { t } = useI18n()
  return (
    <article className="workflow-chapter">
      <div className="workflow-chapter__heading">
        <div>
          <p className="eyebrow eyebrow--dark">{workflow.eyebrow} · {workflow.index}</p>
          <h3>{workflow.title}</h3>
        </div>
        <span className="workflow-chapter__status">{t('ANIMATED SYSTEM VIEW')}</span>
      </div>
      <div className="workflow-chapter__body">
        <figure className="workflow-visual">
          <img src={assetPath(workflow.asset)} alt={workflow.alt} />
          <div className="workflow-motion-note">
            {t('Animation is hidden because reduced motion is enabled. The workflow details remain available beside the diagram.')}
          </div>
          <figcaption>{t('Existing Remis workflow asset · animation preserved from the repository README')}</figcaption>
        </figure>
        <dl className="workflow-questions">
          <div><dt>{t('01 / INPUT')}</dt><dd>{workflow.input}</dd></div>
          <div><dt>{t('02 / STATE')}</dt><dd>{workflow.state}</dd></div>
          <div><dt>{t('03 / MODEL ROLE')}</dt><dd>{workflow.model}</dd></div>
          <div><dt>{t('04 / RECOVERY')}</dt><dd>{workflow.recovery}</dd></div>
        </dl>
      </div>
    </article>
  )
}

export function EngineeringPage() {
  const { t } = useI18n()
  const localizedWorkflows = translateDeep(workflowDiagrams, t)
  const localizedCopilotLayers = translateDeep(copilotLayers, t)
  const localizedAgentMilestones = translateDeep(agentMilestones, t)
  const localizedBenchmarkMetrics = benchmarkMetrics.map(([metric, question]) => [metric, t(question)])
  return (
    <SiteShell activePage="engineering">
      <section className="page-hero page-hero--engineering">
        <div className="container engineering-hero-grid">
          <div>
            <p className="eyebrow">{t('AI ENGINEERING · SYSTEM RELATIONSHIPS AND TRUST BOUNDARIES')}</p>
            <MeasuredText className="display-heading display-heading--engineering">
              {t('Localization intelligence, without surrendering control.')}
            </MeasuredText>
            <p className="hero-lead">
              {t('Remis coordinates game structure, project memory, provider-flexible inference, deterministic validation, and human review. The model proposes. The product decides what is safe to accept.')}
            </p>
            <div className="hero-actions">
              <ButtonLink href={links.issue132} tone="accent" external>Read architecture issue #132</ButtonLink>
              <ButtonLink href="#workflows" tone="dark">Trace the shipped workflows</ButtonLink>
            </div>
          </div>
          <SystemMap />
        </div>
      </section>

      <section className="section section--paper workflow-section" id="workflows">
        <div className="container">
          <div className="section-heading section-heading--split">
            <div>
              <p className="eyebrow eyebrow--dark">{t('WORKING SYSTEMS · NOT CONCEPT ART')}</p>
              <MeasuredText as="h2" className="section-title">
                {t('Three workflows that make the architecture real.')}
              </MeasuredText>
            </div>
            <p>
              {t('These animated diagrams already document the repository. The product site adds the questions a technical reviewer needs: input, state, model role, and recovery behaviour.')}
            </p>
          </div>
          <div className="workflow-chapters">
            {localizedWorkflows.map((workflow) => (
              <WorkflowChapter key={workflow.title} workflow={workflow} />
            ))}
          </div>
        </div>
      </section>

      <section className="section section--paper">
        <div className="container">
          <div className="section-heading section-heading--split">
            <div>
              <p className="eyebrow eyebrow--dark">{t('THE CONTROL BOUNDARY')}</p>
              <MeasuredText as="h2" className="section-title">
                {t('Retrieve. Structure. Validate. Confirm. Execute.')}
              </MeasuredText>
            </div>
            <p>
              {t('The roadmap adds AI capability without handing filesystem authority to a free-roaming agent. Each layer has one job and one trust boundary.')}
            </p>
          </div>

          <div className="architecture-stack">
            {localizedCopilotLayers.map((layer, index) => (
              <article className="architecture-layer" key={layer.name}>
                <span className="architecture-layer__index">0{index + 1}</span>
                <div>
                  <p className="mono-label">{layer.eyebrow}</p>
                  <h3>{layer.name}</h3>
                </div>
                <p>{layer.description}</p>
                <StatusPill>{copilotLayers[index].status}</StatusPill>
              </article>
            ))}
          </div>

          <div className="architecture-rule">
            <span>{t('MODEL PROPOSES')}</span>
            <span>{t('REMIS VALIDATES')}</span>
            <span>{t('UI EXPLAINS')}</span>
            <span>{t('HUMAN CONFIRMS')}</span>
          </div>
        </div>
      </section>

      <section className="section section--ink agent-delivery-section" id="agent-delivery">
        <div className="container">
          <div className="section-heading section-heading--split">
            <div>
              <p className="eyebrow">{t('3.0.7 AGENT DELIVERY')}</p>
              <MeasuredText as="h2" className="section-title">
                {t('The Copilot moved from architecture note to working product surface.')}
              </MeasuredText>
            </div>
            <p>
              {t('The current 3.0.7 branch delivers the smallest complete agent loop: observe the live page, retrieve bounded context, propose typed work, wait for approval, and preserve the handoff into Remis workflows.')}
            </p>
          </div>
          <div className="agent-milestone-grid">
            {localizedAgentMilestones.map((milestone) => (
              <article key={milestone.title}>
                <span>{milestone.index}</span>
                <h3>{milestone.title}</h3>
                <p>{milestone.body}</p>
                <code>{milestone.evidence}</code>
              </article>
            ))}
          </div>
          <div className="agent-delivery-links">
            <TextLink href={links.issue132} external>Read the product vision</TextLink>
            <TextLink href={sitePath('aventine/')}>See how the evaluation system tests recipes</TextLink>
          </div>
        </div>
      </section>

      <section className="section section--paper qa-section">
        <div className="container qa-grid">
          <div>
            <p className="eyebrow eyebrow--dark">{t('READ-ONLY TRANSLATION QA COPILOT')}</p>
            <MeasuredText as="h2" className="section-title">
              {t('Quality judgement with context, evidence, and no silent mutation.')}
            </MeasuredText>
            <p className="section-intro">
              {t('A child localization key can retrieve its parent event, decision, or journal entry before the system evaluates tone. The result is a report, not an automatic overwrite.')}
            </p>
          </div>
          <div className="qa-report" aria-label={t('Example translation quality report')}>
            <div className="qa-report__header">
              <span>{t('TRANSLATION QUALITY REPORT')}</span>
              <StatusPill>Research track</StatusPill>
            </div>
            <dl>
              <div><dt>{t('Overall')}</dt><dd>{t('Usable, proofreading recommended')}</dd></div>
              <div><dt>{t('Format risk')}</dt><dd>{t('Low')}</dd></div>
              <div><dt>{t('Terminology')}</dt><dd>{t('Medium consistency')}</dd></div>
              <div><dt>{t('Context naturalness')}</dt><dd>{t('Good')}</dd></div>
              <div><dt>{t('Write access')}</dt><dd>{t('Disabled')}</dd></div>
            </dl>
            <div className="qa-report__finding">
              <span>{t('STYLE SUGGESTION')}</span>
              <p>“The Senate shall endure” → “元老院必将长存”</p>
              <small>{t('Reason: ceremonial political register · Confidence: medium')}</small>
            </div>
          </div>
        </div>
      </section>

      <section className="section section--signal">
        <div className="container benchmark-grid">
          <div>
            <p className="eyebrow">{t('AGENT EVALUATION')}</p>
            <MeasuredText as="h2" className="section-title">
              {t('Benchmark the work removed, not how intelligent the model sounds.')}
            </MeasuredText>
            <p>
              {t('A Remis agent succeeds when it closes the scan–repair–rescan loop at an acceptable cost and leaves fewer repetitive steps for the user.')}
            </p>
          </div>
          <div className="metric-ledger">
            {localizedBenchmarkMetrics.map(([metric, question], index) => (
              <div key={metric}>
                <span>0{index + 1}</span>
                <code>{metric}</code>
                <p>{question}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section section--paper safety-section">
        <div className="container safety-grid">
          <div>
            <p className="eyebrow eyebrow--dark">{t('NON-NEGOTIABLE SAFETY RULES')}</p>
            <h2>{t('The model never gets a blank cheque.')}</h2>
          </div>
          <ul className="rule-list">
            <li>{t('Do not index API keys or secrets.')}</li>
            <li>{t('Do not index arbitrary user mod content by default.')}</li>
            <li>{t('Reject actions outside the Remis-owned registry.')}</li>
            <li>{t('Require explicit confirmation before every write.')}</li>
            <li>{t('Log action results for inspection and debugging.')}</li>
          </ul>
          <div className="inline-links">
            <TextLink href={sitePath('roadmap/')}>See delivery status</TextLink>
            <TextLink href={links.github} external>Inspect the repository</TextLink>
          </div>
        </div>
      </section>
    </SiteShell>
  )
}
