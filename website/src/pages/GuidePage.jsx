import { MeasuredText } from '../components/MeasuredText'
import { ButtonLink, SiteShell, TextLink } from '../components/SiteShell'
import { assetPath, guideSteps, links, sitePath } from '../site'

const questions = [
  {
    question: 'Do I need to know Python?',
    answer: 'No. Use the Windows installer and the guided desktop interface. The source code is there for contributors, not as an installation requirement.',
  },
  {
    question: 'Do I need an AI API key?',
    answer: 'Usually, yes. You can use a supported cloud provider or a compatible local model. Remis stores provider configuration locally.',
  },
  {
    question: 'Why does my translation not appear in game?',
    answer: 'The most common cause is fake localization in the original mod or the wrong launcher load order. The translated mod should load after the original mod.',
  },
  {
    question: 'Will Remis replace my existing translation?',
    answer: 'Incremental workflows are designed to preserve existing work and process new text. Always review the selected mode before starting a run.',
  },
]

export function GuidePage() {
  return (
    <SiteShell activePage="guide" theme="paper">
      <section className="page-hero page-hero--guide">
        <div className="container guide-hero-grid">
          <div>
            <p className="eyebrow eyebrow--dark">BEGINNER GUIDE · NO COMMAND LINE REQUIRED</p>
            <MeasuredText className="display-heading display-heading--page display-heading--dark">
              From installer to a working localization mod.
            </MeasuredText>
            <p className="hero-lead hero-lead--dark">
              If you can install a Paradox mod and use the launcher, you can use Remis.
              The AI system stays behind a project workflow with visible progress and
              proofreading before deployment.
            </p>
            <div className="hero-actions">
              <ButtonLink href={links.releases} tone="ink" external>Download the latest installer</ButtonLink>
              <ButtonLink href={links.documentation} tone="paper" external>Open full documentation</ButtonLink>
            </div>
          </div>
          <figure className="guide-figure">
            <img src={assetPath('screenshot-en-2.webp')} alt="Remis project status screen" />
            <figcaption>Everything starts from a project, not a folder full of scripts.</figcaption>
          </figure>
        </div>
      </section>

      <section className="section section--paper guide-steps-section">
        <div className="container">
          <div className="section-heading section-heading--split">
            <div>
              <p className="eyebrow eyebrow--dark">FIVE STEPS</p>
              <MeasuredText as="h2" className="section-title">
                The shortest path through the product.
              </MeasuredText>
            </div>
            <p>
              Remis includes demo mods for supported Paradox games, so you can learn the
              workflow before pointing it at a real project.
            </p>
          </div>

          <ol className="guide-steps">
            {guideSteps.map((step) => (
              <li key={step.number}>
                <span className="guide-step__number">{step.number}</span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.summary}</p>
                </div>
                <TextLink href={step.href} external={step.href.startsWith('http')}>{step.action}</TextLink>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="section section--ink launcher-section">
        <div className="container launcher-grid">
          <div>
            <p className="eyebrow">THE ONE LAUNCHER RULE TO REMEMBER</p>
            <MeasuredText as="h2" className="section-title">
              Load the localization mod after the original mod.
            </MeasuredText>
          </div>
          <div className="load-order" aria-label="Correct launcher load order">
            <div><span>01</span><strong>Original mod</strong><small>gameplay and source localization</small></div>
            <div><span>02</span><strong>Remis localization</strong><small>translated files override the originals</small></div>
          </div>
        </div>
      </section>

      <section className="section section--paper">
        <div className="container faq-grid">
          <div>
            <p className="eyebrow eyebrow--dark">COMMON QUESTIONS</p>
            <MeasuredText as="h2" className="section-title">
              The answers people need before they need an architecture diagram.
            </MeasuredText>
          </div>
          <div className="faq-list">
            {questions.map((item) => (
              <details key={item.question}>
                <summary>{item.question}</summary>
                <p>{item.answer}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="section section--signal">
        <div className="container closing-grid">
          <div>
            <p className="eyebrow">NEED MORE HELP?</p>
            <h2>Use the docs today. Ask the Remis Copilot tomorrow.</h2>
          </div>
          <div>
            <p>
              The planned Micro-RAG assistant is aimed directly at setup, logs, fake
              localization, and validation explanations. Until then, the documentation
              and community remain the source of truth.
            </p>
            <div className="inline-links">
              <TextLink href={links.documentation} external>Browse documentation</TextLink>
              <TextLink href={links.discussions} external>Ask the community</TextLink>
              <TextLink href={sitePath('roadmap/')}>See the Copilot roadmap</TextLink>
            </div>
          </div>
        </div>
      </section>
    </SiteShell>
  )
}
