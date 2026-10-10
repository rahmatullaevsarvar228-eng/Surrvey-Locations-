import { useMemo } from 'react'
import type { Data, Layout, Shape, Annotations } from 'plotly.js'
import Plot from './Plot'
import { KIND_COLOR, hhmm } from '../data'
import { useT } from '../i18n'
import type { Disruption, Schedule, Station, Train, Deadlock } from '../types'

export const MARGIN = { l: 78, r: 12, t: 34, b: 62 }
const HEIGHT = 400

interface Props {
  title: string
  stations: Station[]
  trains: Train[]
  schedule: Schedule
  disruption?: Disruption | null
  deadlock?: Deadlock | null
  range: [number, number]
  cursor: number
  accent: string
  onSeek?: (t: number) => void
}

export function waitPoints(trains: Train[], schedule: Schedule, km: (i: number) => number) {
  const pts: { x: number; y: number; id: string; w: number }[] = []
  for (const t of trains) {
    const rows = schedule[t.id] ?? []
    for (let k = 1; k < rows.length - 1; k++) {
      const r = rows[k]
      if (r.ketish == null) continue
      const w = r.ketish - r.kelish - (t.stops[String(r.bekat)] ?? 0)
      if (w > 0) pts.push({ x: r.kelish, y: km(r.bekat), id: t.id, w })
    }
  }
  return pts
}

export default function TrainGraph(p: Props) {
  const t = useT()
  const { data, layout } = useMemo(() => {
    const km = (i: number) => p.stations[i].km
    const data: Data[] = []
    for (const kind of ['yuk', 'yolovchi', 'tezyurar'] as const) {
      data.push({ x: [null], y: [null], mode: 'lines', name: t(`k_${kind}`),
        line: { color: KIND_COLOR[kind], width: 3 }, legendgroup: kind, hoverinfo: 'skip' } as Data)
    }
    const stuck = new Set(p.deadlock?.stuck_trains ?? [])
    for (const tr of p.trains) {
      const rows = p.schedule[tr.id] ?? []
      const x: number[] = [], y: number[] = []
      for (const r of rows) {
        x.push(r.kelish); y.push(km(r.bekat))
        if (r.ketish != null && r.ketish !== r.kelish) { x.push(r.ketish); y.push(km(r.bekat)) }
      }
      data.push({ x, y, mode: 'lines', name: tr.id, showlegend: false, legendgroup: tr.kind,
        line: { color: KIND_COLOR[tr.kind], width: tr.kind === 'yuk' ? 1.6 : 2.2 },
        hovertemplate: `<b>${tr.id}</b> %{y:.1f} km · %{text}<extra></extra>`,
        text: x.map(hhmm) } as Data)
      if (stuck.has(tr.id) && rows.length) {
        const last = rows[rows.length - 1]
        data.push({ x: [last.kelish, p.range[1]], y: [km(last.bekat), km(last.bekat)], mode: 'lines',
          showlegend: false, line: { color: '#e03131', width: 2, dash: 'dot' }, hoverinfo: 'skip' } as Data)
      }
    }
    const wp = waitPoints(p.trains, p.schedule, km)
    data.push({ x: wp.map(w => w.x), y: wp.map(w => w.y), mode: 'markers', name: t('wait_mark'),
      marker: { symbol: 'circle-open', size: 8, color: '#333', line: { width: 1.5 } },
      text: wp.map(w => `${w.id}: +${w.w} ${t('min')}`), hovertemplate: '%{text}<extra></extra>' } as Data)
    if (stuck.size) {
      const sx: number[] = [], sy: number[] = []
      for (const id of stuck) {
        const rows = p.schedule[id]; if (!rows?.length) continue
        const last = rows[rows.length - 1]; sx.push(last.kelish); sy.push(km(last.bekat))
      }
      data.push({ x: sx, y: sy, mode: 'markers', name: t('stuck'),
        marker: { symbol: 'x', size: 11, color: '#e03131' }, hoverinfo: 'skip' } as Data)
    }
    const shapes: Partial<Shape>[] = []
    const annotations: Partial<Annotations>[] = []
    if (p.disruption) {
      const [a, b] = p.disruption.segment
      shapes.push({ type: 'rect', x0: p.disruption.start, x1: p.disruption.end, y0: km(a), y1: km(b),
        fillcolor: 'rgba(224,49,49,0.18)', line: { color: '#e03131', width: 1, dash: 'dash' } })
      annotations.push({ x: (p.disruption.start + p.disruption.end) / 2, y: Math.max(km(a), km(b)),
        text: t('closed'), showarrow: false, yshift: 10, font: { color: '#e03131', size: 11 } })
    }
    const tick0 = Math.floor(p.range[0] / 60) * 60
    const tickvals: number[] = []
    for (let v = tick0; v <= p.range[1]; v += 120) tickvals.push(v)
    const layout: Partial<Layout> = {
      title: { text: p.title, font: { size: 15, color: p.accent }, x: 0.01, xanchor: 'left' },
      margin: MARGIN, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: '#fff',
      showlegend: true, legend: { orientation: 'h', y: -0.1, yanchor: 'top', x: 0, font: { size: 11 } },
      xaxis: { range: p.range, fixedrange: true, tickvals, ticktext: tickvals.map(hhmm),
        gridcolor: '#eee', zeroline: false, title: { text: '' } },
      yaxis: { fixedrange: true, tickvals: p.stations.map(s => s.km),
        ticktext: p.stations.map(s => `${s.name} · ${s.km}`), gridcolor: '#e6e6e6', zeroline: false,
        range: [-3, p.stations[p.stations.length - 1].km + 3], title: { text: '' } },
      shapes, annotations, hovermode: 'closest',
    }
    return { data, layout }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.stations, p.trains, p.schedule, p.disruption, p.deadlock, p.range, p.title, p.accent, t])

  const frac = Math.min(1, Math.max(0, (p.cursor - p.range[0]) / (p.range[1] - p.range[0])))
  return (
    <div className="graph-wrap">
      <Plot data={data} layout={layout} height={HEIGHT} onClickX={p.onSeek} />
      <div className="cursor" style={{
        left: `calc(${MARGIN.l}px + (100% - ${MARGIN.l + MARGIN.r}px) * ${frac})`,
        top: MARGIN.t, height: HEIGHT - MARGIN.t - MARGIN.b }}>
        <span>{hhmm(p.cursor)}</span>
      </div>
    </div>
  )
}
