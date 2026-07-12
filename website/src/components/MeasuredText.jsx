import { useLayoutEffect, useRef, useState } from 'react'
import { observeMeasuredText } from './observeMeasuredText'

export function MeasuredText({ as: Tag = 'h1', children, className = '' }) {
  const ref = useRef(null)
  const [height, setHeight] = useState(null)

  useLayoutEffect(() => {
    const element = ref.current
    if (!element || typeof children !== 'string') return undefined

    return observeMeasuredText({
      element,
      text: children,
      fontsReady: document.fonts.ready,
      onHeight: setHeight,
    })
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
