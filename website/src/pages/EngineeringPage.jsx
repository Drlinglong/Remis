import { MeasuredText } from '../components/MeasuredText'
import { ButtonLink, SiteShell, StatusPill, TextLink } from '../components/SiteShell'
import {
  assetPath,
  benchmarkMetrics,
  copilotLayers,
  links,
  sitePath,
  workflowDiagrams,
} from '../site'

function SystemMap() {
  return (
    <div className="system-map" aria-label="Remis localization intelligence system map">
      <div className="system-map__header">
        <span>CONTEXT GRAPH / PRODUCT RUNTIME</span>
        <span>READ · PROPOSE · VALIDATE · REVIEW</span>
      </div>
      <div className="system-map__canvas">
        <span className="system-map__line system-map__line--one" aria-hidden="true"></span>
        <span className="system-map__line system-map__line--two" aria-hidden="true"></span>
        <span className="system-map__line system-map__line--three" aria-hidden="true"></span>
        <span className="system-map__line system-map__line--four" aria-hidden="true"></span>
        <div className="system-node system-node--source"><b>GAME FILES</b><span>keys · structure · source text</span></div>
        <div className="system-node system-node--context"><b>PROJECT CONTEXT</b><span>glossary · history · parent entries</span></div>
        <div className="system-node system-node--model"><b>MODEL PROVIDER</b><span>cloud API · Ollama · compatible endpoint</span></div>
        <div className="system-node system-node--control"><b>REMIS CONTROL PLANE</b><span>schemas · validators · native handlers</span></div>
        <div className="system-node system-node--review"><b>HUMAN REVIEW</b><span>compare · approve · deploy</span></div>
      </div>
      <p>Model output crosses a validation boundary before it can become product state.</p>
    </div>
  )
}

function WorkflowChapter({ workflow }) {
  return (
    <article className="workflow-chapter">
      <div className="workflow-chapter__heading">
        <div>
          <p className="eyebrow eyebrow--dark">{workflow.eyebrow} · {workflow.index}</p>
          <h3>{workflow.title}</h3>
        </div>
        <span className="workflow-chapter__status">ANIMATED SYSTEM VIEW</span>
      </div>
      <div className="workflow-chapter__body">
        <figure className="workflow-visual">
          <img src={assetPath(workflow.asset)} alt={workflow.alt} />
          <div className="workflow-motion-note">
            Animation is hidden because reduced motion is enabled. The workflow details remain available beside the diagram.
          </div>
          <figcaption>Existing Remis workflow asset · animation preserved from the repository README</figcaption>
        </figure>
        <dl className="workflow-questions">
          <div><dt>01 / INPUT</dt><dd>{workflow.input}</dd></div>
          <div><dt>02 / STATE</dt><dd>{workflow.state}</dd></div>
          <div><dt>03 / MODEL ROLE</dt><dd>{workflow.model}</dd></div>
          <div><dt>04 / RECOVERY</dt><dd>{workflow.recovery}</dd></div>
        </dl>
      </div>
    </article>
  )
}

export function EngineeringPage() {
  return (
    <SiteShell activePage="engineering">
      <section className="page-hero page-hero--engineering">
        <div className="container engineering-hero-grid">
          <div>
            <p className="eyebrow">AI ENGINEERING · SYSTEM RELATIONSHIPS AND TRUST BOUNDARIES</p>
            <MeasuredText className="display-heading display-heading--engineering">
              Localization intelligence, without surrendering control.
            </MeasuredText>
            <p className="hero-lead">
              Remis coordinates game structure, project memory, provider-flexible
              inference, deterministic validation, and human review. The model proposes.
              The product decides what is safe to accept.
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
              <p className="eyebrow eyebrow--dark">WORKING SYSTEMS · NOT CONCEPT ART</p>
              <MeasuredText as="h2" className="section-title">
                Three workflows that make the architecture real.
              </MeasuredText>
            </div>
            <p>
              These animated diagrams already document the repository. The product site
              adds the questions a technical reviewer needs: input, state, model role,
              and recovery behaviour.
            </p>
          </div>
          <div className="workflow-chapters">
            {workflowDiagrams.map((workflow) => (
              <WorkflowChapter key={workflow.title} workflow={workflow} />
            ))}
          </div>
        </div>
      </section>

      <section className="section section--paper">
        <div className="container">
          <div className="section-heading section-heading--split">
            <div>
              <p className="eyebrow eyebrow--dark">THE CONTROL BOUNDARY</p>
              <MeasuredText as="h2" className="section-title">
                Retrieve. Structure. Validate. Confirm. Execute.
              </MeasuredText>
            </div>
            <p>
              The roadmap adds AI capability without handing filesystem authority to a
              free-roaming agent. Each layer has one job and one trust boundary.
            </p>
          </div>

          <div className="architecture-stack">
            {copilotLayers.map((layer, index) => (
              <article className="architecture-layer" key={layer.name}>
                <span className="architecture-layer__index">0{index + 1}</span>
                <div>
                  <p className="mono-label">{layer.eyebrow}</p>
                  <h3>{layer.name}</h3>
                </div>
                <p>{layer.description}</p>
                <StatusPill>{layer.status}</StatusPill>
              </article>
            ))}
          </div>

          <div className="architecture-rule">
            <span>MODEL PROPOSES</span>
            <span>REMIS VALIDATES</span>
            <span>UI EXPLAINS</span>
            <span>HUMAN CONFIRMS</span>
          </div>
        </div>
      </section>

      <section className="section section--paper qa-section">
        <div className="container qa-grid">
          <div>
            <p className="eyebrow eyebrow--dark">READ-ONLY TRANSLATION QA COPILOT</p>
            <MeasuredText as="h2" className="section-title">
              Quality judgement with context, evidence, and no silent mutation.
            </MeasuredText>
            <p className="section-intro">
              A child localization key can retrieve its parent event, decision, or
              journal entry before the system evaluates tone. The result is a report,
              not an automatic overwrite.
            </p>
          </div>
          <div className="qa-report" aria-label="Example translation quality report">
            <div className="qa-report__header">
              <span>TRANSLATION QUALITY REPORT</span>
              <StatusPill>Research track</StatusPill>
            </div>
            <dl>
              <div><dt>Overall</dt><dd>Usable, proofreading recommended</dd></div>
              <div><dt>Format risk</dt><dd>Low</dd></div>
              <div><dt>Terminology</dt><dd>Medium consistency</dd></div>
              <div><dt>Context naturalness</dt><dd>Good</dd></div>
              <div><dt>Write access</dt><dd>Disabled</dd></div>
            </dl>
            <div className="qa-report__finding">
              <span>STYLE SUGGESTION</span>
              <p>“The Senate shall endure” → “元老院必将长存”</p>
              <small>Reason: ceremonial political register · Confidence: medium</small>
            </div>
          </div>
        </div>
      </section>

      <section className="section section--signal">
        <div className="container benchmark-grid">
          <div>
            <p className="eyebrow">AGENT EVALUATION</p>
            <MeasuredText as="h2" className="section-title">
              Benchmark the work removed, not how intelligent the model sounds.
            </MeasuredText>
            <p>
              A Remis agent succeeds when it closes the scan–repair–rescan loop at an
              acceptable cost and leaves fewer repetitive steps for the user.
            </p>
          </div>
          <div className="metric-ledger">
            {benchmarkMetrics.map(([metric, question], index) => (
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
            <p className="eyebrow eyebrow--dark">NON-NEGOTIABLE SAFETY RULES</p>
            <h2>The model never gets a blank cheque.</h2>
          </div>
          <ul className="rule-list">
            <li>Do not index API keys or secrets.</li>
            <li>Do not index arbitrary user mod content by default.</li>
            <li>Reject actions outside the Remis-owned registry.</li>
            <li>Require explicit confirmation before every write.</li>
            <li>Log action results for inspection and debugging.</li>
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
