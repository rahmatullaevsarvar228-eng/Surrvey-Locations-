import { KIND_COLOR } from '../data'
import { useT } from '../i18n'
import type { Disruption, Schedule, Station, Train } from '../types'

const W = 1000, PADX = 50

export interface Pos { x: number; atStation: boolean; stuck: boolean }

// Poyezdning t vaqtdagi joyi (km); harakatda bo'lmasa — null.
export function trainPos(rows: { bekat: number; kelish: number; ketish: number | null }[],
                         st: Station[], t: number): Pos | null {
  if (!rows.length || t < rows[0].kelish) return null
  for (let k = 0; k < rows.length; k++) {
    const r = rows[k]
    if (r.ketish == null) return t >= r.kelish ? { x: st[r.bekat].km, atStation: true, stuck: true } : null
    if (t >= r.kelish && t <= r.ketish) {
      if (k === rows.length - 1) return t - r.kelish < 4 ? { x: st[r.bekat].km, atStation: true, stuck: false } : null
      return { x: st[r.bekat].km, atStation: true, stuck: false }
    }
    const n = rows[k + 1]
    if (n && t > r.ketish && t < n.kelish) {
      const f = (t - r.ketish) / (n.kelish - r.ketish)
      return { x: st[r.bekat].km + (st[n.bekat].km - st[r.bekat].km) * f, atStation: false, stuck: false }
    }
  }
  return null
}

// Hozirgacha rejadan tashqari kutish daqiqalari (tupikda turish ham hisoblanadi).
export function waitedSoFar(trains: Train[], sched: Schedule, t: number): number {
  let sum = 0
  for (const tr of trains) {
    const rows = sched[tr.id] ?? []
    for (let k = 1; k < rows.length; k++) {
      const r = rows[k]
      if (r.ketish == null) { sum += Math.max(0, t - r.kelish); continue }
      if (k === rows.length - 1) continue
      const planned = r.kelish + (tr.stops[String(r.bekat)] ?? 0)
      sum += Math.max(0, Math.min(t, r.ketish) - planned)
    }
  }
  return Math.round(sum)
}

interface Lane { label: string; color: string; schedule: Schedule; counter?: number }

export default function LineScheme({ stations, trains, lanes, t, disruption, showTracks = true }: {
  stations: Station[]; trains: Train[]; lanes: Lane[]; t: number
  disruption?: Disruption | null; showTracks?: boolean
}) {
  const tr = useT()
  const maxKm = stations[stations.length - 1].km
  const X = (km: number) => PADX + (km / maxKm) * (W - 2 * PADX)
  const laneH = 104
  const H = lanes.length * laneH + 4
  const closed = disruption && t >= disruption.start && t < disruption.end
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="scheme" role="img">
      {lanes.map((lane, li) => {
        const y0 = 10 + li * laneH + 46
        return (
          <g key={lane.label}>
            <text x={4} y={y0 - 30} className="lane-label" fill={lane.color}>{lane.label}</text>
            {lane.counter != null && (
              <text x={W - 4} y={y0 - 30} textAnchor="end" className="lane-counter">
                {tr('waiting_counter')}: <tspan fill={lane.color} fontWeight={700}>{lane.counter}</tspan> {tr('min')}
              </text>
            )}
            <line x1={X(0)} x2={X(maxKm)} y1={y0} y2={y0} stroke="#555" strokeWidth={3} />
            {disruption && (
              <line x1={X(stations[disruption.segment[0]].km)} x2={X(stations[disruption.segment[1]].km)}
                y1={y0} y2={y0} stroke={closed ? '#e03131' : '#f4a3a3'} strokeWidth={closed ? 7 : 4}
                strokeDasharray={closed ? '' : '6 4'} />
            )}
            {stations.map((s, i) => {
              const term = i === 0 || i === stations.length - 1
              const x = X(s.km)
              return (
                <g key={s.name}>
                  {showTracks && !term && Array.from({ length: s.tracks - 1 }).map((_, j) => (
                    <path key={j} d={`M${x - 22} ${y0} L${x - 14} ${y0 - 7 - j * 6} L${x + 14} ${y0 - 7 - j * 6} L${x + 22} ${y0}`}
                      fill="none" stroke="#999" strokeWidth={1.5} />
                  ))}
                  <rect x={x - 3} y={y0 - 4} width={6} height={8} fill={term ? '#222' : '#fff'} stroke="#222" />
                  <text x={x} y={y0 + 42} textAnchor="middle" className="st-label">{s.name}</text>
                </g>
              )
            })}
            {trains.map(trn => {
              const p = trainPos(lane.schedule[trn.id] ?? [], stations, t)
              if (!p) return null
              const dy = trn.direction === 1 ? -13 : 13
              const x = X(p.x)
              return (
                <g key={trn.id} transform={`translate(${x},${y0 + (p.atStation ? dy : dy * 0.55)})`}>
                  <path d={trn.direction === 1 ? 'M-9 -5 L5 -5 L10 0 L5 5 L-9 5 Z' : 'M9 -5 L-5 -5 L-10 0 L-5 5 L9 5 Z'}
                    fill={p.stuck ? '#e03131' : KIND_COLOR[trn.kind]} stroke={p.stuck ? '#7a0000' : '#fff'}
                    strokeWidth={1} opacity={p.atStation && !p.stuck ? 0.75 : 1}>
                    <title>{trn.id}</title>
                  </path>
                  <text y={trn.direction === 1 ? -8 : 16} textAnchor="middle" className="tr-label">{trn.id}</text>
                </g>
              )
            })}
          </g>
        )
      })}
    </svg>
  )
}
