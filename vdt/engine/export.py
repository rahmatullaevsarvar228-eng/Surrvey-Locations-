"""Frontend uchun eksport."""
import json
from dataclasses import asdict


def sched_rows(sched):
    return {k: [dict(bekat=s, kelish=a, ketish=d) for s, a, d in v] for k, v in sched.items()}


def scenario_dict(st, trains, disruption=None):
    return dict(stations=[asdict(s) for s in st],
                trains=[dict(asdict(t), stops={str(k): v for k, v in t.stops.items()})
                        for t in trains],
                disruption=dict(disruption, segment=list(disruption["segment"])) if disruption else None)


def to_json(st, trains, sched):
    """Frontend uchun eksport (asl API)."""
    return json.dumps(dict(stations=[asdict(s) for s in st],
                           trains=[asdict(t) for t in trains],
                           schedule=sched_rows(sched)), ensure_ascii=False)
