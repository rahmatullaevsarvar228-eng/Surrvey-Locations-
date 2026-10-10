import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import type { Data, Layout } from 'plotly.js'

export default function Plot({ data, layout, height = 380, onClickX }: {
  data: Data[]; layout: Partial<Layout>; height?: number; onClickX?: (x: number) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    Plotly.react(el, data, { ...layout, height, autosize: true },
      { displayModeBar: false, responsive: true })
  }, [data, layout, height])
  useEffect(() => {
    const el = ref.current as (HTMLDivElement & { on?: (ev: string, cb: (e: { points: { x: number }[] }) => void) => void }) | null
    if (!el || !onClickX || !el.on) return
    el.on('plotly_click', (e) => { if (e.points?.[0]) onClickX(Number(e.points[0].x)) })
  }, [onClickX])
  useEffect(() => {
    const el = ref.current
    return () => { if (el) Plotly.purge(el) }
  }, [])
  return <div ref={ref} style={{ width: '100%', height }} />
}
