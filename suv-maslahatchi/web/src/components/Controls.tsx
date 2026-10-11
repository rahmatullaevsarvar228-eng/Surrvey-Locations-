import { useT } from "../lib/i18n";

export interface FieldState { soil: string; method: string; kc_set: "uz" | "fao" }
export interface HabitState { every: string; mm: string }

const SOILS = ["yengil", "orta", "ogir"] as const;
const METHODS = ["egat", "yomgir", "tomchi"] as const;

export function FieldControls({ value, onChange }: { value: FieldState; onChange: (v: FieldState) => void }) {
  const { t } = useT();
  return (
    <div className="grid gap-3">
      <label>
        <span className="field-label">{t("web.soil")}</span>
        <select className="input" value={value.soil} onChange={(e) => onChange({ ...value, soil: e.target.value })}>
          {SOILS.map((s) => <option key={s} value={s}>{t(`soil.${s}`)}</option>)}
        </select>
        <span className="block text-sm text-muted mt-1">{t(`soil_hint.${value.soil}`)}</span>
      </label>
      <label>
        <span className="field-label">{t("web.method")}</span>
        <select className="input" value={value.method} onChange={(e) => onChange({ ...value, method: e.target.value })}>
          {METHODS.map((m) => <option key={m} value={m}>{t(`method.${m}`)}</option>)}
        </select>
      </label>
      <label className="dev-only">
        <span className="field-label">Kc</span>
        <select className="input" value={value.kc_set} onChange={(e) => onChange({ ...value, kc_set: e.target.value as "uz" | "fao" })}>
          <option value="uz">{t("web.kc_uz")}</option>
          <option value="fao">{t("web.kc_fao")}</option>
        </select>
      </label>
    </div>
  );
}

export function parseHabit(h: HabitState): { every_days: number; mm: number } | null {
  const every = Number(h.every), mm = Number(h.mm);
  if (!h.every || !h.mm || !Number.isFinite(every) || !Number.isFinite(mm)) return null;
  if (every < 1 || every > 60 || mm <= 0 || mm > 500) return null;
  return { every_days: Math.round(every), mm };
}

/** Fermer odatiy jadvali — bo‘sh maydonlar: raqamlarni foydalanuvchi o‘zi kiritadi. */
export function HabitInputs({ value, onChange }: { value: HabitState; onChange: (v: HabitState) => void }) {
  const { t } = useT();
  return (
    <fieldset className="border-t border-ink/10 pt-3">
      <legend className="font-medium">{t("web.mode_habit")}</legend>
      <div className="grid grid-cols-2 gap-2 mt-2">
        <label>
          <span className="field-label">{t("web.habit_every")}</span>
          <input className="input num" inputMode="numeric" value={value.every}
                 onChange={(e) => onChange({ ...value, every: e.target.value })} />
        </label>
        <label>
          <span className="field-label">{t("web.habit_mm")}</span>
          <input className="input num" inputMode="decimal" value={value.mm}
                 onChange={(e) => onChange({ ...value, mm: e.target.value })} />
        </label>
      </div>
      <p className="text-sm text-muted mt-2">{t("web.habit_note")}</p>
      <p className="text-sm text-muted">{t("web.habit_mm_hint")}</p>
    </fieldset>
  );
}
