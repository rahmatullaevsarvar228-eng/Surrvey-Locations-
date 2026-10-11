import { useEffect, useState } from "react";
import { LangCtx, translate, type Lang } from "./lib/i18n";
import { isStage, load, save } from "./lib/store";
import { useCaches } from "./lib/useCaches";
import type { CacheMeta } from "./lib/api";
import { BucketPage } from "./pages/BucketPage";
import { SimulatorPage } from "./pages/SimulatorPage";
import { DemandPage } from "./pages/DemandPage";
import { SciencePage } from "./pages/SciencePage";

const ROUTES = ["stakan", "sim", "uyushma", "ilm"] as const;
type Route = (typeof ROUTES)[number];
const NAV: Record<Route, string> = { stakan: "web.nav_bucket", sim: "web.nav_sim", uyushma: "web.nav_demand", ilm: "web.nav_science" };

function currentRoute(): Route {
  const h = location.hash.replace(/^#\/?/, "") as Route;
  return ROUTES.includes(h) ? h : "stakan";
}

export function App() {
  const [lang, setLang] = useState<Lang>(() => (load("lang", "uz") === "ru" ? "ru" : "uz"));
  const [theme, setTheme] = useState(() => load("theme", "auto"));
  const [route, setRoute] = useState<Route>(currentRoute);
  const { caches, error } = useCaches();
  const [cacheId, setCacheId] = useState<string>(() => load("cache", ""));
  const t = (k: string, v?: Record<string, string | number>) => translate(lang, k, v);

  useEffect(() => {
    const on = () => setRoute(currentRoute());
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  useEffect(() => {
    const root = document.documentElement;
    root.lang = lang;
    if (theme === "auto") root.removeAttribute("data-theme"); else root.dataset.theme = theme;
    if (isStage()) root.dataset.stage = "1";
    save("lang", lang); save("theme", theme);
  }, [lang, theme]);

  const cache: CacheMeta | undefined = caches?.find((c) => c.id === cacheId) ?? caches?.[0];
  useEffect(() => { if (cache) save("cache", cache.id); }, [cache]);

  return (
    <LangCtx.Provider value={lang}>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:p-2 focus:bg-surface">Skip</a>
      <header className="border-b border-ink/10 bg-surface">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-2">
          <div className="flex items-center gap-2 mr-auto">
            <img src="/favicon.svg" alt="" width={28} height={28} />
            <div>
              <div className="font-semibold text-lg leading-tight">{t("app.name")}</div>
              <div className="text-sm text-muted leading-tight">{t("app.tagline")}</div>
            </div>
          </div>
          <nav aria-label="Asosiy" className="flex flex-wrap gap-1">
            {ROUTES.map((r) => (
              <a key={r} href={`#/${r}`} aria-current={route === r ? "page" : undefined}
                 className={`px-3 py-2 rounded-card font-medium ${route === r ? "bg-water text-bg" : "hover:bg-ink/5"}`}>
                {t(NAV[r])}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            {caches && caches.length > 0 && (
              <label className="flex items-center gap-2 text-sm">
                <span className="text-muted">{t("web.place")}</span>
                <select className="input py-1" value={cache?.id} onChange={(e) => setCacheId(e.target.value)}>
                  {caches.map((c) => <option key={c.id} value={c.id}>{c.place} · {c.start.slice(0, 4)}{c.crop === "bugdoy" ? ` · ${t("crop.bugdoy")}` : ""}</option>)}
                </select>
              </label>
            )}
            <button className="btn py-1" onClick={() => setLang(lang === "uz" ? "ru" : "uz")} aria-label={t("web.lang")}>
              {lang === "uz" ? "RU" : "UZ"}
            </button>
            <button className="btn py-1 dev-only" aria-label={t("web.theme")}
                    onClick={() => setTheme(theme === "auto" ? "dark" : theme === "dark" ? "light" : "auto")}>
              <ThemeIcon mode={theme} />
            </button>
          </div>
        </div>
        {cache?.synthetic && (
          <div role="alert" className="bg-alert text-bg text-center font-semibold py-2 px-4">{t("errors.synthetic")}</div>
        )}
      </header>

      <main id="main" className="max-w-7xl mx-auto px-4 py-6 min-h-[70vh]">
        {error && <div role="alert" className="card border-alert text-alert">{t("web.error")}: {error}</div>}
        {!error && caches === null && <p className="text-muted">{t("web.loading")}</p>}
        {caches && caches.length === 0 && route !== "ilm" && <NoCache />}
        {cache && route === "stakan" && <BucketPage cache={cache} />}
        {cache && route === "sim" && <SimulatorPage cache={cache} />}
        {cache && route === "uyushma" && <DemandPage cache={cache} />}
        {route === "ilm" && <SciencePage />}
      </main>

      <footer className="border-t border-ink/10 bg-surface">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap justify-between gap-2 text-sm">
          <span className="font-medium">{t("app.authors")}</span>
          {cache && (
            <span className="text-muted">
              <span className="inline-block px-2 rounded bg-leaf/15 text-ink mr-2">{t("web.offline_badge")}</span>
              {t("web.source")}: {cache.synthetic ? cache.source : t("web.source_archive")} · {cache.place} ({cache.lat}, {cache.lon})
            </span>
          )}
        </div>
      </footer>
    </LangCtx.Provider>
  );
}

function NoCache() {
  return (
    <LangCtx.Consumer>
      {(lang) => (
        <div className="card max-w-2xl" role="status">
          <h2 className="text-xl font-semibold mb-2">{translate(lang, "web.no_cache_title")}</h2>
          <p className="mb-2">{translate(lang, "errors.no_cache")}</p>
          <p className="text-muted">{translate(lang, "web.no_cache_steps")}</p>
        </div>
      )}
    </LangCtx.Consumer>
  );
}

function ThemeIcon({ mode }: { mode: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2">
      {mode === "dark" && <path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z" fill="currentColor" />}
      {mode === "light" && <><circle cx="12" cy="12" r="4" fill="currentColor" />{[0, 45, 90, 135, 180, 225, 270, 315].map((a) => <line key={a} x1="12" y1="2" x2="12" y2="4.5" transform={`rotate(${a} 12 12)`} />)}</>}
      {mode !== "dark" && mode !== "light" && <><circle cx="12" cy="12" r="9" /><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" /></>}
    </svg>
  );
}
