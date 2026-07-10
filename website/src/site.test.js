import { describe, expect, it } from 'vitest'
import {
  pageFromPath,
  productLayers,
  roadmapPhases,
  SITE_BASE,
  workflowDiagrams,
} from './site'

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

describe('product positioning content', () => {
  it('labels every product layer with a delivery status', () => {
    expect(productLayers.map((layer) => layer.status)).toEqual([
      'Shipped',
      'Planned',
      'Planned',
    ])
  })

  it('documents every workflow with its trust-boundary questions', () => {
    expect(workflowDiagrams).toHaveLength(3)
    expect(workflowDiagrams.every((workflow) => (
      workflow.asset
      && workflow.input
      && workflow.state
      && workflow.model
      && workflow.recovery
    ))).toBe(true)
  })
})
