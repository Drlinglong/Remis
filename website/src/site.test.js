import { describe, expect, it } from 'vitest'
import { pageFromPath, roadmapPhases, SITE_BASE } from './site'

describe('pageFromPath', () => {
  it.each([
    ['/Remis/', 'home'],
    ['/Remis/index.html', 'home'],
    ['/Remis/engineering/', 'engineering'],
    ['/Remis/guide/', 'guide'],
    ['/Remis/roadmap/', 'roadmap'],
    ['/Remis/not-a-page/', 'notFound'],
  ])('maps %s to %s', (path, page) => {
    expect(pageFromPath(path, SITE_BASE)).toBe(page)
  })
})

describe('roadmap content', () => {
  it('labels every future-facing claim with a delivery status', () => {
    expect(roadmapPhases.every((phase) => phase.status && phase.version)).toBe(true)
  })
})
