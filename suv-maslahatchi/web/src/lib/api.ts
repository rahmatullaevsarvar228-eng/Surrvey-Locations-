// API turlari engine/suv_engine.py dagi TypedDict larga mos. Hisob-kitob faqat serverda (engine).
export type Holat = "bugun" | "tez_orada" | "kerak_emas" | "mavsum_yoq";
export type Stage = "ekilmagan" | "boshlangich" | "rivojlanish" | "orta" | "kechki" | "tugagan";

export interface CacheMeta {
  id: string; place: string; lat: number; lon: number; start: string; end: string;
  crop: "paxta" | "bugdoy"; planting: string; source: string; fetched_at: string; synthetic: boolean;
}
export interface SimRow {
  sana: string; das: number; bosqich: Stage; et0: number; etc: number; yomgir: number;
  sugorish_mm: number; netto_mm: number; chuqur_mm: number; tanqislik_mm: number;
  taw_mm: number; raw_mm: number; zr_m: number; stress: boolean;
}
export interface SimResult {
  rows: SimRow[]; suv_m3_ga: number; yoqotish_m3_ga: number; chuqur_m3_ga: number;
  stress_kunlari: number; sugorishlar: number; etc_mm: number;
}
export interface FieldIn {
  crop: string; soil: string; method: string; planting?: string | null; area_ha?: number;
  kc_set?: "uz" | "fao"; eff?: number | null;
}
export interface SimulateOut {
  meta: CacheMeta; field: FieldIn & { planting: string }; fao: SimResult; habit: SimResult | null;
}
export interface DemandOut {
  meta: CacheMeta; today: string; total_area_ha: number;
  days: { sana: string; m3: number; dalalar: number }[];
  fields: { id: string; crop: string; soil: string; method: string; area_ha: number; planting: string;
            last_irrigation: string; holat: Holat | null; kun: number | null; m3_jami: number;
            zaxira: number | null }[];
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...init });
  const js = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((js as { detail?: string }).detail ?? `HTTP ${r.status}`);
  return js as T;
}

export const api = {
  caches: () => req<{ caches: CacheMeta[]; allow_synthetic: boolean }>("/api/demo"),
  simulate: (body: { field: FieldIn; cache_id: string; habit?: { every_days: number; mm: number } | null }) =>
    req<SimulateOut>("/api/simulate", { method: "POST", body: JSON.stringify(body) }),
  demand: (cache_id: string, today?: string) =>
    req<DemandOut>(`/api/demand?cache_id=${encodeURIComponent(cache_id)}${today ? `&today=${today}` : ""}`),
};
