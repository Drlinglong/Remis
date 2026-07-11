import { pages, sitePath, links } from '../site'
import { useI18n } from '../i18n/context'

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
  const { t } = useI18n()
  return (
    <a
      className={`text-link ${className}`.trim()}
      href={href}
      {...(external ? { target: '_blank', rel: 'noreferrer' } : {})}
    >
      <span>{typeof children === 'string' ? t(children) : children}</span>
      <Arrow external={external} />
    </a>
  )
}

export function ButtonLink({ href, children, tone = 'light', external = false }) {
  const { t } = useI18n()
  return (
    <a
      className={`button-link button-link--${tone}`}
      href={href}
      {...(external ? { target: '_blank', rel: 'noreferrer' } : {})}
    >
      <span>{typeof children === 'string' ? t(children) : children}</span>
      <Arrow external={external} />
    </a>
  )
}

export function StatusPill({ children }) {
  const { t } = useI18n()
  const normalized = children.toLowerCase().replaceAll(' ', '-')
  return <span className={`status-pill status-pill--${normalized}`}>{t(children)}</span>
}

function LanguageSelector() {
  const { locale, setLocale, supportedLocales, t } = useI18n()

  return (
    <label className="language-selector">
      <span className="sr-only">{t('Select language')}</span>
      <select
        aria-label={t('Select language')}
        value={locale}
        onChange={(event) => setLocale(event.target.value)}
      >
        {supportedLocales.map((language) => (
          <option key={language.code} value={language.code}>{language.label}</option>
        ))}
      </select>
    </label>
  )
}

function Header({ activePage }) {
  const { t } = useI18n()
  return (
    <header className="site-header">
      <a className="skip-link" href="#main-content">{t('Skip to content')}</a>
      <div className="container nav-row">
        <a className="brand" href={sitePath()} aria-label={t('Remis home')}>
          <BrandMark />
          <span className="brand-name">REMIS</span>
        </a>

        <nav className="desktop-nav" aria-label={t('Primary navigation')}>
          {pages.map((page) => (
            <a
              key={page.key}
              className={activePage === page.key ? 'is-active' : ''}
              href={sitePath(page.path)}
              aria-current={activePage === page.key ? 'page' : undefined}
            >
              {t(page.label)}
            </a>
          ))}
        </nav>

        <a className="github-link" href={links.github} target="_blank" rel="noreferrer">
          {t('GitHub')} <Arrow external />
        </a>

        <LanguageSelector />

        <details className="mobile-nav">
          <summary aria-label={t('Open navigation')}>{t('Menu')}</summary>
          <nav aria-label={t('Mobile navigation')}>
            {pages.map((page) => (
              <a key={page.key} href={sitePath(page.path)}>{t(page.label)}</a>
            ))}
            <a href={links.github} target="_blank" rel="noreferrer">{t('GitHub')} ↗</a>
          </nav>
        </details>
      </div>
    </header>
  )
}

function Footer() {
  const { t } = useI18n()
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div>
          <div className="footer-brand"><BrandMark /><strong>REMIS</strong></div>
          <p>{t('Open-source desktop AI orchestration for Paradox mod localization.')}</p>
        </div>
        <div>
          <span className="footer-label">{t('Explore')}</span>
          <a href={sitePath('engineering/')}>{t('AI Engineering')}</a>
          <a href={sitePath('guide/')}>{t('Beginner Guide')}</a>
          <a href={sitePath('roadmap/')}>{t('Roadmap')}</a>
        </div>
        <div>
          <span className="footer-label">{t('Project')}</span>
          <a href={links.releases}>{t('Releases')}</a>
          <a href={links.documentation}>{t('Documentation')}</a>
          <a href={links.discussions}>{t('Discussions')}</a>
        </div>
        <div className="builder-note">
          <span className="footer-label">{t('Built by Linglong')}</span>
          <p>{t('Applied AI / LLM Workflow Engineer')}<br />{t('Engineering PhD')}</p>
          <a href={links.github}>{t('GitHub')} ↗</a>
        </div>
      </div>
      <div className="container footer-floor">
        <span>{t('AGPL-3.0 code · CC BY-NC-SA 4.0 data and documentation')}</span>
        <span>{t('Human review is a feature, not an afterthought.')}</span>
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
