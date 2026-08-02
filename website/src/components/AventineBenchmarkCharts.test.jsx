import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { AventineBenchmarkCharts } from './AventineBenchmarkCharts'

describe('Aventine benchmark charts', () => {
  it('localizes the complete chart surface', () => {
    const markup = renderToStaticMarkup(<AventineBenchmarkCharts locale="zh" onSelect={() => {}} />)

    expect(markup).toContain('智力指数')
    expect(markup).toContain('每 100 题成本')
    expect(markup).toContain('端到端耗时包含服务商排队与网络传输')
    expect(markup).toContain('免费档表示测试当日的服务商福利')
    expect(markup).toContain('Qwen 3.7 Plus')
    expect(markup).toContain('TranslateGemma 27B')
    expect(markup).toContain('本地 GPU')
    expect(markup).toContain('TranslateGemma 27B · 成本未排名')
    expect(markup).not.toContain('aria-label="TranslateGemma 27B: 39.29 score')
    expect(markup).not.toContain('Most attractive quadrant')
  })

  it('keeps scatter points interactive and draws a coordinate-aware frontier', () => {
    const markup = renderToStaticMarkup(<AventineBenchmarkCharts locale="en" onSelect={() => {}} />)

    expect(markup).toContain('role="group"')
    expect(markup).not.toContain('role="img"')
    expect(markup).toContain('class="aa-scatter__point"')
    expect(markup).toContain('aria-label="Model key"')
    expect(markup).toContain('Gemini 3.6 Flash')
    expect(markup).toContain('preserveAspectRatio="none"')
    expect(markup).toContain('<polyline')
  })
})
