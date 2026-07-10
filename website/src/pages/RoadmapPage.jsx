import { MeasuredText } from '../components/MeasuredText'
import { ButtonLink, SiteShell, StatusPill, TextLink } from '../components/SiteShell'
import { links, roadmapPhases, sitePath } from '../site'

export function RoadmapPage() {
  return (
    <SiteShell activePage="roadmap">
      <section className="page-hero page-hero--roadmap">
        <div className="container page-hero__grid">
          <div>
            <p className="eyebrow">PUBLIC ROADMAP · CLAIMS WITH DELIVERY STATUS</p>
            <MeasuredText className="display-heading display-heading--page">
              What exists. What is moving. What is still a bet.
            </MeasuredText>
          </div>
          <div className="page-hero__aside">
            <p>
              Remis remains a localization product. RAG and agent systems earn their
              place by reducing setup pain, making quality visible, and removing
              repetitive work without weakening user control.
            </p>
            <ButtonLink href={links.issue132} tone="accent" external>Follow issue #132</ButtonLink>
          </div>
        </div>
      </section>

      <section className="section section--paper roadmap-section">
        <div className="container">
          <div className="roadmap-ledger">
            {roadmapPhases.map((phase, index) => (
              <article key={phase.title} className="roadmap-row">
                <span className="roadmap-row__index">0{index + 1}</span>
                <div className="roadmap-row__status">
                  <StatusPill>{phase.status}</StatusPill>
                  <code>{phase.version}</code>
                </div>
                <h2>{phase.title}</h2>
                <p>{phase.summary}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section section--ink roadmap-principles">
        <div className="container">
          <div className="section-heading section-heading--split">
            <div>
              <p className="eyebrow">THE LINE WE WILL NOT CROSS</p>
              <MeasuredText as="h2" className="section-title">
                No free-roaming autonomous agent in a beginner’s mod folder.
              </MeasuredText>
            </div>
            <p>
              The model may retrieve, explain, classify, plan, and suggest. Remis owns
              the action registry, validation, risk level, preview, confirmation, and
              execution.
            </p>
          </div>
          <div className="principle-sequence">
            <div><span>01</span><strong>READ</strong><small>documentation and approved context</small></div>
            <div><span>02</span><strong>PROPOSE</strong><small>typed answer, intent, or DAG</small></div>
            <div><span>03</span><strong>VERIFY</strong><small>schema, tools, arguments, and risk</small></div>
            <div><span>04</span><strong>CONFIRM</strong><small>visible UI gate before writes</small></div>
          </div>
        </div>
      </section>

      <section className="section section--paper roadmap-cta">
        <div className="container closing-grid closing-grid--dark-text">
          <div>
            <p className="eyebrow eyebrow--dark">OPEN DEVELOPMENT</p>
            <h2>Architecture notes live beside the code.</h2>
          </div>
          <div>
            <p>
              Follow the issue, inspect the repository, or start with the user workflow.
              The roadmap should make the project easier to judge, not harder to use.
            </p>
            <div className="inline-links">
              <TextLink href={links.issue132} external>Read issue #132</TextLink>
              <TextLink href={links.github} external>View source</TextLink>
              <TextLink href={sitePath('guide/')}>Open beginner guide</TextLink>
            </div>
          </div>
        </div>
      </section>
    </SiteShell>
  )
}
