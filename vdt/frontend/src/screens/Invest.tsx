import { useEffect, useMemo, useState } from 'react'
import type { Data, Layout } from 'plotly.js'
import { loadObgon, loadScenario, type PresetName } from '../data'
import type { ObgonData, ScenarioData } from '../types'
import Plot from '../components/Plot'
import NumInput, { fmtMoney } from '../components/NumInput'
import { Loading, PresetPicker } from '../components/Common'
import StationView from '../components/StationView'
import LineScheme from '../components/LineScheme'
import PlayerBar from '../components/PlayerBar'
import { usePlayer } from '../components/usePlayer'
import { Badge } from '../components/MetricsPanel'
import { DEFAULTS, SOURCES } from '../costs'
import { useT } from '../i18n'

type ObName = 'oddiy' | 'avariya' | 'osish30'

export default function Invest() {
  const t = useT()
  const [sc, setSc] = useState<PresetName>('osish30')
  const [err, setErr] = useState<string | null>(null)
  const [ob, setOb] = useState<ObgonData | null>(null)
  const [odd, setOdd] = useState<ScenarioData | null>(null)
  const [vi, setVi] = useState(0)
  const [loops, setLoops] = useState<number | null>(DEFAULTS.obgonLoops)
  const [len, setLen] = useState<number | null>(DEFAULTS.sidingKm)
  const [perKm, setPerKm] = useState<number | null>(DEFAULTS.trackPerKm)
  const [sw, setSw] = useState<number | null>(DEFAULTS.obgonSwitches)
  const [idle, setIdle] = useState<number | null>(DEFAULTS.idlePerHour)
  const [inc, setInc] = useState<number | null>(null)
  useEffect(() => { loadObgon().then(setOb).catch(e => setErr(String(e))); loadScenario('oddiy').then(setOdd) }, [])
  useEffect(() => { setVi(0) }, [sc])
  const d = ob?.ssenariylar[sc as ObName] ?? null

  const plot = useMemo(() => {
    if (!d) return null
    const rows = [...d.reyting].sort((a, b) => a.k - b.k)
    const data: Data[] = [{
      type: 'bar', x: rows.map(r => r.peregon), y: rows.map(r => r.tejaldi_daq),
      marker: { color: rows.map(r => (r.sezilarli ? '#1c7c54' : '#b8bcc2')) },
      text: rows.map(r => `${r.tejaldi_daq}`), textposition: 'outside',
      customdata: rows.map(r => r.uzunlik_km),
      hovertemplate: '%{x} (%{customdata} km): %{y} ' + t('min') + '<extra></extra>',
    } as Data]
    const noise = Math.max(d.shovqin ?? 0, 1)
    const layout: Partial<Layout> = {
      margin: { l: 60, r: 20, t: 20, b: 60 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: '#fff',
      yaxis: { title: { text: t('saved_min') }, fixedrange: true, rangemode: 'tozero', gridcolor: '#eee' },
      xaxis: { fixedrange: true, type: 'category', title: { text: t('peregon_label') } },
      shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: noise, y1: noise, line: { color: '#e8590c', dash: 'dash', width: 1.5 } }],
      annotations: [{ xref: 'paper', x: 1, y: noise, xanchor: 'right', yanchor: 'bottom', showarrow: false,
        text: `${t('noise')}: ${noise} ${t('min')}`, font: { color: '#e8590c', size: 12 } }],
    }
    return { data, layout }
  }, [d, t])

  const v = d?.variantlar[vi] ?? d?.variantlar[0]
  const range = useMemo<[number, number]>(() => {
    if (!v) return [0, 720]
    let lo = Infinity, hi = 0
    for (const rows of Object.values(v.keyin)) for (const r of rows) { lo = Math.min(lo, r.kelish); hi = Math.max(hi, r.ketish ?? r.kelish) }
    return [Math.max(0, Math.floor(lo / 10) * 10), Math.ceil(hi / 10) * 10 + 10]
  }, [v])
  const p = usePlayer(range)

  if (!ob) return <Loading error={err ? t('siding_missing') : null} />
  const picker = <div className="toolbar"><PresetPicker value={sc} onChange={setSc} options={['osish30', 'avariya', 'oddiy']} /></div>
  if (!d) return <>{picker}<Loading error={t('siding_missing')} /></>

  const total = loops != null && len != null && perKm != null && sw != null ? loops * len * perKm + sw : null
  const saved = v ? v.tejaldi_daq : 0
  const isIncident = sc === 'avariya'
  const perEvent = idle != null ? (saved / 60) * idle : null
  const perYear = perEvent == null ? null : isIncident ? (inc != null ? perEvent * inc : null) : perEvent * DEFAULTS.daysPerYear
  const fm = odd?.fifo.metrics, am = odd?.ai.umumiy?.metrics
  const softDay = fm && am ? fm.umumiy_kechikish_daq - am.umumiy_kechikish_daq : null
  const softYear = softDay != null && idle != null ? (softDay / 60) * idle * DEFAULTS.daysPerYear : null
  const sig = d.reyting.filter(r => r.sezilarli).slice(0, 3).map(r => `${r.peregon} (−${r.tejaldi_daq} ${t('min')})`)

  const stAfter = v?.scenario.stations
  const stBefore = stAfter?.map((s, i) => (v && i === v.k + 1 ? { ...s, tracks: 1 } : s))
  const dis = v?.scenario.disruption
  const closedAt = dis && p.t >= dis.start && p.t < dis.end ? [dis.segment] : []

  return (
    <>
      {picker}
      <div className="card">
        <h3>{t('ob_title')}</h3>
        <p className="muted">{t('ob_what')}</p>
        <div className={sig.length ? 'box-note' : 'warn'}>{sig.length ? t('ob_effect', { s: sig.join(', ') }) : t('ob_none')}</div>
        {plot && <Plot data={plot.data} layout={plot.layout} height={330} />}
        <div className="legend-row">
          <span><span className="dot" style={{ background: '#1c7c54' }} />{t('significant')}</span>
          <span><span className="dot" style={{ background: '#b8bcc2' }} />{t('not_significant')}</span>
        </div>
        <p className="muted small">{t('ob_protocol')} ({ob.hisob_s} s × {ob.seedlar.length} seed) · {t('synthetic')}</p>
      </div>

      <div className="card">
        <div className="stview-bar">
          <h3>{t('ob_before_after')}</h3>
          {d.variantlar.map((x, i) => (
            <button key={x.peregon} className={`btn chip ${v?.peregon === x.peregon ? 'on' : ''}`} onClick={() => setVi(i)}>{x.peregon}</button>
          ))}
        </div>
        {v && stAfter && stBefore ? (
          <>
            <p className="muted small">{t('ob_hint')}</p>
            <PlayerBar p={p} range={range} />
            <div className="graphs">
              <StationView title={t('before_ob')} accent="#c2410c" stations={stBefore} trains={v.scenario.trains}
                schedule={v.oldin} station={v.k + 1} t={p.t} tracks={1} closedSegments={closedAt} />
              <StationView title={t('after_ob')} accent="#1c7c54" stations={stAfter} trains={v.scenario.trains}
                schedule={v.keyin} station={v.k + 1} t={p.t} plannedAll closedSegments={closedAt} />
            </div>
            <div style={{ marginTop: 10 }}>
              <div className="small muted">{t('whole_line')}</div>
              <LineScheme stations={stAfter} trains={v.scenario.trains} t={p.t} disruption={dis}
                lanes={[{ label: '', color: '#1c7c54', schedule: v.keyin }]} />
            </div>
            <div className="kpis" style={{ marginTop: 10 }}>
              <div className="kpi"><div className="kpi-label">{t('m_total')} · {t('before_ob')}</div>
                <div className="kpi-val fifo-c">{v.metrics_oldin.umumiy_kechikish_daq} {t('min')}</div></div>
              <div className="kpi ai"><div className="kpi-label">{t('m_total')} · {t('after_ob')}</div>
                <div className="kpi-val ai-c">{v.metrics_keyin.umumiy_kechikish_daq} {t('min')}</div>
                <Badge errors={v.xatolar} /></div>
              <div className="kpi"><div className="kpi-label">{isIncident ? t('saved_event_min') : t('saved_day')}</div>
                <div className="kpi-val">{v.tejaldi_daq} {t('min')}</div></div>
            </div>
          </>
        ) : <p className="muted">{t('ob_none')}</p>}
      </div>

      <div className="card">
        <h3>{t('cost_title')} <span className="est">{t('estimate_tag')}</span></h3>
        <div className="warn soft">{t('default_note')}</div>
        <div className="cost-grid">
          <NumInput label={t('cost_loops')} value={loops} onChange={setLoops} step={1} />
          <NumInput label={t('cost_loop_km')} value={len} onChange={setLen} note={t('cost_len_note')} step={0.1} />
          <NumInput label={t('cost_km')} value={perKm} onChange={setPerKm} note={t('cost_km_note')} />
          <NumInput label={t('cost_sw4')} value={sw} onChange={setSw} note={t('cost_sw_note')} />
          <NumInput label={t('idle_cost')} value={idle} onChange={setIdle} note={t('idle_note')} />
          {isIncident && <NumInput label={t('incidents_year')} value={inc} onChange={setInc} note={t('incidents_note')} step={1} />}
        </div>
        <div className="formula">
          <b>{t('cost_total_ob')}:</b>
          <div className="formula-live">{loops ?? '?'} × {len ?? '?'} km × {perKm != null ? fmtMoney(perKm) : '?'} + {sw != null ? fmtMoney(sw) : '?'} = <b>{total != null ? fmtMoney(total) : '?'}</b></div>
          <div className="small muted">{t('cost_bench')}</div>
        </div>
        <div className="kpis">
          <div className="kpi"><div className="kpi-label">{t('cost_total_ob')}</div><div className="kpi-val">{total != null ? fmtMoney(total) : '—'}</div></div>
          {isIncident && <div className="kpi"><div className="kpi-label">{t('saved_event')} ({t('saved_this_ob')}{v ? ` ${v.peregon}` : ''})</div>
            <div className="kpi-val">{perEvent != null ? fmtMoney(perEvent) : '—'}</div>
            <div className="small muted">{saved} {t('min')} ÷ 60 × {idle ?? '?'} $</div></div>}
          <div className="kpi"><div className="kpi-label">{t('saved_year')} ({t('saved_this_ob')}{v ? ` ${v.peregon}` : ''})</div>
            <div className="kpi-val">{perYear != null ? fmtMoney(perYear) : '—'}</div>
            <div className="small muted">{saved} {t('min')} ÷ 60 × {idle ?? '?'} $ × {isIncident ? (inc ?? '?') : DEFAULTS.daysPerYear}</div></div>
          <div className="kpi"><div className="kpi-label">{t('payback_years')}</div>
            <div className="kpi-val">{total != null && perYear ? `${Math.round(total / perYear).toLocaleString('ru-RU')} ${t('years')}` : '—'}</div></div>
        </div>
        {softDay != null && softYear != null && <div className="box-note">{t('compare_software', { m: softDay, d: fmtMoney(softYear) })}</div>}
        <p className="muted small">{t('only_delay_note')}</p>
        <details><summary className="small">{t('sources')}</summary>
          <ol className="src-list">{SOURCES.map(s => <li key={s.u}>{s.t} <a href={s.u} target="_blank" rel="noreferrer">{new URL(s.u).hostname}</a></li>)}</ol>
        </details>
      </div>
    </>
  )
}
