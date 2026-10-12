import { useT } from '../i18n'

// Bo'sh qiymat = null. Hech qanday narx oldindan to'ldirilmaydi.
export default function NumInput({ label, value, onChange, note, step }: {
  label: string; value: number | null; onChange: (v: number | null) => void; note?: string; step?: number
}) {
  const t = useT()
  return (
    <label className="num-input">
      <span>{label}</span>
      <input type="number" min={0} step={step ?? 'any'} placeholder={t('enter_source')} value={value ?? ''}
        onChange={e => onChange(e.target.value === '' ? null : Math.max(0, Number(e.target.value)))} />
      {note && <span className="note">{note}</span>}
    </label>
  )
}

export function fmtMoney(v: number): string {
  return '$' + Math.round(v).toLocaleString('en-US').replace(/,/g, ' ')
}
