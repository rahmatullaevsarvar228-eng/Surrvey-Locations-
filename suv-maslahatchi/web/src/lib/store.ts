// Foydalanuvchi qulayliklari (til, mavzu) — localStorage; xatoga chidamli.
export function load(key: string, fallback: string): string {
  try { return localStorage.getItem(`suv.${key}`) ?? fallback; } catch { return fallback; }
}
export function save(key: string, value: string): void {
  try { localStorage.setItem(`suv.${key}`, value); } catch { /* maxfiy rejim */ }
}
export const isStage = (): boolean => new URLSearchParams(location.search).get("stage") === "1";
export const fmt = (n: number): string =>
  Math.round(n).toLocaleString("ru-RU").replace(/[\u00a0\u202f]/g, "\u2009");
