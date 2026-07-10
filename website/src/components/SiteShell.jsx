import { pages, sitePath, links } from '../site'

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span>R</span>
    </span>
  )
}

function Arrow({ external = false }) {
  return <span aria-hidden="true">{external ? '↗' : '→'}</span>
}

export function TextLink({ href, children, external = false, className = '' }) {
  return (
    <a
      className={`text-link ${className}`.trim()}
      href={href}
      {...(external ? { target: '_blank', rel: 'noreferrer' } : {})}
    >
      <span>{children}</span>
      <Arrow external={external} />
    </a>
  )
}

export function ButtonLink({ href, children, tone = 'light', external = false }) {
  return (
    <a
      className={`button-link button-link--${tone}`}
      href={href}
      {...(external ? { target: '_blank', rel: 'noreferrer' } : {})}
    >
      <span>{children}</span>
      <Arrow external={external} />
    </a>
  )
}

export function StatusPill({ children }) {
  const normalized = children.toLowerCase().replaceAll(' ', '-')
  return <span className={`status-pill status-pill--${normalized}`}>{children}</span>
}

function Header({ activePage }) {
  return (
    <header className="site-header">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <div className="container nav-row">
        <a className="brand" href={sitePath()} aria-label="Remis home">
          <BrandMark />
          <span className="brand-name">REMIS</span>
        </a>

        <nav className="desktop-nav" aria-label="Primary navigation">
          {pages.map((page) => (
            <a
              key={page.key}
              className={activePage === page.key ? 'is-active' : ''}
              href={sitePath(page.path)}
              aria-current={activePage === page.key ? 'page' : undefined}
            >
              {page.label}
            </a>
          ))}
        </nav>

        <a className="github-link" href={links.github} target="_blank" rel="noreferrer">
          GitHub <Arrow external />
        </a>

        <details className="mobile-nav">
          <summary aria-label="Open navigation">Menu</summary>
          <nav aria-label="Mobile navigation">
            {pages.map((page) => (
              <a key={page.key} href={sitePath(page.path)}>{page.label}</a>
            ))}
            <a href={links.github} target="_blank" rel="noreferrer">GitHub ↗</a>
          </nav>
        </details>
      </div>
    </header>
  )
}

function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div>
          <div className="footer-brand"><BrandMark /><strong>REMIS</strong></div>
          <p>Open-source desktop AI orchestration for Paradox mod localization.</p>
        </div>
        <div>
          <span className="footer-label">Explore</span>
          <a href={sitePath('engineering/')}>AI Engineering</a>
          <a href={sitePath('guide/')}>Beginner Guide</a>
          <a href={sitePath('roadmap/')}>Roadmap</a>
        </div>
        <div>
          <span className="footer-label">Project</span>
          <a href={links.releases}>Releases</a>
          <a href={links.documentation}>Documentation</a>
          <a href={links.discussions}>Discussions</a>
        </div>
        <div className="builder-note">
          <span className="footer-label">Built by Linglong</span>
          <p>Applied AI / LLM Workflow Engineer<br />Engineering PhD</p>
          <a href={links.github}>GitHub ↗</a>
        </div>
      </div>
      <div className="container footer-floor">
        <span>AGPL-3.0 code · CC BY-NC-SA 4.0 data and documentation</span>
        <span>Human review is a feature, not an afterthought.</span>
      </div>
    </footer>
  )
}

export function SiteShell({ activePage, children, theme = 'dark' }) {
  return (
    <div className={`site site--${theme}`}>
      <Header activePage={activePage} />
      <main id="main-content">{children}</main>
      <Footer />
    </div>
  )
}
