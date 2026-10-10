"""VDT API (FastAPI). Mualliflar: Saynatov Yodgor, Raxmatullayev Sarvar."""
import json
import os
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engine import (Station, Train, preset, PRESETS, verify, apply_breakdown,
                    scenario_dict, recovery_time, breakdown_event)
from engine.run import fifo_result, ai_result

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "cache")
DIST = os.path.join(ROOT, "frontend", "dist")
WORKERS = int(os.environ.get("VDT_WORKERS", "8"))

app = FastAPI(title="Virtual Double-Track API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Disruption(BaseModel):
    segment: List[int] = Field(min_length=2, max_length=2)
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class Breakdown(BaseModel):
    train_id: str
    station: int
    minutes: int = Field(ge=1, le=600)


class StationIn(BaseModel):
    name: str
    km: float
    tracks: int


class TrainIn(BaseModel):
    id: str
    kind: str
    direction: int
    speed: float
    release: int
    weight: int
    stops: dict = {}


class SolveReq(BaseModel):
    preset: Optional[Literal["oddiy", "avariya", "osish30"]] = "oddiy"
    stations: Optional[List[StationIn]] = None
    trains: Optional[List[TrainIn]] = None
    disruption: Optional[Disruption] = None
    breakdown: Optional[Breakdown] = None
    objective: Literal["umumiy", "ustuvorlik"] = "umumiy"
    time_limit: float = Field(default=10.0, gt=0, le=15.0)


class VerifyReq(BaseModel):
    stations: List[StationIn]
    trains: List[TrainIn]
    schedule: dict
    disruption: Optional[Disruption] = None


def _build(req):
    if req.stations and req.trains:
        st = [Station(**s.model_dump()) for s in req.stations]
        tr = [Train(**dict(t.model_dump(), stops={int(k): v for k, v in t.stops.items()}))
              for t in req.trains]
        dis = None
    else:
        st, tr, dis = preset(req.preset or "oddiy")
    if req.disruption is not None:
        d = req.disruption
        a, b = d.segment
        if abs(a - b) != 1 or not (0 <= min(a, b) and max(a, b) < len(st)) or d.end <= d.start:
            raise HTTPException(400, "noto'g'ri peregon yoki vaqt oralig'i")
        dis = dict(segment=(a, b), start=d.start, end=d.end)
    if req.breakdown is not None:
        bk = req.breakdown
        if not (0 < bk.station < len(st) - 1) or bk.train_id not in {t.id for t in tr}:
            raise HTTPException(400, "noto'g'ri poyezd yoki bekat (faqat oraliq bekat)")
        tr = apply_breakdown(tr, bk.train_id, bk.station, bk.minutes)
    return st, tr, dis


def _cache(name):
    p = os.path.join(CACHE, name)
    if not os.path.exists(p):
        raise HTTPException(404, f"kesh topilmadi: {name}. scripts/precompute.py ni ishga tushiring")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/scenarios")
def scenarios():
    return [dict(nomi=n, mavjud=os.path.exists(os.path.join(CACHE, f"{n}.json")))
            for n in PRESETS]


@app.get("/api/scenarios/{name}")
def scenario(name: str):
    if name not in PRESETS:
        raise HTTPException(404, "ssenariy yo'q")
    return _cache(f"{name}.json")


@app.get("/api/investment")
def investment():
    return _cache("investment.json")


@app.post("/api/simulate_fifo")
def api_fifo(req: SolveReq):
    st, tr, dis = _build(req)
    res, _ = fifo_result(st, tr, dis)
    return dict(scenario=scenario_dict(st, tr, dis), fifo=res)


@app.post("/api/solve")
def api_solve(req: SolveReq):
    st, tr, dis = _build(req)
    f, fs = fifo_result(st, tr, dis)
    a, asch = ai_result(st, tr, dis, req.objective, req.time_limit, WORKERS)
    out = dict(scenario=scenario_dict(st, tr, dis), fifo=f, ai={req.objective: a})
    if dis:
        out["tiklanish"] = dict(
            fifo=None if fs is None else recovery_time(st, tr, fs, dis),
            ai={req.objective: None if asch is None else recovery_time(st, tr, asch, dis)})
    elif req.breakdown:
        bk = req.breakdown

        def rec(sched):
            return recovery_time(st, tr, sched, breakdown_event(st, tr, sched, bk.train_id, bk.station))
        out["tiklanish"] = dict(fifo=None if fs is None else rec(fs),
                                ai={req.objective: None if asch is None else rec(asch)})
    return out


@app.post("/api/verify")
def api_verify(req: VerifyReq):
    st = [Station(**s.model_dump()) for s in req.stations]
    tr = [Train(**dict(t.model_dump(), stops={int(k): v for k, v in t.stops.items()}))
          for t in req.trains]
    sched = {k: [(r["bekat"], r["kelish"], r["ketish"]) for r in v] for k, v in req.schedule.items()}
    dis = None
    if req.disruption:
        dis = dict(segment=tuple(req.disruption.segment), start=req.disruption.start,
                   end=req.disruption.end)
    errs = verify(st, tr, sched, dis)
    return dict(konfliktlar=len(errs), xatolar=errs)


@app.get("/api/health")
def health():
    return dict(ok=True)


if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        p = os.path.join(DIST, full_path)
        if full_path and os.path.isfile(p):
            return FileResponse(p)
        return FileResponse(os.path.join(DIST, "index.html"))
