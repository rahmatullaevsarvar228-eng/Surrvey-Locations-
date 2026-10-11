import { useEffect, useMemo, useState } from "react";
import { api, type CacheMeta, type SimResult, type SimulateOut } from "../lib/api";
import { useT } from "../lib/i18n";
import { fmt } from "../lib/store";
import { EChart } from "../components/EChart";
import { tok } from "../lib/charts";
import { FieldControls, HabitInputs, parseHabit, type FieldState, type HabitState } from "../components/Controls";

export function SimulatorPage({ cache }: { cache: CacheMeta }) {
  const { t } = useT();
  const [field, setField] = useState<FieldState>({ soil: "orta", method: "egat", kc_set: "uz" });
  const [planting, setPlanting] = useState(cache.planting);
  const [habit, setHabit] = useState<HabitState>({ every: "", mm: "" });
  const [price, setPrice] = useState("");
  const [energy, setEnergy] = useState("");
  const [data, setData] = useState<SimulateOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const hp = parseHabit(habit);

  useEffect(() => setPlanting(cache.planting), [cache.planting]);
  useEffect(() => {
    let alive = true;
    setErr(null);
    api.simulate({ field: { crop: cache.crop, ...field, planting }, cache_id: cache.id, habit: hp })
      .then((d) => alive && setData(d)).catch((e: Error) => alive && setErr(e.message));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cache.id, field.soil, field.method, field.kc_set, planting, hp?.every_days, hp?.mm]);

  const perM3 = (Number(price) || 0) + (Number(energy) || 0);
  const hasCost = price !== "" || energy !== "";

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      <aside className="card space-y-3 h-fit">
        <h1 className="text-[28px] font-semibold">{t("web.nav_sim")}</h1>
        <div className="text-sm text-muted">{t(`crop.${cache.crop}`)} · {cache.place}</div>
        <label>
          <span className="field-label">{t("web.planting")}</span>
          <input type="date" className="input num" value={planting} min={cache.start} max={cache.end}
                 onChange={(e) => e.target.value && setPlanting(e.target.value)} />
        </label>
        <FieldControls value={field} onChange={setField} />
        <HabitInputs value={habit} onChange={setHabit} />
        <fieldset className="border-t border-ink/10 pt-3">
          <legend className="font-medium">{t("web.cost_title")}</legend>
          <label className="block mt-2">
            <span className="field-label">{t("web.cost_price")}</span>
            <input className="input num" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
          </label>
          <label className="block mt-2">
            <span className="field-label">{t("web.cost_energy")}</span>
            <input className="input num" inputMode="decimal" value={energy} onChange={(e) => setEnergy(e.target.value)} />
          </label>
          <p className="text-sm text-muted mt-2">{t("web.cost_note")}</p>
        </fieldset>
      </aside>

      <section className="space-y-4" aria-live="polite">
        {err && <div role="alert" className="card text-alert">{t("web.error")}: {err}</div>}
        {!data && !err && <p className="text-muted">{t("web.loading")}</p>}
        {data && (
          <>
            <div className={`grid gap-4 ${data.habit ? "md:grid-cols-3" : "md:grid-cols-1"}`}>
              <ResultCard title={t("web.mode_fao")} r={data.fao} tone="water" />
              {data.habit && <ResultCard title={t("web.mode_habit")} r={data.habit} tone="soil" />}
              {data.habit && <DiffCard a={data.fao} b={data.habit} perM3={hasCost ? perM3 : null} />}
            </div>
            <div className="card"><Cumulative data={data} /></div>
          </>
        )}
      </section>
    </div>
  );
}

function ResultCard({ title, r, tone }: { title: string; r: SimResult; tone: string }) {
  const { t } = useT();
  return (
    <div className={`card border-t-8 border-${tone === "water" ? "water" : "sun"}`}>
      <div className="font-semibold mb-2">{title}</div>
      <div className="text-sm text-muted">{t("web.kpi_water")}</div>
      <div className="num kpi font-semibold">{fmt(r.suv_m3_ga)}<span className="text-base text-muted font-normal"> {t("web.unit_m3ha")}</span></div>
      <dl className="grid grid-cols-2 gap-2 mt-3 text-sm">
        <dt className="text-muted">{t("web.kpi_loss")}</dt><dd className="num text-right">{fmt(r.yoqotish_m3_ga)} {t("web.unit_m3ha")}</dd>
        <dt className="text-muted">{t("web.kpi_deep")}</dt><dd className="num text-right">{fmt(r.chuqur_m3_ga)} {t("web.unit_m3ha")}</dd>
        <dt className="text-muted">{t("web.kpi_events")}</dt><dd className="num text-right">{r.sugorishlar}</dd>
        <dt className="text-muted">{t("web.kpi_stress")}</dt><dd className={`num text-right ${r.stress_kunlari ? "text-alert font-semibold" : ""}`}>{r.stress_kunlari}</dd>
        <dt className="text-muted">{t("web.kpi_etc")}</dt><dd className="num text-right">{r.etc_mm} mm</dd>
      </dl>
    </div>
  );
}

function DiffCard({ a, b, perM3 }: { a: SimResult; b: SimResult; perM3: number | null }) {
  const { t } = useT();
  const dWater = b.suv_m3_ga - a.suv_m3_ga;
  return (
    <div className="card">
      <div className="font-semibold mb-2">{t("web.difference")} ({t("web.mode_habit")} − FAO-56)</div>
      <div className="text-sm text-muted">{t("web.kpi_water")}</div>
      <div className={`num kpi font-semibold ${dWater > 0 ? "text-alert" : "text-ink"}`}>
        {dWater > 0 ? "+" : ""}{fmt(dWater)}<span className="text-base text-muted font-normal"> {t("web.unit_m3ha")}</span>
      </div>
      <dl className="grid grid-cols-2 gap-2 mt-3 text-sm">
        <dt className="text-muted">{t("web.kpi_stress")}</dt>
        <dd className="num text-right">{b.stress_kunlari - a.stress_kunlari > 0 ? "+" : ""}{b.stress_kunlari - a.stress_kunlari}</dd>
      </dl>
      {perM3 !== null && (
        <p className="mt-3 font-medium">{t("web.cost_result", { sum: fmt(dWater * perM3) })}</p>
      )}
      <p className="text-sm text-muted mt-2">{t("web.diff_note")}</p>
    </div>
  );
}

function Cumulative({ data }: { data: SimulateOut }) {
  const { t, lang } = useT();
  const option = useMemo(() => {
    const cum = (rows: SimulateOut["fao"]["rows"]) => { let s = 0; return rows.map((r) => (s += r.sugorish_mm * 10)); };
    const series: object[] = [
      { name: t("web.mode_fao"), type: "line", symbol: "none", data: cum(data.fao.rows), lineStyle: { color: tok("water"), width: 3 }, itemStyle: { color: tok("water") } },
      { name: t("web.kpi_etc"), type: "line", symbol: "none", lineStyle: { color: tok("leaf"), type: "dotted", width: 2 }, itemStyle: { color: tok("leaf") },
        data: (() => { let s = 0; return data.fao.rows.map((r) => (s += r.etc * 10)); })() },
    ];
    if (data.habit) series.push({ name: t("web.mode_habit"), type: "line", symbol: "none", data: cum(data.habit.rows), lineStyle: { color: tok("soil"), width: 3 }, itemStyle: { color: tok("soil") } });
    return {
      textStyle: { fontFamily: "IBM Plex Sans", color: tok("muted") },
      tooltip: { trigger: "axis", valueFormatter: (v: number) => `${Math.round(v)} m³/ga` },
      legend: { type: "scroll", top: 0, textStyle: { color: tok("ink") } },
      grid: { left: 60, right: 20, top: 36, bottom: 28 },
      xAxis: { type: "category", data: data.fao.rows.map((r) => r.sana.slice(5)), axisLabel: { interval: 29 } },
      yAxis: { type: "value", name: "m³/ga", splitLine: { lineStyle: { color: tok("muted", 0.2) } } },
      series,
    };
  }, [data, lang]); // eslint-disable-line react-hooks/exhaustive-deps
  return <EChart option={option} height={320} label={t("web.kpi_water")} />;
}
