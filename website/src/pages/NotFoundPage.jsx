import { ButtonLink, SiteShell } from '../components/SiteShell'
import { sitePath } from '../site'

export function NotFoundPage() {
  return (
    <SiteShell activePage="">
      <section className="not-found">
        <div className="container">
          <p className="eyebrow">404 · VALIDATION FAILED</p>
          <h1>This route is not part of the workflow.</h1>
          <p>The page may have moved, or the URL may contain a localization error of its own.</p>
          <ButtonLink href={sitePath()} tone="accent">Return to Remis</ButtonLink>
        </div>
      </section>
    </SiteShell>
  )
}
