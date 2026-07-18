import { EngineeringPage } from './pages/EngineeringPage'
import { GuidePage } from './pages/GuidePage'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { RoadmapPage } from './pages/RoadmapPage'
import { AventinePage } from './pages/AventinePage'
import { CodexPage } from './pages/CodexPage'

const pageComponents = {
  home: HomePage,
  engineering: EngineeringPage,
  aventine: AventinePage,
  codex: CodexPage,
  guide: GuidePage,
  roadmap: RoadmapPage,
  notFound: NotFoundPage,
}

export function App({ page }) {
  const Page = pageComponents[page] ?? NotFoundPage
  return <Page />
}
