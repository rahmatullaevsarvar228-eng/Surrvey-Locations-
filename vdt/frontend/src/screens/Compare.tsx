import { useEffect, useState } from 'react'
import { loadScenario, type PresetName } from '../data'
import type { Objective, ScenarioData } from '../types'
import Comparison from '../components/Comparison'
import { Loading, ObjectivePicker, PresetPicker } from '../components/Common'
import { useT } from '../i18n'

export default function Compare() {
  const t = useT()
  const [preset, setPreset] = useState<PresetName>('oddiy')
  const [obj, setObj] = useState<Objective>('umumiy')
  const [data, setData] = useState<ScenarioData | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    setData(null); setErr(null)
    loadScenario(preset).then(d => live && setData(d)).catch(e => live && setErr(String(e)))
    return () => { live = false }
  }, [preset])
  return (
    <>
      <div className="toolbar">
        <PresetPicker value={preset} onChange={setPreset} />
        <ObjectivePicker value={obj} onChange={setObj} />
        {data && <span className="muted small">{t('cache_note')} · seed {data.seed} · {data.time_limit} {t('sec')}</span>}
      </div>
      {data ? <Comparison key={preset} data={data} objective={obj} /> : <Loading error={err} />}
    </>
  )
}
