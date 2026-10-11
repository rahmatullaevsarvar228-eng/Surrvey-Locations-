"""FastAPI: /api/advice /api/simulate /api/demand /api/demo + yig‘ilgan veb (web/dist)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import Settings, get_settings
from app.services import advisor
from app.services.demo_cache import CacheMissing, DemoCache, get_cache, list_caches
from app.services.texts import t
from app.services.weather import WeatherClient, WeatherUnavailable

from .schemas import AdviceIn, SimulateIn


def create_app(settings: Settings | None = None, weather: WeatherClient | None = None) -> FastAPI:
    st = settings or get_settings()
    wc = weather or WeatherClient(st.weather_dir, ttl_s=st.weather_ttl_s)
    app = FastAPI(title="Suv Maslahatchi API", version="0.1.0",
                  description="FAO-56 sug‘orish maslahati. Mualliflar: Saynatov Yodgor, Raxmatullayev Sarvar")

    def cache(cid: str) -> DemoCache:
        return get_cache(st.cache_dir, cid, st.allow_synthetic)

    @app.exception_handler(CacheMissing)
    async def _cache_missing(_: Request, e: CacheMissing) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": t("uz", "errors.no_cache"), "id": str(e)})

    @app.exception_handler(WeatherUnavailable)
    async def _weather(_: Request, e: WeatherUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": t("uz", "errors.weather")})

    @app.exception_handler(ValueError)
    async def _value(_: Request, e: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(e)})

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "caches": len(list_caches(st.cache_dir, st.allow_synthetic))}

    @app.get("/api/demo")
    def demo_list() -> dict[str, Any]:
        return {"caches": [c.meta.to_json() for c in list_caches(st.cache_dir, st.allow_synthetic)],
                "allow_synthetic": st.allow_synthetic}

    @app.get("/api/demo/{cache_id}")
    def demo_one(cache_id: str) -> dict[str, Any]:
        c = cache(cache_id)
        return {"meta": c.meta.to_json(),
                "days": [{"date": d.date.isoformat(), "et0": d.et0, "rain": d.rain} for d in c.days]}

    @app.post("/api/advice")
    def advice(body: AdviceIn) -> dict[str, Any]:
        if body.mode == "live":
            fld = body.field.to_engine()
            out, w = advisor.advise_live(fld, body.last_irrigation, wc, body.lang)
            return {**out.to_json(), "source": {"kind": "live", "stale": w.stale,
                                               "fetched_at": w.fetched_at}}
        if not body.cache_id:
            raise ValueError("demo rejimi uchun cache_id kerak")
        c = cache(body.cache_id)
        fld = body.field.to_engine(c.meta.planting)
        today = body.today or (fld.planting + timedelta(days=90))
        out = advisor.advise_demo(fld, body.last_irrigation, c, today, body.lang)
        return {**out.to_json(), "source": {"kind": "demo", "today": today.isoformat(),
                                           "text": t(body.lang, "advice.source_demo", place=c.meta.place,
                                                     date=today.isoformat()),
                                           **c.meta.to_json()}}

    @app.post("/api/simulate")
    def simulate(body: SimulateIn) -> dict[str, Any]:
        c = cache(body.cache_id)
        fld = body.field.to_engine(c.meta.planting)
        habit = (body.habit.every_days, body.habit.mm) if body.habit else None
        res = advisor.simulate_pair(fld, c, habit)
        if not res["fao"] or not res["fao"]["rows"]:
            raise ValueError("tanlangan ekish sanasi kesh oralig‘iga tushmaydi")
        return {"meta": c.meta.to_json(), "field": {**body.field.model_dump(mode="json"),
                                                    "planting": fld.planting.isoformat()}, **res}

    @app.get("/api/demand")
    def demand(cache_id: str, today: date | None = None) -> dict[str, Any]:
        c = cache(cache_id)
        day = today or (c.meta.planting + timedelta(days=90))
        return {"meta": c.meta.to_json(), "today": day.isoformat(), **advisor.demand(c, day)}

    # ---------------------------------------------------------------- yig‘ilgan veb (oflayn)
    dist = st.web_dist
    if (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            f = dist / path
            if path and f.is_file() and dist in f.resolve().parents:
                return FileResponse(f)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
