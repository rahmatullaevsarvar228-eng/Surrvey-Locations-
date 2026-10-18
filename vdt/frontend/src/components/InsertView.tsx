import { useMemo } from 'react'
import { KIND_COLOR, hhmm } from '../data'
import { useT } from '../i18n'
import type { Schedule, Station, Train } from '../types'
import { trainPos } from './LineScheme'
import { insertPassages, type Passage } from './lanes'

// Obgon uchastkasi (asosiy yo'l + chap va o'ng aylanma yo'l) yaqindan: poyezdlar to'xtamasdan
// uchrashadi va quvib o'tadi.

const W = 640, H = 230, YM = 118, GAP = 42, PAD = 30

export default function InsertView({ title, accent, stations, trains, schedule, jl, t, planned, single }: {
  title: string; accent: string; stations: Station[]; trains: Train[]; schedule: Schedule
  jl: number; t: number; planned?: boolean; single?: boolean
}) {
  const tr = useT()
  const A = stations[jl], B = stations[jl + 1]
  const left = stations[jl - 1], right = stations[jl + 2]
  const k0 = left.km, k1 = right.km
  const X = (km: number) => PAD + ((km - k0) / (k1 - k0)) * (W - 2 * PAD)
  const xa = X(A.km), xb = X(B.km), sw = Math.min(40, (xb - xa) / 4)
  const passages = useMemo(() => (single ? new Map<number, Passage[]>() : insertPassages(stations, trains, schedule)),
    [stations, trains, schedule, single])
  const list = passages.get(jl) ?? []
  const loopPath = (y: number) =>
    `M${xa} ${YM} C ${xa + sw * 0.6} ${YM} ${xa + sw * 0.4} ${y} ${xa + sw} ${y} L ${xb - sw} ${y} C ${xb - sw * 0.4} ${y} ${xb - sw * 0.6} ${YM} ${xb} ${YM}`
  const laneY = (lane: number, x: number) => {
    if (!lane) return YM
    const target = YM + lane * GAP
    if (x <= xa || x >= xb) return YM
    const f = Math.min(1, (x - xa) / sw, (xb - x) / sw)
    return YM + (target - YM) * Math.max(0, Math.min(1, f))
  }
  const busyLane = new Set<number>()
  const drawn = trains.map(trn => {
    const p = trainPos(schedule[trn.id] ?? [], stations, t)
    if (!p || p.x < k0 || p.x > k1) return null
    const x = X(p.x)
    const pas = list.find(q => q.id === trn.id && t >= q.enter && t <= q.exit)
    const lane = pas?.lane ?? 0
    if (pas) busyLane.add(lane)
    const y = laneY(lane, x)
    const w = 64, d = trn.direction
    const body = d === 1 ? `M${x - w} ${y - 7} L${x - 8} ${y - 7} L${x} ${y} L${x - 8} ${y + 7} L${x - w} ${y + 7} Z`
      : `M${x + w} ${y - 7} L${x + 8} ${y - 7} L${x} ${y} L${x + 8} ${y + 7} L${x + w} ${y + 7} Z`
    const cx = d === 1 ? x - w / 2 - 4 : x + w / 2 + 4
    return (
      <g key={trn.id}>
        <path d={body} fill={KIND_COLOR[trn.kind]} stroke="#0b130e" strokeWidth="1.5" />
        <text x={cx} y={y + 4} textAnchor="middle" className="sv-train">{trn.id}</text>
        <text x={cx} y={y - 12} textAnchor="middle" className="sv-wait">{trn.speed} km/h</text>
      </g>
    )
  })
  const loopColor = (lane: number) => (busyLane.has(lane) ? '#3ddc84' : planned ? '#f59f00' : '#c9d1cc')
  return (
    <div className="stview">
      <div className="stview-head">
        <b style={{ color: accent }}>{title}</b>
        <span className="muted small">{left.name} → {right.name} · {single ? tr('one_track') : `${A.name}: ${(B.km - A.km).toFixed(1)} km`}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="stview-svg" role="img" aria-label={title}>
        <defs>
          <pattern id="grid2" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M20 0 L0 0 0 20" fill="none" stroke="#ffffff10" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width={W} height={H} rx="10" fill="#14231a" />
        <rect width={W} height={H} rx="10" fill="url(#grid2)" />
        <line x1="0" x2={W} y1={YM} y2={YM} stroke={busyLane.has(0) && !single ? '#3ddc84' : '#c9d1cc'} strokeWidth="5" strokeLinecap="round" />
        {!single && <>
          <path d={loopPath(YM - GAP)} fill="none" stroke={loopColor(-1)} strokeWidth="5" strokeDasharray={planned && !busyLane.has(-1) ? '10 7' : undefined} />
          <path d={loopPath(YM + GAP)} fill="none" stroke={loopColor(1)} strokeWidth="5" strokeDasharray={planned && !busyLane.has(1) ? '10 7' : undefined} />
          <text x={(xa + xb) / 2} y={YM - GAP - 12} textAnchor="middle" className="sv-dim">{tr('loop_left')}</text>
          <text x={(xa + xb) / 2} y={YM + GAP + 22} textAnchor="middle" className="sv-dim">{tr('loop_right')}</text>
          {[xa, xb].map(x => <circle key={x} cx={x} cy={YM} r="5" fill="#14231a" stroke="#c9d1cc" strokeWidth="2" />)}
        </>}
        <text x="12" y={YM - 10} className="sv-dim">← {left.name}</text>
        <text x={W - 12} y={YM - 10} textAnchor="end" className="sv-dim">{right.name} →</text>
        {drawn}
        <text x={W / 2} y="26" textAnchor="middle" className="sv-title">{single ? tr('one_track') : `${tr('obgon_point')} ${A.name}`}</text>
        <text x={W - 14} y="26" textAnchor="end" className="sv-clock">{hhmm(t)}</text>
      </svg>
      <div className="stview-legend small muted">
        {!single && <span><i className="trk-new" /> {tr('new_obgon')}</span>}
        {!single && <span>{tr('no_stop_note')}</span>}
      </div>
    </div>
  )
}
