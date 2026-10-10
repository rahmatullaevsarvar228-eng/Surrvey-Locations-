import { useMemo } from 'react'
import { useT } from '../i18n'
import type { Objective, ScenarioData } from '../types'
import TrainGraph from './TrainGraph'
import LineScheme, { waitedSoFar } from './LineScheme'
import PlayerBar from './PlayerBar'
import MetricsPanel, { Badge, StatusTag } from './MetricsPanel'
import { usePlayer } from './usePlayer'

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
  if (!ai || !ai.schedule) return <div className="card">{t('load_error')}</div>
  return (
    <div className="comparison">
      <div className="card">
        <PlayerBar p={p} range={range} />
        <LineScheme stations={stations} trains={trains} t={p.t} disruption={disruption}
          lanes={[
            { label: t('fifo_title'), color: 'var(--fifo)', schedule: data.fifo.schedule,
              counter: waitedSoFar(trains, data.fifo.schedule, p.t) },
            { label: t('ai_title'), color: 'var(--ai)', schedule: ai.schedule,
              counter: waitedSoFar(trains, ai.schedule, p.t) },
          ]} />
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
