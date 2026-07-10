import { layout, prepare } from '@chenglou/pretext'
import { useLayoutEffect, useRef, useState } from 'react'

export function MeasuredText({ as: Tag = 'h1', children, className = '' }) {
  const ref = useRef(null)
  const [height, setHeight] = useState(null)

  useLayoutEffect(() => {
    const element = ref.current
    if (!element || typeof children !== 'string') return undefined

    let prepared

    const measure = () => {
      const styles = window.getComputedStyle(element)
      const lineHeight = Number.parseFloat(styles.lineHeight)
      prepared ??= prepare(children, styles.font)
      const result = layout(prepared, element.clientWidth, lineHeight)
      setHeight(Math.ceil(result.height + 2))
    }

    document.fonts.ready.then(measure)
    const observer = new ResizeObserver(measure)
    observer.observe(element)

    return () => observer.disconnect()
  }, [children])

  return (
    <Tag
      ref={ref}
      className={className}
      style={height ? { minHeight: `${height}px` } : undefined}
    >
      {children}
    </Tag>
  )
}
