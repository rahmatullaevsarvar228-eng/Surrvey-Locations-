import { PRESETS, type PresetName } from '../data'
import { useT } from '../i18n'
import type { Objective } from '../types'

export function PresetPicker({ value, onChange, options = PRESETS }: {
  value: PresetName; onChange: (v: PresetName) => void; options?: PresetName[]
}) {
  const t = useT()
  return (
    <div className="seg">
      <span className="muted">{t('scenario')}:</span>
      {options.map(p => (
        <button key={p} className={`btn chip ${value === p ? 'on' : ''}`} onClick={() => onChange(p)}>
          {t(`sc_${p}`)}
        </button>
      ))}
    </div>
  )
}

export function ObjectivePicker({ value, onChange }: { value: Objective; onChange: (v: Objective) => void }) {
  const t = useT()
  return (
    <div className="seg">
      <span className="muted">{t('objective')}:</span>
      {(['umumiy', 'ustuvorlik'] as const).map(o => (
        <button key={o} className={`btn chip ${value === o ? 'on' : ''}`} onClick={() => onChange(o)}>
          {t(`obj_${o}`)}
        </button>
      ))}
    </div>
  )
}

export function Loading({ error }: { error?: string | null }) {
  const t = useT()
  return <div className="card muted">{error ? `${t('load_error')} (${error})` : t('loading')}</div>
}
