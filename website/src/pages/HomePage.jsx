import { MeasuredText } from '../components/MeasuredText'
import { ButtonLink, SiteShell, TextLink } from '../components/SiteShell'
import {
  assetPath,
  links,
  pipeline,
  productLayers,
  proofPoints,
  sitePath,
} from '../site'

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

function ProductLayers() {
  return (
    <div className="product-layer-ledger" role="list" aria-label="Remis product layers and delivery status">
      {productLayers.map((layer) => (
        <article className="product-layer" key={layer.title} role="listitem">
          <span className="product-layer__index">{layer.index}</span>
          <div className="product-layer__identity">
            <span>{layer.eyebrow}</span>
            <strong className={`delivery-state delivery-state--${layer.status.toLowerCase().replaceAll(' ', '-')}`}>
              {layer.status}
            </strong>
          </div>
          <div className="product-layer__copy">
            <h3>{layer.title}</h3>
            <p>{layer.body}</p>
          </div>
          <code>{layer.code}</code>
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
            <div className="runtime-status" role="status">
              <span aria-hidden="true"></span>
              OPEN SOURCE · WINDOWS DESKTOP · CLOUD OR LOCAL MODELS
            </div>
            <MeasuredText className="display-heading display-heading--product">
              The operating system for AI localization.
            </MeasuredText>
            <p className="hero-lead">
              Remis turns Paradox game files into glossary-aware, reviewable localization
              through a controlled LLM workflow. Project files, terminology, and review
              history are managed on your machine, while inference can use cloud APIs,
              Ollama, or OpenAI-compatible endpoints.
            </p>
            <div className="hero-actions">
              <ButtonLink href={links.releases} tone="accent" external>Download for Windows</ButtonLink>
              <ButtonLink href={sitePath('engineering/')} tone="dark">Explore AI Engineering</ButtonLink>
            </div>
            <div className="system-signals" aria-label="System principles">
              <div><strong>6-stage</strong><span>governed workflow</span></div>
              <div><strong>provider-flexible</strong><span>cloud or local inference</span></div>
              <div><strong>human-controlled</strong><span>review before deployment</span></div>
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
              <span>REAL PRODUCT · PUBLIC RELEASES</span>
              <span>Tauri · React · FastAPI · SQLite · LLM APIs</span>
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
              <p className="eyebrow">CAPABILITIES · DELIVERY STATUS</p>
              <MeasuredText as="h2" className="section-title">
                Built like a product. Explained like a system.
              </MeasuredText>
            </div>
            <p>
              The shipped workflow is the product core. RAG and agent layers extend it
              through explicit boundaries, not by replacing it with a free-roaming bot.
            </p>
          </div>
          <ProductLayers />
          <TextLink href={sitePath('roadmap/')}>See what is shipped, in development, and planned</TextLink>
        </div>
      </section>

      <section className="section section--boundary">
        <div className="container inference-boundary">
          <div className="inference-boundary__copy">
            <p className="eyebrow">LOCAL PROJECT CONTROL · PROVIDER-FLEXIBLE INFERENCE</p>
            <MeasuredText as="h2" className="section-title section-title--compact">
              Your workspace stays local. Your model choice stays open.
            </MeasuredText>
            <p>
              Remis runs as a desktop application and keeps project state in the local
              workspace. When you choose a cloud provider, the context required for that
              model request is sent to that provider. A hosted Remis account or cloud
              project workspace is never required.
            </p>
          </div>
          <div className="provider-boundary" aria-label="Remis model provider boundary">
            <div className="provider-boundary__local">
              <span>ON YOUR MACHINE</span>
              <strong>Remis workspace</strong>
              <ul>
                <li>Project files and mappings</li>
                <li>Glossaries and review history</li>
                <li>Validation and deployment state</li>
              </ul>
            </div>
            <div className="provider-boundary__bridge" aria-hidden="true">
              <span>required prompt context</span>
              <b>→</b>
            </div>
            <div className="provider-boundary__models">
              <span>YOU CHOOSE THE ENDPOINT</span>
              <strong>Model inference</strong>
              <ul>
                <li>Cloud APIs</li>
                <li>Ollama</li>
                <li>OpenAI-compatible services</li>
              </ul>
            </div>
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
