import { useEffect, useMemo, useState } from 'react'
import type { Data, Layout } from 'plotly.js'
import { loadScenario, loadSiding, type PresetName } from '../data'
import type { ScenarioData, SidingData } from '../types'
import Plot from '../components/Plot'
import NumInput, { fmtMoney } from '../components/NumInput'
import { Loading, PresetPicker } from '../components/Common'
import StationView from '../components/StationView'
import PlayerBar from '../components/PlayerBar'
import { usePlayer } from '../components/usePlayer'
import { Badge } from '../components/MetricsPanel'
import { DEFAULTS, SOURCES } from '../costs'
import { useT } from '../i18n'

export default function Invest() {
  const t = useT()
  const [sc, setSc] = useState<PresetName>('avariya')
  const [err, setErr] = useState<string | null>(null)
  const [sid, setSid] = useState<SidingData | null>(null)
  const [base, setBase] = useState<ScenarioData | null>(null)
  const [odd, setOdd] = useState<ScenarioData | null>(null)
  const [vi, setVi] = useState(0)
  const [len, setLen] = useState<number | null>(DEFAULTS.sidingKm)
  const [perKm, setPerKm] = useState<number | null>(DEFAULTS.trackPerKm)
  const [sw, setSw] = useState<number | null>(DEFAULTS.switchesSignals)
  const [idle, setIdle] = useState<number | null>(DEFAULTS.idlePerHour)
  const [inc, setInc] = useState<number | null>(null)
  useEffect(() => { loadSiding().then(setSid).catch(e => setErr(String(e))); loadScenario('oddiy').then(setOdd) }, [])
  useEffect(() => { setBase(null); setVi(0); loadScenario(sc).then(setBase) }, [sc])
  const d = sid?.ssenariylar[sc as 'oddiy' | 'avariya'] ?? null

  const plot = useMemo(() => {
    if (!d) return null
    const rows = d.reyting
    const data: Data[] = [{
      type: 'bar', x: rows.map(r => r.bekat), y: rows.map(r => r.tejaldi_daq),
      marker: { color: rows.map(r => (r.sezilarli ? '#1c7c54' : '#b8bcc2')) },
      text: rows.map(r => `${r.tejaldi_daq}`), textposition: 'outside',
      hovertemplate: '%{x}: %{y} ' + t('min') + '<extra></extra>',
    } as Data]
    const noise = Math.max(d.shovqin ?? 0, 1)
    const layout: Partial<Layout> = {
      margin: { l: 60, r: 20, t: 20, b: 50 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: '#fff',
      yaxis: { title: { text: t('saved_min') }, fixedrange: true, rangemode: 'tozero', gridcolor: '#eee' },
      xaxis: { fixedrange: true, type: 'category' },
      shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: noise, y1: noise,
        line: { color: '#e8590c', dash: 'dash', width: 1.5 } }],
      annotations: [{ xref: 'paper', x: 1, y: noise, xanchor: 'right', yanchor: 'bottom', showarrow: false,
        text: `${t('noise')}: ${noise} ${t('min')}`, font: { color: '#e8590c', size: 12 } }],
    }
    return { data, layout }
  }, [d, t])

  const range = useMemo<[number, number]>(() => (sc === 'avariya' ? [170, 600] : [0, 720]), [sc])
  const p = usePlayer(range)

  if (!sid) return <Loading error={err ? t('siding_missing') : null} />
  const picker = <div className="toolbar"><PresetPicker value={sc} onChange={setSc} options={['oddiy', 'avariya']} /></div>
  if (!d) return <>{picker}<Loading error={t('siding_missing')} /></>
  const vars = d.variantlar.filter(x => x.tejaldi_daq > 0)
  const v = vars[vi] ?? vars[0]
  const sig = d.reyting.filter(r => r.sezilarli).map(r => r.bekat)
  const total = len != null && perKm != null && sw != null ? len * perKm + sw : null
  const savedDay = v ? v.tejaldi_daq : 0
  const isIncident = sc === 'avariya'
  const perEvent = idle != null ? (savedDay / 60) * idle : null
  const perYear = perEvent == null ? null : isIncident ? (inc != null ? perEvent * inc : null) : perEvent * DEFAULTS.daysPerYear
  const fm = odd?.fifo.metrics, am = odd?.ai.umumiy?.metrics
  const softDay = fm && am ? fm.umumiy_kechikish_daq - am.umumiy_kechikish_daq : null
  const softYear = softDay != null && idle != null ? (softDay / 60) * idle * DEFAULTS.daysPerYear : null
  const st = base?.scenario.stations
  const stAfter = st && v ? st.map((s, i) => (i === v.indeks ? { ...s, tracks: v.yollar_keyin } : s)) : null

  const dis = base?.scenario.disruption
  const closedAt = dis && p.t >= dis.start && p.t < dis.end ? [dis.segment] : []
  return (
    <>
      {picker}
      <div className="card">
        <h3>{t('invest_title')}</h3>
        <div className="message">{t('invest_msg2')}</div>
        <div className={sig.length ? 'box-note' : 'warn'}>{sig.length ? t('effect_msg', { s: sig.join(', ') }) : t('no_effect_msg')}</div>
        {d.reyting.length < 10 && <div className="warn">{t('invest_partial')} ({d.reyting.length}/10)</div>}
        {plot && <Plot data={plot.data} layout={plot.layout} height={340} />}
        <div className="legend-row">
          <span><span className="dot" style={{ background: '#1c7c54' }} />{t('significant')}</span>
          <span><span className="dot" style={{ background: '#b8bcc2' }} />{t('not_significant')}</span>
        </div>
        <p className="muted small">{t('protocol')} ({sid.hisob_s} s × {sid.seedlar.length} seed) · {t('synthetic')}</p>
      </div>

      <div className="card">
        <div className="stview-bar">
          <h3>{t('before_after')}</h3>
          {vars.map((x, i) => (
            <button key={x.bekat} className={`btn chip ${vi === i ? 'on' : ''}`} onClick={() => setVi(i)}>{x.bekat}</button>
          ))}
        </div>
        {v && base && st && stAfter ? (
          <>
            <p className="muted small">{t('before_after_hint')}</p>
            <PlayerBar p={p} range={range} />
            <div className="graphs">
              <StationView title={`${t('now_tracks')}: ${v.yollar_oldin} ${t('tracks')}`} accent="#c2410c" stations={st}
                trains={base.scenario.trains} schedule={d.nazorat.schedule} station={v.indeks} t={p.t} closedSegments={closedAt} />
              <StationView title={`${t('with_new')}: ${v.yollar_keyin} ${t('tracks')}`} accent="#1c7c54" stations={stAfter}
                trains={base.scenario.trains} schedule={v.schedule} station={v.indeks} t={p.t} plannedTrack closedSegments={closedAt} />
            </div>
            <div className="kpis" style={{ marginTop: 10 }}>
              <div className="kpi"><div className="kpi-label">{t('m_total')} · {t('now_tracks')}</div>
                <div className="kpi-val fifo-c">{d.nazorat.metrics.umumiy_kechikish_daq} {t('min')}</div></div>
              <div className="kpi ai"><div className="kpi-label">{t('m_total')} · {t('with_new')}</div>
                <div className="kpi-val ai-c">{v.metrics.umumiy_kechikish_daq} {t('min')}</div>
                <Badge errors={v.xatolar} /></div>
              <div className="kpi"><div className="kpi-label">{sc === 'avariya' ? t('saved_event_min') : t('saved_day')}</div>
                <div className="kpi-val">{v.tejaldi_daq} {t('min')}</div></div>
            </div>
          </>
        ) : <p className="muted">{vars.length ? t('loading') : t('no_effect_msg')}</p>}
      </div>

      <div className="card">
        <h3>{t('cost_title')} <span className="est">{t('estimate_tag')}</span></h3>
        <div className="warn soft">{t('default_note')}</div>
        <div className="cost-grid">
          <NumInput label={t('cost_len')} value={len} onChange={setLen} note={t('cost_len_note')} step={0.1} />
          <NumInput label={t('cost_km')} value={perKm} onChange={setPerKm} note={t('cost_km_note')} />
          <NumInput label={t('cost_sw')} value={sw} onChange={setSw} note={t('cost_sw_note')} />
          <NumInput label={t('idle_cost')} value={idle} onChange={setIdle} note={t('idle_note')} />
          {isIncident && <NumInput label={t('incidents_year')} value={inc} onChange={setInc} note={t('incidents_note')} step={1} />}
        </div>
        <div className="formula">
          <b>{t('cost_total')}:</b>
          <div className="formula-live">{len ?? '?'} km × {perKm != null ? fmtMoney(perKm) : '?'} + {sw != null ? fmtMoney(sw) : '?'} = <b>{total != null ? fmtMoney(total) : '?'}</b></div>
          <div className="small muted">{t('cost_bench')}</div>
        </div>
        <div className="kpis">
          <div className="kpi"><div className="kpi-label">{t('cost_total')}</div><div className="kpi-val">{total != null ? fmtMoney(total) : '—'}</div></div>
          {isIncident && <div className="kpi"><div className="kpi-label">{t('saved_event')} ({t('saved_this')}{v ? ` ${v.bekat}` : ''})</div>
            <div className="kpi-val">{perEvent != null ? fmtMoney(perEvent) : '—'}</div>
            <div className="small muted">{savedDay} {t('min')} ÷ 60 × {idle ?? '?'} $</div></div>}
          <div className="kpi"><div className="kpi-label">{t('saved_year')} ({t('saved_this')}{v ? ` ${v.bekat}` : ''})</div>
            <div className="kpi-val">{perYear != null ? fmtMoney(perYear) : '—'}</div>
            <div className="small muted">{savedDay} {t('min')} ÷ 60 × {idle ?? '?'} $ × {isIncident ? (inc ?? '?') : DEFAULTS.daysPerYear}</div></div>
          <div className="kpi"><div className="kpi-label">{t('payback_years')}</div>
            <div className="kpi-val">{total != null && perYear ? `${Math.round(total / perYear).toLocaleString('ru-RU')} ${t('years')}` : '—'}</div></div>
        </div>
        {softDay != null && softYear != null && (
          <div className="box-note">{t('compare_software', { m: softDay, d: fmtMoney(softYear) })}</div>
        )}
        <p className="muted small">{t('only_delay_note')}</p>
        <details><summary className="small">{t('sources')}</summary>
          <ol className="src-list">{SOURCES.map(s => <li key={s.u}>{s.t} <a href={s.u} target="_blank" rel="noreferrer">{new URL(s.u).hostname}</a></li>)}</ol>
        </details>
      </div>
    </>
  )
}
