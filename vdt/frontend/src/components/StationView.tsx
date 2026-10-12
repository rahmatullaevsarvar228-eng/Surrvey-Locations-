import { useMemo } from 'react'
import { KIND_COLOR, hhmm } from '../data'
import { useT } from '../i18n'
import type { Schedule, Station, Train } from '../types'

// Bekat (razyezd) sxemasi: asosiy yo'l + qo'shimcha yo'llar, strelkalar, svetoforlar, poyezdlar.
// Yo'l raqami: 0 — asosiy, 1, 2, ... — qo'shimcha (navbat bilan yuqori/pastki).

const W = 640, H = 230, YM = 118, GAP = 40
const SWL = 120, SWR = 520            // strelkalar
const LOOP_L = 175, LOOP_R = 465      // qo'shimcha yo'lning to'g'ri qismi
const TW = 74                         // poyezd uzunligi (px)

function trackY(k: number) {
  if (k === 0) return YM
  const side = k % 2 === 1 ? -1 : 1
  return YM + side * GAP * Math.ceil(k / 2)
}

interface Stay { id: string; arr: number; dep: number; track: number; extraWait: boolean }

// Har bir bekatda turgan poyezdlarga yo'l biriktirish (bir xil vaqtda bitta yo'lda bitta poyezd).
export function assignTracks(trains: Train[], sched: Schedule, station: number, tracks: number): Stay[] {
  const stays: Omit<Stay, 'track'>[] = []
  for (const t of trains) {
    for (const r of sched[t.id] ?? []) {
      if (r.bekat !== station) continue
      const dep = r.ketish ?? Number.POSITIVE_INFINITY
      const planned = t.stops[String(station)] ?? 0
      stays.push({ id: t.id, arr: r.kelish, dep, extraWait: dep - r.kelish > planned })
    }
  }
  stays.sort((a, b) => a.arr - b.arr || a.dep - b.dep)
  const freeAt = Array.from({ length: Math.max(tracks, 1) }, () => -Infinity)
  return stays.map(s => {
    // to'xtamasdan o'tadigan poyezd — asosiy yo'l; kutadigan — qo'shimcha yo'l
    const order = s.extraWait
      ? [...Array.from({ length: tracks - 1 }, (_, i) => i + 1), 0]
      : [0, ...Array.from({ length: tracks - 1 }, (_, i) => i + 1)]
    let k = order.find(i => freeAt[i] <= s.arr)
    if (k === undefined) k = order.reduce((b, i) => (freeAt[i] < freeAt[b] ? i : b), order[0])
    freeAt[k] = s.dep + 1
    return { ...s, track: k }
  })
}

interface Props {
  title: string
  accent: string
  stations: Station[]
  trains: Train[]
  schedule: Schedule
  station: number
  t: number
  tracks?: number           // bekatdagi yo'llar soni (qurilgan razyezd bilan)
  plannedTrack?: boolean    // oxirgi yo'l — loyihadagi yangi razyezd (punktir)
  closedSegments?: [number, number][]
}

export default function StationView(p: Props) {
  const tr = useT()
  const st = p.stations[p.station]
  const term = p.station === 0 || p.station === p.stations.length - 1
  const tracks = Math.min(p.tracks ?? st.tracks, 5)
  const stays = useMemo(() => assignTracks(p.trains, p.schedule, p.station, term ? 3 : tracks),
    [p.trains, p.schedule, p.station, tracks, term])
  const byId = useMemo(() => new Map(p.trains.map(x => [x.id, x])), [p.trains])

  // bekatda turgan poyezdlar
  const here = stays.filter(s => p.t >= s.arr && p.t <= s.dep)
  // yaqinlashayotgan / ketayotgan poyezdlar (qo'shni peregonlarda)
  const moving: { id: string; x: number; dir: number; leaving: boolean }[] = []
  for (const t of p.trains) {
    const rows = p.schedule[t.id] ?? []
    for (let k = 0; k < rows.length - 1; k++) {
      const a = rows[k], b = rows[k + 1]
      if (a.ketish == null || p.t <= a.ketish || p.t >= b.kelish) continue
      const f = (p.t - a.ketish) / (b.kelish - a.ketish)
      if (b.bekat === p.station) {          // kelmoqda
        const fromLeft = a.bekat < p.station
        moving.push({ id: t.id, dir: t.direction, leaving: false, x: fromLeft ? f * SWL - TW : W - f * SWL })
      } else if (a.bekat === p.station) {   // ketmoqda
        const toRight = b.bekat > p.station
        moving.push({ id: t.id, dir: t.direction, leaving: true, x: toRight ? SWR + f * (W - SWR) : SWL - f * SWL - TW })
      }
    }
  }
  const closed = (p.closedSegments ?? []).some(([a, b]) => a === p.station || b === p.station)
  const nextPrev = (d: number) => p.stations[p.station + d]?.name

  return (
    <div className="stview">
      <div className="stview-head">
        <b style={{ color: p.accent }}>{p.title}</b>
        <span className="muted small">{st.name} · {st.km} km · {term ? tr('terminal') : `${tracks} ${tr('tracks')}`}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="stview-svg" role="img" aria-label={`${st.name}`}>
        <defs>
          <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M20 0 L0 0 0 20" fill="none" stroke="#ffffff10" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width={W} height={H} rx="10" fill="#14231a" />
        <rect width={W} height={H} rx="10" fill="url(#grid)" />
        <rect x="6" y="6" width={W - 12} height={H - 12} rx="8" fill="none" stroke="#ffffff30" />
        {nextPrev(-1) && <text x="12" y={YM - 10} className="sv-dim">← {nextPrev(-1)}</text>}
        {nextPrev(1) && <text x={W - 12} y={YM - 10} textAnchor="end" className="sv-dim">{nextPrev(1)} →</text>}

        {/* yo'llar */}
        {Array.from({ length: term ? 1 : tracks }).map((_, k) => {
          const y = trackY(k)
          const planned = p.plannedTrack && k === tracks - 1 && k > 0
          const busy = here.some(s => s.track === k)
          const color = planned ? '#f59f00' : busy ? '#3ddc84' : '#c9d1cc'
          if (k === 0) return <line key={k} x1="0" x2={W} y1={y} y2={y} stroke={busy ? color : '#c9d1cc'} strokeWidth="5" strokeLinecap="round" />
          return (
            <path key={k} d={`M${SWL} ${YM} L${LOOP_L} ${y} L${LOOP_R} ${y} L${SWR} ${YM}`} fill="none"
              stroke={color} strokeWidth="5" strokeLinejoin="round" strokeDasharray={planned ? '10 7' : undefined} opacity={busy || planned ? 1 : 0.85} />
          )
        })}
        {closed && <text x={W / 2} y={H - 12} textAnchor="middle" className="sv-closed">{tr('closed')}</text>}

        {/* strelkalar */}
        {!term && tracks > 1 && [SWL, SWR].map(x => <circle key={x} cx={x} cy={YM} r="5" fill="#14231a" stroke="#c9d1cc" strokeWidth="2" />)}

        {/* svetoforlar: har bir yo'l oxirida, ikki yo'nalish uchun */}
        {!term && Array.from({ length: tracks }).map((_, k) => {
          const y = trackY(k)
          return [1, -1].map(dir => {
            const s = here.find(h => h.track === k && byId.get(h.id)?.direction === dir)
            const go = s && p.t >= s.dep - 1
            const fill = !s ? '#56635b' : go ? '#3ddc84' : '#ff5a4f'
            const x = dir === 1 ? LOOP_R + 14 : LOOP_L - 14
            return <circle key={`${k}${dir}`} cx={x} cy={y + (k === 0 ? (dir === 1 ? -14 : 14) : (y < YM ? -12 : 12))} r="5" fill={fill} stroke="#0008" />
          })
        })}

        {/* bekatdagi poyezdlar */}
        {here.map(s => {
          const t = byId.get(s.id); if (!t) return null
          const y = trackY(term ? 0 : s.track)
          const cx = (LOOP_L + LOOP_R) / 2 + (term ? 0 : 0)
          return <TrainRect key={s.id} id={s.id} x={cx - TW / 2} y={y} color={KIND_COLOR[t.kind]} dir={t.direction}
            label={s.dep === Number.POSITIVE_INFINITY ? 'TUPIK' : s.extraWait ? `${tr('wait_short')} → ${hhmm(s.dep)}` : ''} stuck={s.dep === Number.POSITIVE_INFINITY} />
        })}
        {moving.map(m => {
          const t = byId.get(m.id); if (!t) return null
          return <TrainRect key={m.id + (m.leaving ? 'L' : 'A')} id={m.id} x={m.x} y={YM} color={KIND_COLOR[t.kind]} dir={m.dir} label="" />
        })}

        <text x={W / 2} y="26" textAnchor="middle" className="sv-title">{st.name}</text>
        <text x={W - 14} y="26" textAnchor="end" className="sv-clock">{hhmm(p.t)}</text>
      </svg>
      <div className="stview-legend small muted">
        <span><i className="sig g" /> {tr('sig_go')}</span>
        <span><i className="sig r" /> {tr('sig_stop')}</span>
        {p.plannedTrack && <span><i className="trk-new" /> {tr('new_track')}</span>}
      </div>
    </div>
  )
}

function TrainRect({ id, x, y, color, dir, label, stuck }: {
  id: string; x: number; y: number; color: string; dir: number; label: string; stuck?: boolean
}) {
  const nose = dir === 1 ? `M${x + TW} ${y - 7} L${x + TW + 8} ${y} L${x + TW} ${y + 7} Z` : `M${x} ${y - 7} L${x - 8} ${y} L${x} ${y + 7} Z`
  return (
    <g>
      <rect x={x} y={y - 7} width={TW} height="14" rx="2" fill={stuck ? '#ff5a4f' : color} stroke="#0b130e" strokeWidth="1.5" />
      <path d={nose} fill={stuck ? '#ff5a4f' : color} stroke="#0b130e" strokeWidth="1.2" />
      {[1, 2, 3].map(i => <line key={i} x1={x + (TW / 4) * i} x2={x + (TW / 4) * i} y1={y - 7} y2={y + 7} stroke="#0b130e55" />)}
      <text x={x + TW / 2} y={y + 4} textAnchor="middle" className="sv-train">{id}</text>
      {label && <text x={x + TW / 2} y={y - 12} textAnchor="middle" className={stuck ? 'sv-stuck' : 'sv-wait'}>{label}</text>}
    </g>
  )
}
