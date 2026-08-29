import { describe, expect, it } from 'vitest'
import {
  agentMilestones,
  aventineEvidence,
  aventineProofPoints,
  aventineRanking,
  aventineRecipeStages,
  links,
  navigationHref,
  pageFromPath,
  productLayers,
  roadmapPhases,
  SITE_BASE,
  workflowDiagrams,
  pages,
  proofPoints,
} from './site'

describe('pageFromPath', () => {
  it.each([
    ['/Remis/', 'home'],
    ['/Remis/index.html', 'home'],
    ['/Remis/engineering/', 'engineering'],
    ['/Remis/aventine/', 'aventine'],
    ['/Remis/codex/', 'codex'],
    ['/Remis/guide/', 'guide'],
    ['/Remis/roadmap/', 'roadmap'],
    ['/Remis/not-a-page/', 'notFound'],
  ])('maps %s to %s', (path, page) => {
    expect(pageFromPath(path, SITE_BASE)).toBe(page)
  })
})

describe('Codex product entry', () => {
  it('publishes a dedicated product route without replacing the main product identity', () => {
    expect(pages.find((page) => page.key === 'codex')).toMatchObject({
      label: 'Use with Codex',
      path: 'codex/',
    })
    expect(pages[0].key).toBe('home')
  })

  it('links developer resources to the durable main branch', () => {
    expect(links.agentQuickstart).toBe(
      'https://github.com/Drlinglong/Remis/blob/main/docs/en/developer/agent-api-quickstart.md',
    )
    expect(links.agentSkill).toBe(
      'https://github.com/Drlinglong/Remis/tree/main/.agents/skills/remis-agent',
    )
  })
})

describe('public evidence and navigation', () => {
  it('publishes the current release evidence snapshot', () => {
    expect(proofPoints.find((point) => point.label === 'Public releases')?.value).toBe('38')
    expect(proofPoints.find((point) => point.label === 'Installer downloads')?.value).toBe('600+')
  })

  it('routes Aventine navigation to the standalone benchmark site', () => {
    const aventinePage = pages.find((page) => page.key === 'aventine')

    expect(links.aventineSite).toBe('https://drlinglong.github.io/remis-aventine/')
    expect(navigationHref(aventinePage)).toBe(links.aventineSite)
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
      'In development',
      'In development',
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

  it('publishes the Agent delivery and Aventine evidence contracts', () => {
    expect(agentMilestones).toHaveLength(4)
    expect(aventineProofPoints).toHaveLength(4)
    expect(aventineRecipeStages).toHaveLength(3)
    expect(aventineRanking[0]).toMatchObject({
      recipe: 'Qwen 3.6 27B Q4_K_M',
      result: 'Champion',
    })
    expect(aventineEvidence).toHaveLength(4)
  })
})
