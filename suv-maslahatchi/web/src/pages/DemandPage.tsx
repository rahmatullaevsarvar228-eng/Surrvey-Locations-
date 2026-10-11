import { useEffect, useMemo, useState } from "react";
import { api, type CacheMeta, type DemandOut } from "../lib/api";
import { useT } from "../lib/i18n";
import { fmt } from "../lib/store";
import { EChart } from "../components/EChart";
import { tok } from "../lib/charts";

function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export function DemandPage({ cache }: { cache: CacheMeta }) {
  const { t } = useT();
  const [today, setToday] = useState(() => addDays(cache.planting, 90));
  const [data, setData] = useState<DemandOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => setToday(addDays(cache.planting, 90)), [cache.planting]);
  useEffect(() => {
    let alive = true;
    api.demand(cache.id, today).then((d) => alive && setData(d)).catch((e: Error) => alive && setErr(e.message));
    return () => { alive = false; };
  }, [cache.id, today]);

  const option = useMemo(() => data && {
    textStyle: { fontFamily: "IBM Plex Sans", color: tok("muted") },
    tooltip: { trigger: "axis" },
    grid: { left: 64, right: 20, top: 24, bottom: 28 },
    xAxis: { type: "category", data: data.days.map((d) => d.sana.slice(5)) },
    yAxis: { type: "value", name: "m³", splitLine: { lineStyle: { color: tok("muted", 0.2) } } },
    series: [{ type: "bar", data: data.days.map((d) => d.m3), itemStyle: { color: tok("water"), borderRadius: [6, 6, 0, 0] },
               label: { show: true, position: "top", color: tok("ink"), fontFamily: "IBM Plex Mono", formatter: (p: { value: number }) => (p.value ? fmt(p.value) : "") } }],
  }, [data]);

  const label = t("app.sample_label");
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="mr-auto">
          <h1 className="text-[28px] font-semibold">{t("web.demand_title")}</h1>
          <p className="text-muted">{t("web.demand_note", { label })}</p>
        </div>
        <label>
          <span className="field-label">{t("web.demand_date")}</span>
          <input type="date" className="input num" value={today} min={addDays(cache.start, 7)} max={addDays(cache.end, -7)}
                 onChange={(e) => e.target.value && setToday(e.target.value)} />
        </label>
      </div>
      {err && <div role="alert" className="card text-alert">{t("web.error")}: {err}</div>}
      {data && option && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="card"><div className="text-sm text-muted">{t("web.demand_m3")} · 7 {t("web.unit_days")}</div>
              <div className="num kpi font-semibold text-water">{fmt(data.days.reduce((a, d) => a + d.m3, 0))}</div></div>
            <div className="card"><div className="text-sm text-muted">{t("web.demand_fields")}</div>
              <div className="num kpi font-semibold">{data.fields.length}</div><div className="text-sm text-muted">{label}</div></div>
            <div className="card"><div className="text-sm text-muted">{t("web.area")}</div>
              <div className="num kpi font-semibold">{fmt(data.total_area_ha)}</div></div>
          </div>
          <div className="card"><EChart option={option} height={300} label={t("web.demand_title")} /></div>
          <div className="card overflow-x-auto">
            <h2 className="font-semibold mb-2">{t("web.fields_table")} <span className="text-sm font-normal px-2 py-0.5 rounded bg-sun/20">{label}</span></h2>
            <table className="w-full text-sm">
              <thead className="text-muted text-left">
                <tr><th className="py-1 pr-3">ID</th><th className="pr-3">{t("web.soil")}</th><th className="pr-3">{t("web.method")}</th>
                  <th className="pr-3 text-right">{t("web.area")}</th><th className="pr-3">{t("web.planting")}</th>
                  <th className="pr-3">{t("web.last_irrigation")}</th><th className="pr-3 text-right">{t("web.reserve")}</th><th>{t("web.advice_today")}</th></tr>
              </thead>
              <tbody>
                {data.fields.map((f) => (
                  <tr key={f.id} className="border-t border-ink/10">
                    <td className="py-1 pr-3 num">{f.id}</td><td className="pr-3">{t(`soil.${f.soil}`)}</td><td className="pr-3">{t(`method.${f.method}`)}</td>
                    <td className="pr-3 num text-right">{f.area_ha}</td><td className="pr-3 num">{f.planting}</td><td className="pr-3 num">{f.last_irrigation}</td>
                    <td className="pr-3 num text-right">{f.zaxira === null ? "—" : `${Math.round(f.zaxira * 100)}%`}</td>
                    <td className={f.holat === "bugun" ? "text-water font-semibold" : ""}>
                      {f.holat === "bugun" ? `${t("web.day_irrigate")} · ${fmt(f.m3_jami)} m³`
                        : f.holat === "tez_orada" ? t("web.day_wait", { k: f.kun ?? 0 })
                        : f.holat === "kerak_emas" ? t("web.day_ok") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
