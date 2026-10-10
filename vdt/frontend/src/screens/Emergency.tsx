import { useEffect, useState } from 'react'
import { hhmm, loadScenario, solve } from '../data'
import type { Objective, ScenarioData } from '../types'
import Comparison from '../components/Comparison'
import { Loading, ObjectivePicker } from '../components/Common'
import { useT } from '../i18n'

type EvType = 'closure' | 'breakdown'

export default function Emergency() {
  const t = useT()
  const [cached, setCached] = useState<ScenarioData | null>(null)
  const [live, setLive] = useState<ScenarioData | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [obj, setObj] = useState<Objective>('umumiy')
  const [busy, setBusy] = useState(false)
  const [runId, setRunId] = useState(0)
  const [apiErr, setApiErr] = useState<string | null>(null)
  const [ev, setEv] = useState<EvType>('closure')
  const [seg, setSeg] = useState(6)
  const [start, setStart] = useState(180)
  const [dur, setDur] = useState(90)
  const [trainId, setTrainId] = useState('')
  const [station, setStation] = useState(5)
  const [stuckMin, setStuckMin] = useState(60)

  useEffect(() => {
    loadScenario('avariya').then(d => { setCached(d); setTrainId(d.scenario.trains[0].id) })
      .catch(e => setErr(String(e)))
  }, [])

  const data = live ?? cached
  if (!data || !cached) return <Loading error={err} />
  const st = cached.scenario.stations

  const run = async () => {
    setBusy(true); setApiErr(null)
    try {
      const body = ev === 'closure'
        ? { preset: 'oddiy', objective: obj, time_limit: 10,
            disruption: { segment: [seg, seg + 1], start, end: start + dur } }
        : { preset: 'oddiy', objective: obj, time_limit: 10,
            breakdown: { train_id: trainId, station, minutes: stuckMin } }
      setLive(await solve(body))
      setRunId(r => r + 1)
    } catch (e) {
      setApiErr(String(e))
    } finally { setBusy(false) }
  }

  const dl = data.fifo.deadlock
  const ai = data.ai[obj] ?? Object.values(data.ai)[0]
  const objShown = (data.ai[obj] ? obj : (Object.keys(data.ai)[0] as Objective))
  const rec = data.tiklanish
  return (
    <>
      <div className="card form">
        <div className="form-row">
          <b>{t('event')}:</b>
          <button className={`btn chip ${ev === 'closure' ? 'on' : ''}`} onClick={() => setEv('closure')}>{t('ev_closure')}</button>
          <button className={`btn chip ${ev === 'breakdown' ? 'on' : ''}`} onClick={() => setEv('breakdown')}>{t('ev_breakdown')}</button>
        </div>
        {ev === 'closure' ? (
          <div className="form-row">
            <label>{t('segment')}
              <select value={seg} onChange={e => setSeg(Number(e.target.value))}>
                {st.slice(0, -1).map((s, i) => <option key={i} value={i}>{s.name}–{st[i + 1].name}</option>)}
              </select></label>
            <label>{t('from_min')} <input type="number" min={0} max={1200} value={start} onChange={e => setStart(Number(e.target.value))} />
              <span className="muted small">{hhmm(start)}</span></label>
            <label>{t('duration')} <input type="number" min={10} max={600} value={dur} onChange={e => setDur(Number(e.target.value))} /></label>
          </div>
        ) : (
          <div className="form-row">
            <label>{t('train')}
              <select value={trainId} onChange={e => setTrainId(e.target.value)}>
                {cached.scenario.trains.map(tr => <option key={tr.id}>{tr.id}</option>)}
              </select></label>
            <label>{t('station')}
              <select value={station} onChange={e => setStation(Number(e.target.value))}>
                {st.slice(1, -1).map((s, i) => <option key={i + 1} value={i + 1}>{s.name}</option>)}
              </select></label>
            <label>{t('stuck_min')} <input type="number" min={1} max={600} value={stuckMin} onChange={e => setStuckMin(Number(e.target.value))} /></label>
          </div>
        )}
        <div className="form-row">
          <ObjectivePicker value={obj} onChange={setObj} />
          <button className="btn primary big" onClick={run} disabled={busy}>{busy ? t('replanning') : t('replan')}</button>
          {live && <button className="btn" onClick={() => setLive(null)}>{t('showing_cache')}: {t('sc_avariya')}</button>}
          <span className="muted small">{live ? t('showing_live') : `${t('showing_cache')}: ${t('sc_avariya')} (S6–S7, ${hhmm(180)}–${hhmm(270)})`}</span>
        </div>
        {apiErr && <div className="warn">{t('api_needed')} <span className="small muted">{apiErr}</span></div>}
      </div>

      {dl ? (
        <div className="banner-deadlock">
          <div className="big">⛔ {t('deadlock_title')}</div>
          <div>{dl.stuck_trains.length} {t('deadlock_text')}: {hhmm(dl.vaqt)}</div>
          <div className="stuck-list"><b>{t('deadlock_list')}:</b>{' '}
            {dl.stuck_trains.map(id => <span key={id} className="pill">{id} → {dl.at_station[id]}</span>)}
          </div>
        </div>
      ) : <div className="banner-ok">{t('no_deadlock')}</div>}

      <div className="kpis">
        {ai?.ok && <div className="kpi ai">
          <div className="kpi-label">{t('ai_rescued')}</div>
          <div className="kpi-val">✓ {ai.metrics?.umumiy_kechikish_daq} {t('min')}</div>
          {!live && data.tez_hisob && <div className="small">{t('ai_rescued_quick', {
            s: data.tez_hisob.soniya, d: data.tez_hisob.umumiy_kechikish, e: data.tez_hisob.xatolar })}</div>}
        </div>}
        {rec && <div className="kpi">
          <div className="kpi-label">{t('recovery')} · {t('fifo_short')}</div>
          <div className="kpi-val fifo-c">{rec.fifo == null ? `∞ (${t('never')})` : `${rec.fifo} ${t('min')}`}</div>
          <div className="small muted">{t('recovery_hint')}</div>
        </div>}
        {rec && <div className="kpi">
          <div className="kpi-label">{t('recovery')} · {t('ai_short')}</div>
          <div className="kpi-val ai-c">{rec.ai[objShown] == null ? '—' : `${rec.ai[objShown]} ${t('min')}`}</div>
          <div className="small muted">{t('recovery_hint')}</div>
        </div>}
      </div>

      <Comparison key={`${live ? runId : 'cache'}-${objShown}`} data={data} objective={objShown} />
    </>
  )
}
