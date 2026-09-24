import { MeasuredText } from '../components/MeasuredText'
import { ButtonLink, SiteShell, TextLink } from '../components/SiteShell'
import { translateDeep, useI18n } from '../i18n/context'
import {
  assetPath,
  links,
  pipeline,
  productLayers,
  proofPoints,
  sitePath,
} from '../site'

function ProofStrip() {
  const { t } = useI18n()
  const localizedProofPoints = translateDeep(proofPoints, t)
  return (
    <section className="proof-strip" aria-label={t('Project evidence')}>
      <div className="container proof-grid">
        {localizedProofPoints.map((point) => (
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
  const { t } = useI18n()
  const localizedPipeline = translateDeep(pipeline, t)
  return (
    <div className="pipeline" role="list" aria-label={t('Remis localization pipeline')}>
      {localizedPipeline.map((step) => (
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
  const { t } = useI18n()
  const localizedProductLayers = translateDeep(productLayers, t)
  return (
    <div className="product-layer-ledger" role="list" aria-label={t('Remis product layers and delivery status')}>
      {localizedProductLayers.map((layer, index) => (
        <article className="product-layer" key={layer.title} role="listitem">
          <span className="product-layer__index">{layer.index}</span>
          <div className="product-layer__identity">
            <span>{layer.eyebrow}</span>
            <strong className={`delivery-state delivery-state--${productLayers[index].status.toLowerCase().replaceAll(' ', '-')}`}>
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

const projectArchiveCopy = {
  en: {
    eyebrow: 'PROJECT ARCHIVE · CONTEXT ENGINEERING',
    title: 'Turn a mod into a versioned context system.',
    body: 'The Project Archive does more than save summaries. It structures terminology, people, places, organizations, and event chains into immutable Context Releases with source evidence, draft inheritance, stale detection, and human review.',
    action: 'Read the Project Archive guide',
    href: links.archiveGuideEn,
    stages: [
      ['STRUCTURE', 'Extract project, entity, and event knowledge from source localization.'],
      ['TRACE', 'Keep source paths, citations, coverage, and provenance attached to published results.'],
      ['VERSION', 'Publish immutable releases, branch editable drafts, and preserve parentage instead of overwriting history.'],
      ['REUSE', 'Use a readiness-checked release in translation, and expose bounded published context to Agent reads.'],
    ],
  },
  zh: {
    eyebrow: '项目档案馆 · CONTEXT ENGINEERING',
    title: '把一个 Mod 变成有版本的上下文系统。',
    body: '项目档案馆不只是保存摘要。它把术语、人物、地点、组织与事件链整理成不可变的 Context Release，并把来源证据、草稿继承、过期检测和人工审阅一起纳入系统。',
    action: '阅读项目档案馆指南',
    href: links.archiveGuideZh,
    stages: [
      ['结构化', '从本地化源文件中提取项目、实体与事件知识。'],
      ['可追溯', '让来源路径、引用、覆盖率与 provenance 始终跟随发布结果。'],
      ['版本化', '发布不可变版本，从版本继承可编辑草稿，不用覆盖历史。'],
      ['可复用', '翻译使用经过就绪检查的版本，Agent 则读取受限的已发布上下文。'],
    ],
  },
}

function ProjectArchiveSection() {
  const { locale } = useI18n()
  const copy = projectArchiveCopy[locale === 'zh' ? 'zh' : 'en']

  return (
    <section className="section section--signal">
      <div className="container benchmark-grid">
        <div>
          <p className="eyebrow">{copy.eyebrow}</p>
          <MeasuredText as="h2" className="section-title">{copy.title}</MeasuredText>
          <p>{copy.body}</p>
          <TextLink href={copy.href} external>{copy.action}</TextLink>
        </div>
        <div className="metric-ledger" aria-label={copy.eyebrow}>
          {copy.stages.map(([stage, detail], index) => (
            <div key={stage}>
              <span>0{index + 1}</span>
              <code>{stage}</code>
              <p>{detail}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export function HomePage() {
  const { t } = useI18n()
  return (
    <SiteShell activePage="home">
      <section className="hero hero--home">
        <div className="container hero-grid">
          <div className="hero-copy">
            <MeasuredText className="display-heading display-heading--product">
              {t('The operating system for AI localization.')}
            </MeasuredText>
            <p className="hero-lead">
              {t('Remis turns Paradox game files into glossary-aware, reviewable localization through a controlled LLM workflow. Project files, terminology, and review history are managed on your machine, while inference can use cloud APIs, Ollama, or OpenAI-compatible endpoints.')}
            </p>
            <div className="hero-actions">
              <ButtonLink href={links.releases} tone="accent" external>Download for Windows</ButtonLink>
              <ButtonLink href={sitePath('codex/')} tone="agent">Use with an AI Agent</ButtonLink>
              <ButtonLink href={sitePath('engineering/')} tone="dark">Explore AI Engineering</ButtonLink>
            </div>
            <div className="system-signals" aria-label={t('System principles')}>
              <div><strong>{t('6-stage')}</strong><span>{t('governed workflow')}</span></div>
              <div><strong>{t('provider-flexible')}</strong><span>{t('cloud or local inference')}</span></div>
              <div><strong>{t('human-controlled')}</strong><span>{t('review before deployment')}</span></div>
            </div>
          </div>

          <figure className="product-stage">
            <div className="product-stage__frame">
              <div className="product-stage__bar">
                <span></span><span></span><span></span>
                <small>{t('Remis project workspace')}</small>
              </div>
              <img
                src={assetPath('screenshot-en-1.webp')}
                alt={t('Remis desktop application showing the project workspace')}
              />
            </div>
            <figcaption>
              <span>{t('REAL PRODUCT · PUBLIC RELEASES')}</span>
              <span>{t('Tauri · React · FastAPI · SQLite · LLM APIs')}</span>
            </figcaption>
          </figure>
        </div>
      </section>

      <ProofStrip />

      <section className="section section--paper">
        <div className="container">
          <div className="section-heading section-heading--split">
            <div>
              <p className="eyebrow eyebrow--dark">{t('THE WORKFLOW')}</p>
              <MeasuredText as="h2" className="section-title">
                {t('AI where it helps. Deterministic checks where trust matters.')}
              </MeasuredText>
            </div>
            <p>
              {t('Remis does not ask users to trust a chat window with their mod folder. Every model call sits inside a visible product workflow with explicit inputs, validation, recovery, and review.')}
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
              <p className="eyebrow">{t('CAPABILITIES · DELIVERY STATUS')}</p>
              <MeasuredText as="h2" className="section-title">
                {t('Built like a product. Explained like a system.')}
              </MeasuredText>
            </div>
            <p>
              {t('The shipped workflow is the product core. RAG and agent layers extend it through explicit boundaries, not by replacing it with a free-roaming bot.')}
            </p>
          </div>
          <ProductLayers />
          <TextLink href={sitePath('roadmap/')}>See what is shipped, in development, and planned</TextLink>
        </div>
      </section>

      <ProjectArchiveSection />

      <section className="section section--boundary">
        <div className="container inference-boundary">
          <div className="inference-boundary__copy">
            <p className="eyebrow">{t('LOCAL PROJECT CONTROL · PROVIDER-FLEXIBLE INFERENCE')}</p>
            <MeasuredText as="h2" className="section-title section-title--compact">
              {t('Your workspace stays local. Your model choice stays open.')}
            </MeasuredText>
            <p>
              {t('Remis runs as a desktop application and keeps project state in the local workspace. When you choose a cloud provider, the context required for that model request is sent to that provider. A hosted Remis account or cloud project workspace is never required.')}
            </p>
          </div>
          <div className="provider-boundary" aria-label={t('Remis model provider boundary')}>
            <div className="provider-boundary__local">
              <span>{t('ON YOUR MACHINE')}</span>
              <strong>{t('Remis workspace')}</strong>
              <ul>
                <li>{t('Project files and mappings')}</li>
                <li>{t('Glossaries and review history')}</li>
                <li>{t('Validation and deployment state')}</li>
              </ul>
            </div>
            <div className="provider-boundary__bridge" aria-hidden="true">
              <span>{t('required prompt context')}</span>
              <b>→</b>
            </div>
            <div className="provider-boundary__models">
              <span>{t('YOU CHOOSE THE ENDPOINT')}</span>
              <strong>{t('Model inference')}</strong>
              <ul>
                <li>{t('Cloud APIs')}</li>
                <li>Ollama</li>
                <li>{t('OpenAI-compatible services')}</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="section section--paper audience-section">
        <div className="container audience-grid">
          <article className="audience-panel audience-panel--player">
            <p className="eyebrow eyebrow--dark">{t('I USE THE PARADOX LAUNCHER')}</p>
            <h2>{t('I just want my mod translated.')}</h2>
            <p>
              {t('Start with the installer, a provider key, and a guided project workflow. No command line. No repository archaeology.')}
            </p>
            <ButtonLink href={sitePath('guide/')} tone="paper">Open the beginner guide</ButtonLink>
          </article>
          <article className="audience-panel audience-panel--engineer">
            <p className="eyebrow">{t('I EVALUATE AI ENGINEERING')}</p>
            <h2>{t('I want the contracts, failure modes, and roadmap.')}</h2>
            <p>
              {t('Inspect the retrieval boundary, schema-bound Copilot design, agent benchmarks, validation loops, and links back to source.')}
            </p>
            <ButtonLink href={sitePath('engineering/')} tone="dark">Open AI Engineering</ButtonLink>
          </article>
        </div>
      </section>

    </SiteShell>
  )
}
