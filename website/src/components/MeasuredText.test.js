import { describe, expect, it, vi } from 'vitest'
import { observeMeasuredText } from './observeMeasuredText'

function deferred() {
  let resolve
  const promise = new Promise((complete) => {
    resolve = complete
  })
  return { promise, resolve }
}

describe('observeMeasuredText', () => {
  it('waits for web fonts before preparing text metrics and then reuses them on resize', async () => {
    const fonts = deferred()
    const element = { clientWidth: 720 }
    const prepared = { id: 'prepared-with-loaded-font' }
    const prepareText = vi.fn(() => prepared)
    const layoutText = vi.fn(() => ({ height: 300.2 }))
    const onHeight = vi.fn()
    let resize
    const disconnect = vi.fn()
    const observe = vi.fn()
    const Observer = vi.fn(function Observer(callback) {
      resize = callback
      return { observe, disconnect }
    })

    const cleanup = observeMeasuredText({
      element,
      text: 'The operating system for AI localization.',
      fontsReady: fonts.promise,
      onHeight,
      getStyle: () => ({ font: '700 102px Manrope', lineHeight: '100px' }),
      Observer,
      prepareText,
      layoutText,
    })

    expect(prepareText).not.toHaveBeenCalled()
    expect(Observer).not.toHaveBeenCalled()

    fonts.resolve()
    await fonts.promise
    await Promise.resolve()

    expect(prepareText).toHaveBeenCalledOnce()
    expect(layoutText).toHaveBeenCalledWith(prepared, 720, 100)
    expect(onHeight).toHaveBeenCalledWith(303)
    expect(observe).toHaveBeenCalledWith(element)

    element.clientWidth = 640
    resize()
    expect(prepareText).toHaveBeenCalledOnce()
    expect(layoutText).toHaveBeenLastCalledWith(prepared, 640, 100)

    cleanup()
    expect(disconnect).toHaveBeenCalledOnce()
  })

  it('does not start measuring after unmount while fonts are still loading', async () => {
    const fonts = deferred()
    const prepareText = vi.fn()
    const Observer = vi.fn()
    const cleanup = observeMeasuredText({
      element: { clientWidth: 720 },
      text: 'Deferred heading',
      fontsReady: fonts.promise,
      onHeight: vi.fn(),
      getStyle: vi.fn(),
      Observer,
      prepareText,
      layoutText: vi.fn(),
    })

    cleanup()
    fonts.resolve()
    await fonts.promise
    await Promise.resolve()

    expect(prepareText).not.toHaveBeenCalled()
    expect(Observer).not.toHaveBeenCalled()
  })
})
