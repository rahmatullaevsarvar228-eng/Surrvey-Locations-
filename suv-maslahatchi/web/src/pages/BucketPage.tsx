import { useEffect, useMemo, useRef, useState } from "react";
import { api, type CacheMeta, type SimResult, type SimRow, type SimulateOut } from "../lib/api";
import { useT } from "../lib/i18n";
import { fmt } from "../lib/store";
import { SoilBucket } from "../components/SoilBucket";
import { EChart } from "../components/EChart";
import { tok } from "../lib/charts";
import { FieldControls, HabitInputs, type FieldState, type HabitState, parseHabit } from "../components/Controls";

const SPEEDS = [1, 2, 4] as const;
const MS_PER_DAY = 260;

export function BucketPage({ cache }: { cache: CacheMeta }) {
  const { t } = useT();
  const [field, setField] = useState<FieldState>({ soil: "orta", method: "egat", kc_set: "uz" });
  const [habit, setHabit] = useState<HabitState>({ every: "", mm: "" });
  const [data, setData] = useState<SimulateOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [day, setDay] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const habitParsed = parseHabit(habit);

  useEffect(() => {
    let alive = true;
    setErr(null);
    api.simulate({ field: { crop: cache.crop, ...field }, cache_id: cache.id, habit: habitParsed })
      .then((d) => { if (alive) { setData(d); setDay((x) => Math.min(x, d.fao.rows.length - 1)); } })
      .catch((e: Error) => alive && setErr(e.message));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cache.id, cache.crop, field.soil, field.method, field.kc_set, habitParsed?.every_days, habitParsed?.mm]);

  const n = data?.fao.rows.length ?? 0;
  const timer = useRef<number | null>(null);
  useEffect(() => {
    if (!playing || !n) return;
    timer.current = window.setInterval(() => {
      setDay((d) => { if (d >= n - 1) { setPlaying(false); return d; } return d + 1; });
    }, MS_PER_DAY / speed);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [playing, speed, n]);

  // klaviatura: bo‘sh joy — boshlash/to‘xtatish, ← → — kun
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input,select,textarea,button")) return;
      if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
      if (e.key === "ArrowRight") setDay((d) => Math.min(n - 1, d + 1));
      if (e.key === "ArrowLeft") setDay((d) => Math.max(0, d - 1));
    };
    addEventListener("keydown", on);
    return () => removeEventListener("keydown", on);
  }, [n]);

  if (err) return <div role="alert" className="card text-alert">{t("web.error")}: {err}</div>;
  if (!data) return <p className="text-muted">{t("web.loading")}</p>;

  const rows = data.fao.rows;
  const row = rows[day];
  const hRow = data.habit?.rows[day];
  const zrMax = Math.max(...rows.map((r) => r.zr_m));

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <section aria-labelledby="stakan-h" className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <h1 id="stakan-h" className="text-[28px] font-semibold mr-auto">{t("web.nav_bucket")}</h1>
          <div className="text-lg" aria-live="polite">
            <span className="num">{row.sana}</span> · {t("web.day")} <span className="num">{row.das + 1}</span> · {t(`stage.${row.bosqich}`)}
          </div>
        </div>

        <div className={`grid gap-4 ${hRow ? "sm:grid-cols-2" : ""} justify-items-center`}>
          <SoilBucket row={row} zrMax={zrMax} title={t("web.mode_fao")} />
          {hRow && <SoilBucket row={hRow} zrMax={zrMax} title={t("web.mode_habit")} tone="soil" />}
        </div>

        <div className="card flex flex-wrap items-center gap-3">
          <button className="btn btn-primary min-w-[8rem] justify-center" onClick={() => {
            if (day >= n - 1) setDay(0);
            setPlaying(!playing);
          }}>
            {playing ? `❚❚ ${t("web.pause")}` : `▶ ${t("web.play")}`}
          </button>
          <button className="btn" onClick={() => { setPlaying(false); setDay(0); }}>↺ {t("web.reset")}</button>
          <div role="group" aria-label={t("web.speed")} className="flex gap-1">
            {SPEEDS.map((s) => (
              <button key={s} className={`btn px-2 ${s === speed ? "bg-ink/10" : ""}`} aria-pressed={s === speed}
                      onClick={() => setSpeed(s)}>{s}×</button>
            ))}
          </div>
          <label className="flex-1 min-w-[200px]">
            <span className="sr-only">{t("web.day")}</span>
            <input type="range" min={0} max={n - 1} value={day} className="w-full accent-[rgb(var(--water))]"
                   onChange={(e) => { setPlaying(false); setDay(Number(e.target.value)); }} />
          </label>
        </div>

        <div className="card">
          <Timeline rows={rows} habit={data.habit?.rows} day={day} />
        </div>
      </section>

      <aside className="space-y-4">
        <DayAdvice rows={rows} day={day} />
        <Totals res={data.fao} upto={day} title={t("web.mode_fao")} />
        {data.habit && <Totals res={data.habit} upto={day} title={t("web.mode_habit")} />}
        <div className="card space-y-3">
          <FieldControls value={field} onChange={setField} />
          <HabitInputs value={habit} onChange={setHabit} />
        </div>
        <Legend />
      </aside>
    </div>
  );
}

/** Shu kungi maslahat — engine simulyatsiyasi natijasidan o‘qiladi (qayta hisoblanmaydi). */
function DayAdvice({ rows, day }: { rows: SimRow[]; day: number }) {
  const { t } = useT();
  const r = rows[day];
  const next = rows.slice(day, day + 8).findIndex((x) => x.sugorish_mm > 0);
  let cls = "border-leaf", head = t("web.day_ok"), sub = "";
  if (r.das < 0 || r.bosqich === "tugagan") {
    head = t(`stage.${r.bosqich}`);
  } else if (r.sugorish_mm > 0) {
    cls = "border-water"; head = t("web.day_irrigate");
    sub = `≈ ${fmt(r.sugorish_mm * 10)} ${t("web.unit_m3ha")}`;
  } else if (next > 0) {
    cls = "border-sun"; head = t("web.day_wait", { k: next });
  }
  return (
    <div className={`card border-l-8 ${cls}`} aria-live="polite">
      <div className="text-sm text-muted">{t("web.advice_today")}</div>
      <div className="text-xl font-semibold">{head}</div>
      {sub && <div className="num kpi text-water">{sub}</div>}
      <div className="text-sm text-muted mt-2 num">
        ET0 {r.et0.toFixed(1)} · ETc {r.etc.toFixed(1)} · {t("web.rain")} {r.yomgir.toFixed(0)} mm
      </div>
    </div>
  );
}

function Totals({ res, upto, title }: { res: SimResult; upto: number; title: string }) {
  const { t } = useT();
  const s = useMemo(() => {
    const part = res.rows.slice(0, upto + 1);
    const gross = part.reduce((a, r) => a + r.sugorish_mm, 0);
    const net = part.reduce((a, r) => a + r.netto_mm, 0);
    const deep = part.reduce((a, r) => a + r.chuqur_mm, 0);
    return { water: gross * 10, loss: (gross - net + deep) * 10, deep: deep * 10,
             stress: part.filter((r) => r.stress).length, events: part.filter((r) => r.sugorish_mm > 0).length };
  }, [res, upto]);
  return (
    <div className="card">
      <div className="text-sm text-muted mb-1">{title}</div>
      <dl className="grid grid-cols-2 gap-2">
        <Kpi label={t("web.kpi_water")} value={fmt(s.water)} unit={t("web.unit_m3ha")} tone="water" />
        <Kpi label={t("web.kpi_loss")} value={fmt(s.loss)} unit={t("web.unit_m3ha")} tone={s.loss > 0 ? "alert" : "ink"} />
        <Kpi label={t("web.kpi_events")} value={String(s.events)} />
        <Kpi label={t("web.kpi_stress")} value={String(s.stress)} unit={t("web.unit_days")} tone={s.stress ? "alert" : "ink"} />
      </dl>
    </div>
  );
}

export function Kpi({ label, value, unit, tone = "ink" }: { label: string; value: string; unit?: string; tone?: string }) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className={`num text-[28px] font-semibold text-${tone}`}>{value}{unit && <span className="text-sm text-muted font-normal"> {unit}</span>}</dd>
    </div>
  );
}

function Legend() {
  const { t } = useT();
  const items: [string, string][] = [
    ["bg-water/60", t("web.reserve")], ["border-t-2 border-dashed border-ink h-0 mt-2", t("web.raw_line")],
    ["bg-soil", t("web.roots")], ["bg-alert rounded-full", t("web.deep_loss")],
  ];
  return (
    <ul className="card text-sm space-y-1">
      {items.map(([c, l]) => (
        <li key={l} className="flex items-center gap-2"><span className={`inline-block w-5 h-3 ${c}`} aria-hidden="true" />{l}</li>
      ))}
    </ul>
  );
}

function Timeline({ rows, habit, day }: { rows: SimRow[]; habit?: SimRow[]; day: number }) {
  const { t, lang } = useT();
  const option = useMemo(() => {
    const x = rows.map((r) => r.sana.slice(5));
    const reserve = rows.map((r) => +(r.taw_mm - r.tanqislik_mm).toFixed(1));
    const raw = rows.map((r) => +(r.taw_mm - r.raw_mm).toFixed(1));
    const taw = rows.map((r) => r.taw_mm);
    const series: object[] = [
      { name: "TAW", type: "line", data: taw, symbol: "none", lineStyle: { color: tok("muted"), width: 1 }, itemStyle: { color: tok("muted") } },
      { name: t("web.raw_line"), type: "line", data: raw, symbol: "none", lineStyle: { color: tok("ink"), type: "dashed", width: 1.5 }, itemStyle: { color: tok("ink") } },
      { name: t("web.reserve"), type: "line", data: reserve, symbol: "none", lineStyle: { color: tok("water"), width: 2 }, itemStyle: { color: tok("water") },
        areaStyle: { color: tok("water", 0.18) },
        markLine: { symbol: "none", silent: true, data: [{ xAxis: day }], lineStyle: { color: tok("ink"), width: 2 }, label: { show: false } } },
      { name: t("web.irrigation"), type: "bar", yAxisIndex: 1, data: rows.map((r) => r.netto_mm), itemStyle: { color: tok("water", 0.7) }, barMaxWidth: 6 },
      { name: t("web.rain"), type: "bar", yAxisIndex: 1, data: rows.map((r) => r.yomgir), itemStyle: { color: tok("leaf", 0.8) }, barMaxWidth: 6 },
    ];
    if (habit) series.push({ name: t("web.mode_habit"), type: "line", symbol: "none",
      data: habit.map((r) => +(r.taw_mm - r.tanqislik_mm).toFixed(1)), lineStyle: { color: tok("soil"), width: 2 }, itemStyle: { color: tok("soil") } });
    return {
      textStyle: { fontFamily: "IBM Plex Sans", color: tok("muted") },
      tooltip: { trigger: "axis", valueFormatter: (v: number) => `${v} mm` },
      legend: { type: "scroll", top: 0, textStyle: { color: tok("ink") } },
      grid: { left: 44, right: 44, top: 44, bottom: 28 },
      xAxis: { type: "category", data: x, axisLabel: { interval: 29 } },
      yAxis: [{ type: "value", name: "mm", splitLine: { lineStyle: { color: tok("muted", 0.2) } } },
              { type: "value", name: "mm", inverse: false, splitLine: { show: false } }],
      series,
    };
  }, [rows, habit, day, lang]); // eslint-disable-line react-hooks/exhaustive-deps
  return <EChart option={option} height={280} label={t("web.reserve")} />;
}
