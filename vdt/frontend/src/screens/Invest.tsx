import { useEffect, useMemo, useState } from 'react'
import type { Data, Layout } from 'plotly.js'
import { loadInvestment } from '../data'
import type { InvestmentData } from '../types'
import Plot from '../components/Plot'
import NumInput, { fmtMoney } from '../components/NumInput'
import { Loading } from '../components/Common'
import { useT } from '../i18n'

export default function Invest() {
  const t = useT()
  const [d, setD] = useState<InvestmentData | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [price, setPrice] = useState<number | null>(null)
  useEffect(() => { loadInvestment().then(setD).catch(e => setErr(String(e))) }, [])

  const plot = useMemo(() => {
    if (!d) return null
    const rows = d.reyting
    const data: Data[] = [{
      type: 'bar', x: rows.map(r => r.bekat), y: rows.map(r => r.tejaldi_daq),
      marker: { color: rows.map(r => (r.sezilarli ? '#1c7c54' : '#b8bcc2')) },
      text: rows.map(r => `${r.tejaldi_daq}`), textposition: 'outside',
      hovertemplate: '%{x}: %{y} ' + t('min') + '<extra></extra>',
    } as Data]
    const noise = Math.max(d.shovqin_chegarasi ?? 0, 1)
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

  if (!d) return <Loading error={err ? t('invest_missing') : null} />
  return (
    <>
      <div className="card">
        <h3>{t('invest_title')}</h3>
        <div className="message">{t('invest_msg')}</div>
        {!d.tugallangan && <div className="warn">{t('invest_partial')} ({d.reyting.length}/10)</div>}
        {plot && <Plot data={plot.data} layout={plot.layout} height={380} />}
        <div className="legend-row">
          <span><span className="dot" style={{ background: '#1c7c54' }} />{t('significant')}</span>
          <span><span className="dot" style={{ background: '#b8bcc2' }} />{t('not_significant')}</span>
        </div>
        <p className="muted small">{t('protocol')}
          {d.protokol && ` (${d.protokol.asosiy_hisob_s} s + ${d.protokol.variant_hisob_s} s × ${d.protokol.seedlar.length})`}
          {d.hisob_daqiqa != null && ` · ${d.hisob_daqiqa} ${t('min')}`}
          {' · '}{t('synthetic')}</p>
      </div>
      <div className="card">
        <NumInput label={t('price_siding')} value={price} onChange={setPrice} />
        {price ? (
          <table className="mtable">
            <thead><tr><th>{t('station')}</th><th>{t('saved_min')}</th><th>{t('cost_per_min')}</th></tr></thead>
            <tbody>{d.reyting.map(r => (
              <tr key={r.bekat} className={r.sezilarli ? '' : 'greyed'}>
                <td>{r.bekat}</td><td className="num">{r.tejaldi_daq}</td>
                <td className="num">{r.tejaldi_daq > 0 ? fmtMoney(price / r.tejaldi_daq) : '—'}</td>
              </tr>))}</tbody>
          </table>
        ) : <p className="muted">{t('fill_fields')}</p>}
      </div>
    </>
  )
}
