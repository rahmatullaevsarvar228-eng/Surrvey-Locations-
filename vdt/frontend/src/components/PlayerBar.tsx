import { hhmm } from '../data'
import { useT } from '../i18n'
import type { usePlayer } from './usePlayer'

export default function PlayerBar({ p, range }: { p: ReturnType<typeof usePlayer>; range: [number, number] }) {
  const t = useT()
  return (
    <div className="player">
      {p.playing
        ? <button className="btn primary" onClick={p.pause}>{t('pause')}</button>
        : <button className="btn primary" onClick={p.play}>{t('play')}</button>}
      <button className="btn" onClick={p.reset}>{t('reset')}</button>
      <span className="muted">{t('speed')}:</span>
      {[1, 10, 60].map(s => (
        <button key={s} className={`btn chip ${p.speed === s ? 'on' : ''}`} onClick={() => p.setSpeed(s)}
          title={t('speed_hint')}>×{s}</button>
      ))}
      <input type="range" min={range[0]} max={range[1]} step={1} value={p.t}
        onChange={e => p.seek(Number(e.target.value))} className="scrub" />
      <span className="clock">{hhmm(p.t)}</span>
    </div>
  )
}
