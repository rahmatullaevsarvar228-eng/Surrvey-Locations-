import { useEffect, useState } from 'react'
import { hhmm, KIND_COLOR, loadScenario, type PresetName } from '../data'
import type { ScenarioData } from '../types'
import LineScheme from '../components/LineScheme'
import { Loading, PresetPicker } from '../components/Common'
import { useT } from '../i18n'

export default function Corridor() {
  const t = useT()
  const [preset, setPreset] = useState<PresetName>('oddiy')
  const [data, setData] = useState<ScenarioData | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    setData(null)
    loadScenario(preset).then(setData).catch(e => setErr(String(e)))
  }, [preset])
  if (!data) return <><PresetPicker value={preset} onChange={setPreset} /><Loading error={err} /></>
  const { stations, trains, disruption } = data.scenario
  return (
    <>
      <div className="toolbar"><PresetPicker value={preset} onChange={setPreset} /></div>
      <div className="card">
        <h3>{t('corridor_title')}</h3>
        <p className="muted">{t('corridor_hint')}</p>
        <LineScheme stations={stations} trains={[]} t={0} disruption={disruption}
          lanes={[{ label: '', color: '#333', schedule: {} }]} />
        <div className="st-table">
          {stations.map((s, i) => (
            <div key={s.name} className="st-cell">
              <b>{s.name}</b><span>{s.km} km</span>
              <span>{i === 0 || i === stations.length - 1 ? t('terminal') : `${s.tracks} ${t('tracks')}`}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="card">
        <h3>{t('trains_table')} ({trains.length})</h3>
        <div className="scroll-x">
          <table className="ttable">
            <thead><tr><th>ID</th><th>{t('c_kind')}</th><th>{t('c_dir')}</th><th>{t('c_speed')}</th>
              <th>{t('c_release')}</th><th>{t('c_stops')}</th><th>{t('c_weight')}</th></tr></thead>
            <tbody>
              {trains.map(tr => (
                <tr key={tr.id}>
                  <td><b>{tr.id}</b></td>
                  <td><span className="dot" style={{ background: KIND_COLOR[tr.kind] }} />{t(`k_${tr.kind}`)}</td>
                  <td>{tr.direction === 1 ? `${stations[0].name} → ${stations[stations.length - 1].name}` : `${stations[stations.length - 1].name} → ${stations[0].name}`}</td>
                  <td className="num">{tr.speed}</td>
                  <td className="num">{hhmm(tr.release)}</td>
                  <td>{Object.keys(tr.stops).map(k => stations[Number(k)].name).join(', ') || '—'}</td>
                  <td className="num">{tr.weight}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
