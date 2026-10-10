import { hhmm, pct } from '../data'
import { useT, type TKey } from '../i18n'
import type { AiResult, FifoResult, Objective } from '../types'

function Diff({ a, b, lowerBetter = true }: { a: number | null | undefined; b: number | null | undefined; lowerBetter?: boolean }) {
  if (a == null || b == null) return <span className="diff na">—</span>
  const d = pct(a, b)
  if (d == null) return <span className="diff na">—</span>
  const good = lowerBetter ? d < 0 : d > 0
  return <span className={`diff ${Math.abs(d) < 0.05 ? 'zero' : good ? 'good' : 'bad'}`}>
    {d > 0 ? '+' : ''}{d.toFixed(1)}%</span>
}

export function Badge({ errors }: { errors: string[] | null | undefined }) {
  const t = useT()
  if (errors == null) return null
  return errors.length === 0
    ? <span className="badge ok">{t('badge_ok')}</span>
    : <span className="badge bad" title={errors.join('\n')}>✗ {errors.length} {t('badge_bad')}</span>
}

export function StatusTag({ ai }: { ai: AiResult }) {
  const t = useT()
  const key = `st_${ai.status}` as TKey
  return <span className="status-tag" title={t('status')}>
    {t('status')}: <b>{t(key) === key ? ai.status : t(key)}</b> · {t('calc_time')} {ai.hisob_soniya} {t('sec')}
  </span>
}

export default function MetricsPanel({ fifo, ai, objective }: { fifo: FifoResult; ai: AiResult; objective: Objective }) {
  const t = useT()
  const fm = fifo.metrics, am = ai.metrics
  if (!am) return null
  const heroKey = objective === 'ustuvorlik' ? 'vaznli_kechikish' : 'umumiy_kechikish_daq'
  const heroLabel: TKey = objective === 'ustuvorlik' ? 'm_weighted' : 'm_total'
  const heroPct = fm ? pct(fm[heroKey], am[heroKey]) : null
  const rows: { k: TKey; f: number | null; a: number; fmt?: (v: number) => string }[] = [
    { k: 'm_total', f: fm?.umumiy_kechikish_daq ?? null, a: am.umumiy_kechikish_daq },
    { k: 'm_avg', f: fm?.ortacha_kechikish_daq ?? null, a: am.ortacha_kechikish_daq },
    { k: 'm_weighted', f: fm?.vaznli_kechikish ?? null, a: am.vaznli_kechikish },
    { k: 'm_waits', f: fm?.kutish_toxtashlari ?? null, a: am.kutish_toxtashlari },
    { k: 'm_last', f: fm?.oxirgi_yetib_kelish_daq ?? null, a: am.oxirgi_yetib_kelish_daq, fmt: hhmm },
  ]
  const kinds = ['yuk', 'yolovchi', 'tezyurar'] as const
  return (
    <div className="metrics">
      <div className="hero">
        <div className="hero-label">{t(heroLabel)}</div>
        <div className="hero-nums">
          <div><small>{t('fifo_short')}</small><b className="fifo-c">{fm ? fm[heroKey] : 'TUPIK'}</b></div>
          <div className="arrow">→</div>
          <div><small>{t('ai_short')}</small><b className="ai-c">{am[heroKey]}</b></div>
        </div>
        <div className={`hero-pct ${heroPct == null ? 'text good' : heroPct < 0 ? 'good' : ''}`}>
          {heroPct == null ? t('ai_rescued') : `${heroPct > 0 ? '+' : ''}${heroPct.toFixed(1)}%`}
        </div>
      </div>
      <table className="mtable">
        <thead><tr><th></th><th className="fifo-c">{t('fifo_short')}</th><th className="ai-c">{t('ai_short')}</th><th>{t('diff')}</th></tr></thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.k}>
              <td>{t(r.k)}</td>
              <td className="num">{r.f == null ? '—' : (r.fmt ? r.fmt(r.f) : r.f)}</td>
              <td className="num">{r.fmt ? r.fmt(r.a) : r.a}</td>
              <td>{r.k === 'm_last' ? null : <Diff a={r.f} b={r.a} />}</td>
            </tr>
          ))}
          <tr className="sub"><td colSpan={4}>{t('m_kind')}</td></tr>
          {kinds.filter(k => am.tur_boyicha_ortacha[k] != null).map(k => (
            <tr key={k}>
              <td className="indent">{t(`k_${k}`)}</td>
              <td className="num">{fm?.tur_boyicha_ortacha[k] ?? '—'}</td>
              <td className="num">{am.tur_boyicha_ortacha[k]}</td>
              <td><Diff a={fm?.tur_boyicha_ortacha[k]} b={am.tur_boyicha_ortacha[k]} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
