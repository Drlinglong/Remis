import { EngineeringPage } from './pages/EngineeringPage'
import { GuidePage } from './pages/GuidePage'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { RoadmapPage } from './pages/RoadmapPage'

const pageComponents = {
  home: HomePage,
  engineering: EngineeringPage,
  guide: GuidePage,
  roadmap: RoadmapPage,
  notFound: NotFoundPage,
}

export function App({ page }) {
  const Page = pageComponents[page] ?? NotFoundPage
  return <Page />
}
