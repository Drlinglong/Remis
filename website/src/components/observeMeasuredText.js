import { layout, prepare } from '@chenglou/pretext'

export function observeMeasuredText({
  element,
  text,
  fontsReady,
  onHeight,
  getStyle = window.getComputedStyle,
  Observer = ResizeObserver,
  prepareText = prepare,
  layoutText = layout,
}) {
  let cancelled = false
  let observer
  let prepared

  const measure = () => {
    const styles = getStyle(element)
    const lineHeight = Number.parseFloat(styles.lineHeight)
    prepared ??= prepareText(text, styles.font)
    const result = layoutText(prepared, element.clientWidth, lineHeight)
    onHeight(Math.ceil(result.height + 2))
  }

  fontsReady.then(() => {
    if (cancelled) return
    measure()
    observer = new Observer(measure)
    observer.observe(element)
  })

  return () => {
    cancelled = true
    observer?.disconnect()
  }
}
