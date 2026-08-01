import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { AventineBenchmarkCharts } from './AventineBenchmarkCharts'

describe('Aventine benchmark charts', () => {
  it('localizes the complete chart surface', () => {
    const markup = renderToStaticMarkup(<AventineBenchmarkCharts locale="zh" onSelect={() => {}} />)

    expect(markup).toContain('智力指数')
    expect(markup).toContain('每 100 题成本')
    expect(markup).toContain('端到端耗时包含服务商排队与网络传输')
    expect(markup).toContain('免费档点位表示本轮使用了服务商福利')
    expect(markup).not.toContain('Most attractive quadrant')
  })

  it('keeps scatter points interactive and draws a coordinate-aware frontier', () => {
    const markup = renderToStaticMarkup(<AventineBenchmarkCharts locale="en" onSelect={() => {}} />)

    expect(markup).toContain('role="group"')
    expect(markup).not.toContain('role="img"')
    expect(markup).toContain('class="aa-scatter__point"')
    expect(markup).toContain('preserveAspectRatio="none"')
    expect(markup).toContain('<polyline')
  })
})
