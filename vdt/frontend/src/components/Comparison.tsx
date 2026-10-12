import { useMemo, useState } from 'react'
import { useT } from '../i18n'
import type { Objective, ScenarioData } from '../types'
import TrainGraph from './TrainGraph'
import LineScheme, { waitedSoFar } from './LineScheme'
import PlayerBar from './PlayerBar'
import MetricsPanel, { Badge, StatusTag } from './MetricsPanel'
import { usePlayer } from './usePlayer'
import StationView, { assignTracks } from './StationView'

export function timeRange(d: ScenarioData, obj: Objective): [number, number] {
  let lo = Infinity, hi = 0
  const scheds = [d.fifo.schedule, d.ai[obj]?.schedule].filter(Boolean)
  for (const s of scheds) for (const rows of Object.values(s!)) for (const r of rows) {
    lo = Math.min(lo, r.kelish); hi = Math.max(hi, r.ketish ?? r.kelish)
  }
  if (d.scenario.disruption) hi = Math.max(hi, d.scenario.disruption.end)
  return [Math.max(0, Math.floor((lo - 10) / 10) * 10), Math.ceil((hi + 20) / 10) * 10]
}

export default function Comparison({ data, objective }: { data: ScenarioData; objective: Objective }) {
  const t = useT()
  const ai = data.ai[objective]
  const range = useMemo(() => timeRange(data, objective), [data, objective])
  const p = usePlayer(range)
  const { stations, trains, disruption } = data.scenario
  // sukut bo'yicha: avariya joyidagi bekat yoki FIFO da eng ko'p kutish bo'lgan bekat
  const busiest = useMemo(() => {
    if (disruption) return disruption.segment[0]
    let best = 1, bestN = -1
    for (let i = 1; i < stations.length - 1; i++) {
      const n = assignTracks(trains, data.fifo.schedule, i, stations[i].tracks).filter(x => x.extraWait).length
      if (n > bestN) { best = i; bestN = n }
    }
    return best
  }, [data, stations, trains, disruption])
  const [picked, setPicked] = useState<number | null>(null)
  const station = picked ?? busiest
  if (!ai || !ai.schedule) return <div className="card">{t('load_error')}</div>
  return (
    <div className="comparison">
      <div className="card">
        <PlayerBar p={p} range={range} />
        <LineScheme stations={stations} trains={trains} t={p.t} disruption={disruption}
          selected={station} onPickStation={i => { if (i > 0 && i < stations.length - 1) setPicked(i) }}
          lanes={[
            { label: t('fifo_title'), color: 'var(--fifo)', schedule: data.fifo.schedule,
              counter: waitedSoFar(trains, data.fifo.schedule, p.t) },
            { label: t('ai_title'), color: 'var(--ai)', schedule: ai.schedule,
              counter: waitedSoFar(trains, ai.schedule, p.t) },
          ]} />
      </div>
      <div className="card">
        <div className="stview-bar">
          <h3>{t('station_view')}</h3>
          <select value={station} onChange={e => setPicked(Number(e.target.value))} aria-label={t('station')}>
            {stations.slice(1, -1).map((s, i) => <option key={s.name} value={i + 1}>{s.name} · {s.tracks} {t('tracks')}</option>)}
          </select>
          <span className="muted small">{t('station_hint')}</span>
        </div>
        <div className="graphs">
          <StationView title={t('fifo_title')} accent="#c2410c" stations={stations} trains={trains}
            schedule={data.fifo.schedule} station={station} t={p.t}
            closedSegments={disruption && p.t >= disruption.start && p.t < disruption.end ? [disruption.segment] : []} />
          <StationView title={t('ai_title')} accent="#1c7c54" stations={stations} trains={trains}
            schedule={ai.schedule} station={station} t={p.t}
            closedSegments={disruption && p.t >= disruption.start && p.t < disruption.end ? [disruption.segment] : []} />
        </div>
      </div>
      <div className="graphs">
        <div className="card">
          <TrainGraph title={t('fifo_title')} accent="#c2410c" stations={stations} trains={trains}
            schedule={data.fifo.schedule} disruption={disruption} deadlock={data.fifo.deadlock}
            range={range} cursor={p.t} onSeek={p.seek} />
          <div className="under">
            {data.fifo.deadlock ? <span className="badge bad">TUPIK</span> : <Badge errors={data.fifo.xatolar} />}
          </div>
        </div>
        <div className="card">
          <TrainGraph title={t('ai_title')} accent="#1c7c54" stations={stations} trains={trains}
            schedule={ai.schedule} disruption={disruption} range={range} cursor={p.t} onSeek={p.seek} />
          <div className="under"><Badge errors={ai.xatolar} /><StatusTag ai={ai} /></div>
        </div>
      </div>
      <div className="card"><MetricsPanel fifo={data.fifo} ai={ai} objective={objective} /></div>
    </div>
  )
}
