import { useEffect, useMemo, useState } from 'react'
import type { Data, Layout } from 'plotly.js'
import { loadObgon, loadScenario, type PresetName } from '../data'
import type { ObgonData, ScenarioData } from '../types'
import Plot from '../components/Plot'
import NumInput, { fmtMoney } from '../components/NumInput'
import { Loading, PresetPicker } from '../components/Common'
import InsertView from '../components/InsertView'
import { insertPassages } from '../components/lanes'
import LineScheme, { waitedSoFar } from '../components/LineScheme'
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
  const [pi, setPi] = useState<number | null>(null)   // yaqindan ko'riladigan punkt
  const [nSel, setNSel] = useState<number | null>(null)
  const [loops, setLoops] = useState<number | null>(DEFAULTS.obgonLoops)
  const [len, setLen] = useState<number | null>(DEFAULTS.obgonLoopKm)
  const [perKm, setPerKm] = useState<number | null>(DEFAULTS.trackPerKm)
  const [sw, setSw] = useState<number | null>(DEFAULTS.obgonSwitches)
  const [idle, setIdle] = useState<number | null>(DEFAULTS.idlePerHour)
  const [inc, setInc] = useState<number | null>(null)
  useEffect(() => { loadObgon().then(setOb).catch(e => setErr(String(e))); loadScenario('oddiy').then(setOdd) }, [])
  useEffect(() => { setPi(null); setNSel(null) }, [sc])
  const d = ob?.ssenariylar[sc as ObName] ?? null
  const full = d?.toliq
  const steps = useMemo(() => d?.bosqichlar ?? [], [d])
  const perPoint = loops != null && len != null && perKm != null && sw != null ? loops * len * perKm + sw : null

  // to'liq reja animatsiyasi
  const range = useMemo<[number, number]>(() => {
    if (!full) return [0, 720]
    let lo = Infinity, hi = 0
    for (const rows of Object.values(full.keyin)) for (const r of rows) { lo = Math.min(lo, r.kelish); hi = Math.max(hi, r.ketish ?? r.kelish) }
    return [Math.max(0, Math.floor(lo / 10) * 10), Math.ceil(hi / 10) * 10 + 10]
  }, [full])
  const p = usePlayer(range)
  // sukut bo'yicha — eng ko'p ishlatiladigan punkt (aylanma yo'lda eng ko'p kutish)
  const busiestLoop = useMemo(() => {
    if (!full) return 0
    // sukut bo'yicha — eng ko'p uchrashuv / quvib o'tish bo'lgan uchastka
    const m = insertPassages(full.scenario.stations, full.scenario.trains, full.keyin)
    let best = 0, bestN = -1, j = 0
    for (const list of m.values()) {
      const n = list.filter(p => p.lane !== 0).length
      if (n > bestN) { best = j; bestN = n }
      j++
    }
    return best
  }, [full])

  const planPlot = useMemo(() => {
    if (!steps.length) return null
    const x = steps.map(s => `${s.n}. ${s.qoshildi}`)
    const data: Data[] = [
      { type: 'bar', x, y: steps.map(s => s.tejaldi_daq), name: t('cum_saved'), marker: { color: '#1c7c54' },
        text: steps.map(s => `${s.tejaldi_daq}`), textposition: 'outside', hovertemplate: '%{x}: %{y} ' + t('min') + '<extra></extra>' } as Data,
      ...(perPoint != null ? [{ type: 'scatter', mode: 'lines+markers', x, y: steps.map(s => s.n * perPoint / 1e6), name: t('cum_cost') + ' (mln)',
        yaxis: 'y2', line: { color: '#c2410c', width: 2 }, hovertemplate: '%{y:.0f} mln $<extra></extra>' } as Data] : []),
    ]
    const layout: Partial<Layout> = {
      margin: { l: 60, r: 60, t: 20, b: 90 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: '#fff',
      yaxis: { title: { text: t('cum_saved') }, fixedrange: true, rangemode: 'tozero', gridcolor: '#eee' },
      yaxis2: { title: { text: 'mln $' }, overlaying: 'y', side: 'right', fixedrange: true, rangemode: 'tozero', showgrid: false },
      xaxis: { fixedrange: true, type: 'category', tickangle: -35 },
      legend: { orientation: 'h', y: 1.12 }, showlegend: true,
    }
    return { data, layout }
  }, [steps, perPoint, t])

  const singlePlot = useMemo(() => {
    if (!d) return null
    const rows = [...d.reyting].sort((a, b) => a.k - b.k)
    const data: Data[] = [{
      type: 'bar', x: rows.map(r => r.peregon), y: rows.map(r => r.tejaldi_daq),
      marker: { color: rows.map(r => (r.sezilarli ? '#1c7c54' : '#b8bcc2')) },
      text: rows.map(r => `${r.tejaldi_daq}`), textposition: 'outside',
      hovertemplate: '%{x}: %{y} ' + t('min') + '<extra></extra>',
    } as Data]
    const layout: Partial<Layout> = {
      margin: { l: 60, r: 20, t: 10, b: 50 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: '#fff',
      yaxis: { title: { text: t('saved_min') }, fixedrange: true, rangemode: 'tozero', gridcolor: '#eee' },
      xaxis: { fixedrange: true, type: 'category' },
    }
    return { data, layout }
  }, [d, t])

  if (!ob) return <Loading error={err ? t('siding_missing') : null} />
  const picker = <div className="toolbar"><PresetPicker value={sc} onChange={setSc} options={['osish30', 'oddiy', 'avariya']} /></div>
  if (!d) return <>{picker}<Loading error={t('siding_missing')} /></>

  const n = nSel ?? steps.length
  const step = steps.find(s => s.n === n)
  const saved = step?.tejaldi_daq ?? 0
  const totalCost = perPoint != null ? perPoint * n : null
  const isIncident = sc === 'avariya'
  const perEvent = idle != null ? (saved / 60) * idle : null
  const perYear = perEvent == null ? null : isIncident ? (inc != null ? perEvent * inc : null) : perEvent * DEFAULTS.daysPerYear
  const fm = odd?.fifo.metrics, am = odd?.ai.umumiy?.metrics
  const softDay = fm && am ? fm.umumiy_kechikish_daq - am.umumiy_kechikish_daq : null
  const softYear = softDay != null && idle != null ? (softDay / 60) * idle * DEFAULTS.daysPerYear : null
  const corridorKm = odd ? odd.scenario.stations[odd.scenario.stations.length - 1].km : null
  const trackCost = corridorKm != null && perKm != null ? corridorKm * perKm : null

  const stFull = full?.scenario.stations
  const loopIdx = stFull ? stFull.map((s, i) => (s.kind === 'jl' ? i : -1)).filter(i => i >= 0) : []
  const piEff = pi ?? busiestLoop
  const li = loopIdx[Math.min(piEff, loopIdx.length - 1)]
  const dis = full?.scenario.disruption
  const mb = full?.metrics_oldin.umumiy_kechikish_daq, ma = full?.metrics_keyin.umumiy_kechikish_daq
  const pct = mb && ma != null ? ((ma - mb) / mb) * 100 : null

  return (
    <>
      {picker}

      {full && stFull && (
        <div className="card">
          <h3>{t('full_title')}</h3>
          <p className="muted">{t('full_what')}</p>
          <div className="kpis">
            <div className="kpi"><div className="kpi-label">{t('m_total')} · {t('before_ob')}</div>
              <div className="kpi-val fifo-c">{mb} {t('min')}</div></div>
            <div className="kpi ai"><div className="kpi-label">{t('m_total')} · {t('lane_after')}</div>
              <div className="kpi-val ai-c">{ma} {t('min')} {pct != null && <small className="good">({pct.toFixed(0)}%)</small>}</div>
              <Badge errors={full.xatolar} /></div>
            <div className="kpi"><div className="kpi-label">{t('full_points')}: {full.punktlar} × {perPoint != null ? fmtMoney(perPoint) : '?'}</div>
              <div className="kpi-val">{perPoint != null ? fmtMoney(perPoint * full.punktlar) : '—'}</div>
              <div className="small muted">{t('vs_track')}: {trackCost != null ? fmtMoney(trackCost) : '—'}</div></div>
          </div>
          <PlayerBar p={p} range={range} />
          <LineScheme stations={stFull} trains={full.scenario.trains} t={p.t} disruption={dis} hideObgon
            lanes={[{ label: t('lane_before'), color: 'var(--fifo)', schedule: full.oldin, counter: waitedSoFar(full.scenario.trains, full.oldin, p.t) }]} />
          <LineScheme stations={stFull} trains={full.scenario.trains} t={p.t} disruption={dis}
            selected={li} onPickStation={i => { const j = loopIdx.indexOf(i); if (j >= 0) setPi(j) }}
            lanes={[{ label: t('lane_after'), color: 'var(--ai)', schedule: full.keyin, counter: waitedSoFar(full.scenario.trains, full.keyin, p.t) }]} />
          <div className="stview-bar" style={{ marginTop: 8 }}>
            <b>{t('pick_point')}:</b>
            {loopIdx.map((i, j) => (
              <button key={i} className={`btn chip ${j === piEff ? 'on' : ''}`} onClick={() => setPi(j)}>{stFull[i].name}</button>
            ))}
          </div>
          {li != null && (
            <div className="graphs">
              <InsertView title={t('before_ob')} accent="#c2410c" stations={stFull} trains={full.scenario.trains}
                schedule={full.oldin} jl={li} t={p.t} single />
              <InsertView title={t('after_ob')} accent="#1c7c54" stations={stFull} trains={full.scenario.trains}
                schedule={full.keyin} jl={li} t={p.t} planned />
            </div>
          )}
        </div>
      )}

      {steps.length > 0 && planPlot && (
        <div className="card">
          <h3>{t('plan_title')}</h3>
          <p className="muted">{t('plan_what')}</p>
          <Plot data={planPlot.data} layout={planPlot.layout} height={380} />
          <div className="scroll-x">
            <table className="mtable">
              <thead><tr><th>{t('step')}</th><th>{t('added')}</th><th className="n">{t('cum_saved')}</th><th className="n">{t('marginal')}</th><th className="n">{t('cum_cost')}</th></tr></thead>
              <tbody>{steps.map((s, i) => (
                <tr key={s.n} className={s.n === n ? 'sel-row' : ''} onClick={() => setNSel(s.n)} style={{ cursor: 'pointer' }}>
                  <td>{s.n}</td><td>{s.qoshildi}</td><td className="num">{s.tejaldi_daq}</td>
                  <td className="num">{s.tejaldi_daq - (i ? steps[i - 1].tejaldi_daq : 0)}</td>
                  <td className="num">{perPoint != null ? fmtMoney(perPoint * s.n) : '—'}</td>
                </tr>))}</tbody>
            </table>
          </div>
        </div>
      )}

      <div className="card">
        <h3>{t('cost_title')} <span className="est">{t('estimate_tag')}</span></h3>
        <div className="warn soft">{t('default_note')}</div>
        <div className="cost-grid">
          <label className="num-input"><span>{t('pick_step')}: <b>{n}</b></span>
            <input type="range" min={1} max={Math.max(1, steps.length)} value={n} onChange={e => setNSel(Number(e.target.value))} /></label>
          <NumInput label={t('cost_loops')} value={loops} onChange={setLoops} step={1} />
          <NumInput label={t('cost_loop_km')} value={len} onChange={setLen} note={t('ob_len_note')} step={0.1} />
          <NumInput label={t('cost_km')} value={perKm} onChange={setPerKm} note={t('cost_km_note')} />
          <NumInput label={t('cost_sw4')} value={sw} onChange={setSw} note={t('cost_sw_note')} />
          <NumInput label={t('idle_cost')} value={idle} onChange={setIdle} note={t('idle_note')} />
          {isIncident && <NumInput label={t('incidents_year')} value={inc} onChange={setInc} note={t('incidents_note')} step={1} />}
        </div>
        <div className="formula">
          <b>{t('cost_total_ob')}:</b>
          <div className="formula-live">{loops ?? '?'} × {len ?? '?'} km × {perKm != null ? fmtMoney(perKm) : '?'} + {sw != null ? fmtMoney(sw) : '?'} = <b>{perPoint != null ? fmtMoney(perPoint) : '?'}</b> · × {n} = <b>{totalCost != null ? fmtMoney(totalCost) : '?'}</b></div>
          <div className="small muted">{t('cost_bench')}</div>
        </div>
        <div className="kpis">
          <div className="kpi"><div className="kpi-label">{t('cum_cost')} ({n})</div><div className="kpi-val">{totalCost != null ? fmtMoney(totalCost) : '—'}</div>
            <div className="small muted">{t('vs_track')}: {trackCost != null ? fmtMoney(trackCost) : '—'}</div></div>
          <div className="kpi"><div className="kpi-label">{isIncident ? t('saved_event_min') : t('saved_day')}</div><div className="kpi-val">{saved} {t('min')}</div></div>
          <div className="kpi"><div className="kpi-label">{isIncident ? t('saved_event') : t('saved_year')}</div>
            <div className="kpi-val">{isIncident ? (perEvent != null ? fmtMoney(perEvent) : '—') : (perYear != null ? fmtMoney(perYear) : '—')}</div>
            <div className="small muted">{saved} {t('min')} ÷ 60 × {idle ?? '?'} ${isIncident ? '' : ` × ${DEFAULTS.daysPerYear}`}</div></div>
          <div className="kpi"><div className="kpi-label">{t('payback_years')}</div>
            <div className="kpi-val">{totalCost != null && perYear ? `${Math.round(totalCost / perYear).toLocaleString('ru-RU')} ${t('years')}` : '—'}</div></div>
        </div>
        {softDay != null && softYear != null && <div className="box-note">{t('compare_software', { m: softDay, d: fmtMoney(softYear) })}</div>}
        <p className="muted small">{t('only_delay_note')}</p>
        <details><summary className="small">{t('sources')}</summary>
          <ol className="src-list">{SOURCES.map(s => <li key={s.u}>{s.t} <a href={s.u} target="_blank" rel="noreferrer">{new URL(s.u).hostname}</a></li>)}</ol>
        </details>
      </div>

      <div className="card">
        <h3>{t('single_title')}</h3>
        <p className="muted small">{t('ob_protocol')} ({ob.hisob_s} s × {ob.seedlar.length} seed) · {t('synthetic')}</p>
        {singlePlot && <Plot data={singlePlot.data} layout={singlePlot.layout} height={260} />}
      </div>
    </>
  )
}
