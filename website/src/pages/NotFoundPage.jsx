import { ButtonLink, SiteShell } from '../components/SiteShell'
import { useI18n } from '../i18n/context'
import { sitePath } from '../site'

export function NotFoundPage() {
  const { t } = useI18n()
  return (
    <SiteShell activePage="">
      <section className="not-found">
        <div className="container">
          <p className="eyebrow">{t('404 · VALIDATION FAILED')}</p>
          <h1>{t('This route is not part of the workflow.')}</h1>
          <p>{t('The page may have moved, or the URL may contain a localization error of its own.')}</p>
          <ButtonLink href={sitePath()} tone="accent">Return to Remis</ButtonLink>
        </div>
      </section>
    </SiteShell>
  )
}
