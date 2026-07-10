import { MeasuredText } from '../components/MeasuredText'
import { ButtonLink, SiteShell, TextLink } from '../components/SiteShell'
import { assetPath, links, pipeline, proofPoints, shippedCapabilities, sitePath } from '../site'

function ProofStrip() {
  return (
    <section className="proof-strip" aria-label="Project evidence">
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

function Pipeline() {
  return (
    <div className="pipeline" role="list" aria-label="Remis localization pipeline">
      {pipeline.map((step) => (
        <article className="pipeline-step" key={step.name} role="listitem">
          <span>{step.index}</span>
          <h3>{step.name}</h3>
          <p>{step.detail}</p>
        </article>
      ))}
    </div>
  )
}

export function HomePage() {
  return (
    <SiteShell activePage="home">
      <section className="hero hero--home">
        <div className="container hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">LOCAL-FIRST AI WORKFLOW · WINDOWS DESKTOP</p>
            <MeasuredText className="display-heading">
              Localization that stays inspectable after the model answers.
            </MeasuredText>
            <p className="hero-lead">
              Remis turns Paradox mod localization into a controlled LLM pipeline with
              glossary-aware context, structured output, validation, repair loops, and
              human proofreading.
            </p>
            <div className="hero-actions">
              <ButtonLink href={links.releases} tone="accent" external>Download for Windows</ButtonLink>
              <ButtonLink href={sitePath('engineering/')} tone="dark">Inspect the AI architecture</ButtonLink>
            </div>
            <div className="keyword-rail" aria-label="Technical keywords">
              <span>Context assembly</span>
              <span>Structured outputs</span>
              <span>Human-in-the-loop</span>
              <span>LLMOps</span>
            </div>
          </div>

          <figure className="product-stage">
            <div className="product-stage__frame">
              <div className="product-stage__bar">
                <span></span><span></span><span></span>
                <small>Remis project workspace</small>
              </div>
              <img
                src={assetPath('screenshot-en-1.webp')}
                alt="Remis desktop application showing the project workspace"
              />
            </div>
            <figcaption>
              <span>01 / REAL PRODUCT</span>
              <span>Tauri · React · FastAPI · SQLite</span>
            </figcaption>
          </figure>
        </div>
      </section>

      <ProofStrip />

      <section className="section section--paper">
        <div className="container">
          <div className="section-heading section-heading--split">
            <div>
              <p className="eyebrow eyebrow--dark">THE WORKFLOW</p>
              <MeasuredText as="h2" className="section-title">
                AI where it helps. Deterministic checks where trust matters.
              </MeasuredText>
            </div>
            <p>
              Remis does not ask users to trust a chat window with their mod folder.
              Every model call sits inside a visible product workflow with explicit
              inputs, validation, recovery, and review.
            </p>
          </div>
          <Pipeline />
          <TextLink href={sitePath('engineering/')}>Open the engineering case study</TextLink>
        </div>
      </section>

      <section className="section section--ink">
        <div className="container">
          <div className="section-heading section-heading--split">
            <div>
              <p className="eyebrow">SHIPPED FOUNDATIONS</p>
              <MeasuredText as="h2" className="section-title">
                More than a translation prompt.
              </MeasuredText>
            </div>
            <p>
              The system already contains the contracts and failure handling that make
              future RAG and Copilot work useful instead of theatrical.
            </p>
          </div>
          <div className="capability-ledger">
            {shippedCapabilities.map((capability, index) => (
              <article key={capability.title} className="ledger-row">
                <span className="ledger-index">0{index + 1}</span>
                <div>
                  <span className="ledger-status">{capability.label}</span>
                  <h3>{capability.title}</h3>
                </div>
                <p>{capability.body}</p>
                <code>{capability.code}</code>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section section--paper audience-section">
        <div className="container audience-grid">
          <article className="audience-panel audience-panel--player">
            <p className="eyebrow eyebrow--dark">I USE THE PARADOX LAUNCHER</p>
            <h2>I just want my mod translated.</h2>
            <p>
              Start with the installer, a provider key, and a guided project workflow.
              No command line. No repository archaeology.
            </p>
            <ButtonLink href={sitePath('guide/')} tone="paper">Open the beginner guide</ButtonLink>
          </article>
          <article className="audience-panel audience-panel--engineer">
            <p className="eyebrow">I EVALUATE AI ENGINEERING</p>
            <h2>I want the contracts, failure modes, and roadmap.</h2>
            <p>
              Inspect the retrieval boundary, schema-bound Copilot design, agent
              benchmarks, validation loops, and links back to source.
            </p>
            <ButtonLink href={sitePath('engineering/')} tone="dark">Open AI Engineering</ButtonLink>
          </article>
        </div>
      </section>

      <section className="section section--signal">
        <div className="container closing-grid">
          <div>
            <p className="eyebrow">WHAT COMES NEXT</p>
            <MeasuredText as="h2" className="section-title">
              A safe Copilot for the people who need the most help.
            </MeasuredText>
          </div>
          <div>
            <p>
              The planned Micro-RAG and PydanticAI layers target real beginner pain:
              provider setup, logs, fake localization, validation errors, and safe
              suggested actions. Remis remains the execution engine.
            </p>
            <div className="inline-links">
              <TextLink href={sitePath('roadmap/')}>Read the roadmap</TextLink>
              <TextLink href={links.issue132} external>Follow issue #132</TextLink>
            </div>
          </div>
        </div>
      </section>
    </SiteShell>
  )
}
