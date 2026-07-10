import { MeasuredText } from '../components/MeasuredText'
import { ButtonLink, SiteShell, StatusPill, TextLink } from '../components/SiteShell'
import { benchmarkMetrics, copilotLayers, links, shippedCapabilities, sitePath } from '../site'

export function EngineeringPage() {
  return (
    <SiteShell activePage="engineering">
      <section className="page-hero page-hero--engineering">
        <div className="container page-hero__grid">
          <div>
            <p className="eyebrow">AI ENGINEERING · ARCHITECTURE AND EVALUATION</p>
            <MeasuredText className="display-heading display-heading--page">
              Not a chatbot bolted onto a translator.
            </MeasuredText>
          </div>
          <div className="page-hero__aside">
            <p>
              Remis treats model output as untrusted input. Retrieval is read-only,
              intent is schema-bound, writes pass through native handlers, and the user
              sees the plan before anything consequential happens.
            </p>
            <ButtonLink href={links.issue132} tone="accent" external>Read architecture issue #132</ButtonLink>
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

      <section className="section section--ink">
        <div className="container">
          <div className="section-heading section-heading--split">
            <div>
              <p className="eyebrow">CURRENT SYSTEM</p>
              <MeasuredText as="h2" className="section-title">
                The agent roadmap starts from working reliability primitives.
              </MeasuredText>
            </div>
            <p>
              These are shipped code paths, not future-tense architecture. They are the
              reason a bounded Copilot can reuse real product capabilities.
            </p>
          </div>
          <div className="evidence-grid">
            {shippedCapabilities.map((capability) => (
              <article key={capability.title} className="evidence-item">
                <span className="ledger-status">{capability.label}</span>
                <h3>{capability.title}</h3>
                <p>{capability.body}</p>
                <code>{capability.code}</code>
              </article>
            ))}
          </div>
          <TextLink href={links.architecture} external>Read the current architecture document</TextLink>
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
