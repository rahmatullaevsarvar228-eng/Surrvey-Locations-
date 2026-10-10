import { useEffect, useState } from 'react'
import { loadScenario, type PresetName } from '../data'
import type { Objective, ScenarioData } from '../types'
import NumInput, { fmtMoney } from '../components/NumInput'
import { Loading, ObjectivePicker, PresetPicker } from '../components/Common'
import { useT } from '../i18n'

export default function Econ() {
  const t = useT()
  const [preset, setPreset] = useState<PresetName>('oddiy')
  const [obj, setObj] = useState<Objective>('umumiy')
  const [d, setD] = useState<ScenarioData | null>(null)
  const [cost, setCost] = useState<number | null>(null)
  const [perDay, setPerDay] = useState<number | null>(null)
  const [days, setDays] = useState<number | null>(null)
  const [track, setTrack] = useState<number | null>(null)
  useEffect(() => { setD(null); loadScenario(preset).then(setD) }, [preset])
  if (!d) return <Loading />
  const fm = d.fifo.metrics, am = d.ai[obj]?.metrics
  const n = d.scenario.trains.length
  const savedTotal = fm && am ? fm.umumiy_kechikish_daq - am.umumiy_kechikish_daq : null
  const perTrain = savedTotal != null ? savedTotal / n : null
  const hoursDay = perTrain != null && perDay != null ? (perTrain * perDay) / 60 : null
  const year = hoursDay != null && cost != null && days != null ? hoursDay * cost * days : null
  return (
    <>
      <div className="toolbar">
        <PresetPicker value={preset} onChange={setPreset} options={['oddiy', 'osish30']} />
        <ObjectivePicker value={obj} onChange={setObj} />
      </div>
      <div className="card">
        <h3>{t('econ_base')}</h3>
        {savedTotal != null && perTrain != null ? (
          <div className="kpis">
            <div className="kpi"><div className="kpi-label">{t('m_total')} ({t('fifo_short')} → {t('ai_short')})</div>
              <div className="kpi-val">{fm!.umumiy_kechikish_daq} → <span className="ai-c">{am!.umumiy_kechikish_daq}</span></div>
              <div className="small muted">{n} {t('train').toLowerCase()} · {t('synthetic')}</div></div>
            <div className="kpi"><div className="kpi-label">{t('econ_saved_per_train')}</div>
              <div className="kpi-val ai-c">{perTrain.toFixed(1)} {t('min')}</div></div>
          </div>
        ) : <p className="muted">—</p>}
      </div>
      <div className="card">
        <div className="warn soft">{t('econ_warn')}</div>
        <div className="inputs">
          <NumInput label={t('idle_cost')} value={cost} onChange={setCost} />
          <NumInput label={t('trains_day')} value={perDay} onChange={setPerDay} />
          <NumInput label={t('days_year')} value={days} onChange={setDays} />
          <NumInput label={t('track_cost')} value={track} onChange={setTrack} />
        </div>
        <div className="formula">
          <b>{t('formula')}:</b> {t('formula_text')}
          <div className="formula-live">
            ({perTrain != null ? perTrain.toFixed(1) : '?'} {t('min')} × {perDay ?? '?'} / 60) × {cost != null ? fmtMoney(cost) : '?'} × {days ?? '?'}
            {' = '}<b>{year != null ? fmtMoney(year) : '?'}</b>
          </div>
        </div>
        {year != null ? (
          <div className="kpis">
            <div className="kpi ai"><div className="kpi-label">{t('result_year')}</div>
              <div className="kpi-val">{fmtMoney(year)}</div></div>
            {track != null && year > 0 && <div className="kpi"><div className="kpi-label">{t('payback')}</div>
              <div className="kpi-val">{(track / year).toFixed(1)} {t('years')}</div></div>}
          </div>
        ) : <p className="muted">{t('fill_fields')}</p>}
      </div>
    </>
  )
}
