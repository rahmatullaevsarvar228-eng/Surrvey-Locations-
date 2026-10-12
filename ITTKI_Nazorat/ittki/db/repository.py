"""Load/save between SQLite and engine models. Every change is written to audit_log (M11)
in the same transaction as the change itself."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from ..core import engine
from ..core.appsettings import AppSettings
from .permissions import PERMISSIONS, allowed
from .schema import migrate

ROLES = ("leader", "accountant", "auditor")
SYSTEM_USER = ("ITTKI Nazorat", "system")
STAGES = ("research", "development", "ready", "abandoned")
# allowed stage-gate transitions (M2); same-stage = date correction
TRANSITIONS = {
    "research": {"development", "abandoned"},
    "development": {"ready", "abandoned"},
    "ready": {"abandoned"},
    "abandoned": set(),
}


class EvidenceRequired(ValueError):
    """'Ha' without an evidence document, saved not as a draft (M3)."""
    def __init__(self, keys):
        super().__init__(f"evidence required for: {', '.join(keys)}")
        self.keys = list(keys)


class PermissionDenied(PermissionError):
    """The user's role may not perform this action. The message is in Uzbek; the attempt is audited."""
    def __init__(self, message: str, action: str, role: str):
        super().__init__(message)
        self.action, self.role = action, role


class ReadOnlyRole(PermissionDenied):
    """Ichki auditor: view only."""


@dataclass(frozen=True)
class User:
    name: str
    role: str

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("user name is empty")
        if self.role not in ROLES:
            raise ValueError(f"unknown role {self.role!r}")


@dataclass
class ProjectRecord:
    code: str
    name: str
    scope: str = "rnd"
    department: str = ""
    leader: str = ""
    start_date: Optional[date] = None
    budget: Optional[int] = None
    phases_separable: bool = True
    development_start: Optional[date] = None
    available_for_use: Optional[date] = None
    abandoned_on: Optional[date] = None
    useful_life_months: int = 0
    expected_net_benefit: Optional[int] = None
    note: str = ""
    is_demo: bool = False
    id: Optional[int] = None
    created_at: Optional[str] = None

    @property
    def stage(self) -> str:
        if self.abandoned_on:
            return "abandoned"
        if self.available_for_use:
            return "ready"
        if self.development_start:
            return "development"
        return "research"

    @property
    def status(self) -> str:
        return {"abandoned": "abandoned", "ready": "ready"}.get(self.stage, "active")


@dataclass
class EvidenceDoc:
    doc_type: str
    number: str
    doc_date: date
    file_path: str = ""
    id: Optional[int] = None

    def ref(self) -> str:
        return f"{self.doc_type} No {self.number}, {self.doc_date.strftime('%d.%m.%Y')}"


@dataclass
class Answer:
    answer: str                         # yes | no | expert
    evidence: Optional[EvidenceDoc] = None


@dataclass
class AssessmentRecord:
    project_id: int
    on_date: date
    answers: dict                       # criterion key -> Answer
    is_draft: bool = False
    note: str = ""
    actor: str = ""
    role: str = ""
    created_at: str = ""
    id: Optional[int] = None


@dataclass
class CostRecord:
    project_id: int
    on_date: date
    amount: int
    category: str
    document: str = ""
    comment: str = ""
    id: Optional[int] = None


@dataclass
class StageEvent:
    project_id: int
    from_stage: Optional[str]
    to_stage: str
    on_date: date
    note: str
    actor: str
    role: str
    created_at: str
    id: Optional[int] = None


@dataclass
class ImpairmentTest:
    project_id: int
    on_date: date
    note: str = ""
    id: Optional[int] = None


@dataclass
class AuditRow:
    id: int
    at: str
    actor: str
    role: str
    action: str
    entity: str
    entity_id: Optional[int]
    before: Optional[dict]
    after: Optional[dict]


# ------------------------------------------------------------------ helpers
def _d(v: Optional[str]) -> Optional[date]:
    return date.fromisoformat(v) if v else None


def _iso(v: Optional[date]) -> Optional[str]:
    if v is None:
        return None
    if not isinstance(v, date) or isinstance(v, datetime):
        raise TypeError(f"expected datetime.date, got {v!r}")
    return v.isoformat()


def _money(v, nullable=True):
    if v is None and nullable:
        return None
    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
        raise TypeError(f"money must be a non-negative int (so'm), got {v!r}")
    return v


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json(v) -> Optional[str]:
    if v is None:
        return None
    return json.dumps(v, ensure_ascii=False, default=str, sort_keys=True)


def _plain(obj) -> dict:
    d = asdict(obj)
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in d.items()}


# ------------------------------------------------------------------ repository
class Repository:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, isolation_level=None)   # transactions managed by _tx()
        self.conn.row_factory = sqlite3.Row
        self._depth = 0
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.version = migrate(self.conn)
        self._seed_settings()

    @contextmanager
    def _tx(self):
        """Nestable transaction: a change and its audit record commit together or not at all."""
        if self._depth == 0:
            self.conn.execute("BEGIN IMMEDIATE")
        self._depth += 1
        try:
            yield
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                self.conn.execute("ROLLBACK")
            raise
        else:
            self._depth -= 1
            if self._depth == 0:
                self.conn.execute("COMMIT")

    def close(self):
        self.conn.close()

    def backup(self, dest: str | Path):
        """One-button backup (TZ 7): consistent copy via the SQLite backup API."""
        out = sqlite3.connect(str(dest))
        self.conn.backup(out)
        out.close()

    # ---- audit -------------------------------------------------------
    def _audit(self, who, action, entity, entity_id, before=None, after=None):
        name, role = (who.name, who.role) if isinstance(who, User) else who
        self.conn.execute(
            "INSERT INTO audit_log (at, actor, role, action, entity, entity_id, before, after) VALUES (?,?,?,?,?,?,?,?)",
            (_now(), name, role, action, entity, entity_id, _json(before), _json(after)))

    def authorize(self, user: User, action: str):
        """Raises PermissionDenied (ReadOnlyRole for the auditor) if the role may not do `action`.
        A denied attempt is written to the audit log in its own committed transaction."""
        if not isinstance(user, User):
            raise TypeError("user must be a User")
        if allowed(user.role, action):
            return
        from ..i18n import uz
        msg = uz.t("perm.denied", action=uz.PERM_ACTION[action], role=uz.ROLE.get(user.role, user.role),
                   allowed=", ".join(uz.ROLE[r] for r in sorted(PERMISSIONS[action])))
        if self._depth == 0:
            self._audit(user, "denied", action, None, None, {"action": action, "role": user.role})
        raise (ReadOnlyRole if user.role == "auditor" else PermissionDenied)(msg, action, user.role)

    def audit_log(self, entity: Optional[str] = None, entity_id: Optional[int] = None) -> list[AuditRow]:
        q, a = "SELECT * FROM audit_log", []
        cond = []
        if entity:
            cond.append("entity = ?"); a.append(entity)
        if entity_id is not None:
            cond.append("entity_id = ?"); a.append(entity_id)
        if cond:
            q += " WHERE " + " AND ".join(cond)
        rows = self.conn.execute(q + " ORDER BY id", a).fetchall()
        return [AuditRow(r["id"], r["at"], r["actor"], r["role"], r["action"], r["entity"], r["entity_id"],
                         json.loads(r["before"]) if r["before"] else None,
                         json.loads(r["after"]) if r["after"] else None) for r in rows]

    # ---- settings (M12) ----------------------------------------------
    SETTINGS_VERSION = 2   # 2: E9 default threshold 0 -> 1 000 000 so'm

    def _seed_settings(self):
        if self.conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]:
            self._upgrade_settings()
            return
        flat = AppSettings().to_flat()
        with self._tx():
            for k, v in flat.items():
                self.conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (k, _json(v)))
            self.conn.execute("INSERT INTO settings (key, value) VALUES ('meta.settings_version', ?)",
                              (_json(self.SETTINGS_VERSION),))
            self._audit(SYSTEM_USER, "create", "settings", None, None, flat)

    def _upgrade_settings(self):
        """Databases created before settings version 2 had E9 = 0 by default. Replace it with the new default
        unless a user changed it explicitly (that would be in the audit log)."""
        row = self.conn.execute("SELECT value FROM settings WHERE key = 'meta.settings_version'").fetchone()
        if row and json.loads(row["value"]) >= self.SETTINGS_VERSION:
            return
        with self._tx():
            cur = self.conn.execute("SELECT value FROM settings WHERE key = 'control.e9_amount'").fetchone()
            user_set = any(x.after and "control.e9_amount" in x.after and x.role != SYSTEM_USER[1]
                           for x in self.audit_log("settings"))
            if cur is not None and json.loads(cur["value"]) == 0 and not user_set:
                new = AppSettings().controls.e9_amount
                self.conn.execute("UPDATE settings SET value = ? WHERE key = 'control.e9_amount'", (_json(new),))
                self._audit(SYSTEM_USER, "update", "settings", None, {"control.e9_amount": 0},
                            {"control.e9_amount": new})
            self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('meta.settings_version', ?)",
                              (_json(self.SETTINGS_VERSION),))

    def settings(self) -> AppSettings:
        flat = {r["key"]: json.loads(r["value"]) for r in self.conn.execute("SELECT key, value FROM settings")
                if not r["key"].startswith("meta.")}
        return AppSettings.from_flat(flat)

    def save_settings(self, new: AppSettings, user: User) -> list[str]:
        """Validates (constructing AppSettings does), writes changed keys, audits each. Returns changed keys."""
        self.authorize(user, "settings")
        new = AppSettings.from_flat(new.to_flat())     # re-validate
        old = self.settings().to_flat()
        changed = []
        with self._tx():
            for k, v in new.to_flat().items():
                if old.get(k) != v:
                    self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, _json(v)))
                    self._audit(user, "update", "settings", None, {k: old.get(k)}, {k: v})
                    changed.append(k)
        return changed

    # ---- projects (M1) -----------------------------------------------
    _PCOLS = ("code", "name", "scope", "department", "leader", "start_date", "budget", "status", "phases_separable",
              "development_start", "available_for_use", "abandoned_on", "useful_life_months",
              "expected_net_benefit", "note", "is_demo")

    def _project_values(self, p: ProjectRecord) -> dict:
        if not p.code.strip() or not p.name.strip():
            raise ValueError("code and name are required")
        if p.scope not in engine.SCOPES:
            raise ValueError(f"unknown scope {p.scope!r}")
        if not isinstance(p.useful_life_months, int) or p.useful_life_months < 0:
            raise ValueError("useful_life_months must be a non-negative int")
        return {"code": p.code.strip(), "name": p.name.strip(), "scope": p.scope, "department": p.department,
                "leader": p.leader, "start_date": _iso(p.start_date), "budget": _money(p.budget),
                "status": p.status, "phases_separable": int(bool(p.phases_separable)),
                "development_start": _iso(p.development_start), "available_for_use": _iso(p.available_for_use),
                "abandoned_on": _iso(p.abandoned_on), "useful_life_months": p.useful_life_months,
                "expected_net_benefit": _money(p.expected_net_benefit), "note": p.note,
                "is_demo": int(bool(p.is_demo))}

    def save_project(self, p: ProjectRecord, user: User) -> int:
        self.authorize(user, "project")
        vals = self._project_values(p)
        with self._tx():
            if p.id is None:
                p.created_at = _now()
                cur = self.conn.execute(
                    f"INSERT INTO projects ({', '.join(vals)}, created_at) VALUES ({', '.join('?' * len(vals))}, ?)",
                    (*vals.values(), p.created_at))
                p.id = cur.lastrowid
                self._audit(user, "create", "project", p.id, None, vals)
            else:
                before = self.conn.execute(f"SELECT {', '.join(self._PCOLS)} FROM projects WHERE id = ?",
                                           (p.id,)).fetchone()
                if before is None:
                    raise KeyError(p.id)
                before = dict(before)
                diff_b = {k: before[k] for k in vals if before[k] != vals[k]}
                diff_a = {k: vals[k] for k in diff_b}
                if diff_a:
                    self.conn.execute(f"UPDATE projects SET {', '.join(f'{k} = ?' for k in vals)} WHERE id = ?",
                                      (*vals.values(), p.id))
                    self._audit(user, "update", "project", p.id, diff_b, diff_a)
        return p.id

    def _row_to_project(self, r) -> ProjectRecord:
        return ProjectRecord(code=r["code"], name=r["name"], scope=r["scope"], department=r["department"],
                             leader=r["leader"], start_date=_d(r["start_date"]), budget=r["budget"],
                             phases_separable=bool(r["phases_separable"]),
                             development_start=_d(r["development_start"]),
                             available_for_use=_d(r["available_for_use"]), abandoned_on=_d(r["abandoned_on"]),
                             useful_life_months=r["useful_life_months"],
                             expected_net_benefit=r["expected_net_benefit"], note=r["note"],
                             is_demo=bool(r["is_demo"]), id=r["id"], created_at=r["created_at"])

    def project(self, pid: int) -> ProjectRecord:
        r = self.conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        if r is None:
            raise KeyError(pid)
        return self._row_to_project(r)

    def projects(self) -> list[ProjectRecord]:
        return [self._row_to_project(r) for r in self.conn.execute("SELECT * FROM projects ORDER BY code")]

    def project_by_code(self, code: str) -> Optional[ProjectRecord]:
        r = self.conn.execute("SELECT * FROM projects WHERE code = ?", (code,)).fetchone()
        return self._row_to_project(r) if r else None

    # ---- stages (M2) -------------------------------------------------
    def change_stage(self, pid: int, to_stage: str, on: date, user: User, note: str = "") -> ProjectRecord:
        self.authorize(user, "stage")
        p = self.project(pid)
        frm = p.stage
        if to_stage not in STAGES:
            raise ValueError(to_stage)
        if to_stage != frm and to_stage not in TRANSITIONS[frm]:
            raise ValueError(f"transition {frm} -> {to_stage} is not allowed")
        _iso(on)
        if to_stage == "development":
            p.development_start = on
        elif to_stage == "ready":
            p.available_for_use = on
        elif to_stage == "abandoned":
            p.abandoned_on = on
        elif to_stage == "research":
            raise ValueError("research is the initial stage")
        with self._tx():
            self.save_project(p, user)
            ts = _now()
            cur = self.conn.execute(
                "INSERT INTO stage_events (project_id, from_stage, to_stage, on_date, note, actor, role, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)", (pid, frm, to_stage, _iso(on), note, user.name, user.role, ts))
            self._audit(user, "create", "stage_event", cur.lastrowid, None,
                        {"project_id": pid, "from": frm, "to": to_stage, "on": _iso(on), "note": note})
        return p

    def stage_events(self, pid: int) -> list[StageEvent]:
        return [StageEvent(r["project_id"], r["from_stage"], r["to_stage"], _d(r["on_date"]), r["note"], r["actor"],
                           r["role"], r["created_at"], r["id"])
                for r in self.conn.execute("SELECT * FROM stage_events WHERE project_id = ? ORDER BY id", (pid,))]

    # ---- assessments (M3) --------------------------------------------
    def add_assessment(self, a: AssessmentRecord, user: User) -> int:
        """Append a new assessment version. 'yes' needs evidence unless saved as a draft (then E1)."""
        self.authorize(user, "assessment")
        _iso(a.on_date)
        unknown = set(a.answers) - set(engine.CRITERIA)
        if unknown:
            raise ValueError(f"unknown criteria: {unknown}")
        for k, ans in a.answers.items():
            if ans.answer not in ("yes", "no", "expert"):
                raise ValueError(f"{k}: bad answer {ans.answer!r}")
        missing = [k for k, ans in a.answers.items() if ans.answer == "yes" and ans.evidence is None]
        if missing and not a.is_draft:
            raise EvidenceRequired(missing)
        a.actor, a.role, a.created_at = user.name, user.role, _now()
        with self._tx():
            cur = self.conn.execute(
                "INSERT INTO assessments (project_id, on_date, is_draft, note, actor, role, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (a.project_id, _iso(a.on_date), int(a.is_draft), a.note, a.actor, a.role, a.created_at))
            a.id = cur.lastrowid
            audit = {}
            for k in sorted(a.answers):
                ans = a.answers[k]
                ev_id = None
                if ans.evidence is not None:
                    e = ans.evidence
                    if not e.doc_type.strip() or not e.number.strip():
                        raise ValueError(f"{k}: evidence type and number are required")
                    ev_id = self.conn.execute(
                        "INSERT INTO evidence_documents (doc_type, number, doc_date, file_path, created_at) "
                        "VALUES (?,?,?,?,?)", (e.doc_type, e.number, _iso(e.doc_date), e.file_path, _now())).lastrowid
                    e.id = ev_id
                self.conn.execute("INSERT INTO assessment_answers (assessment_id, criterion_key, answer, evidence_id) "
                                  "VALUES (?,?,?,?)", (a.id, k, ans.answer, ev_id))
                audit[k] = {"answer": ans.answer, "evidence": ans.evidence.ref() if ans.evidence else None}
            self._audit(user, "create", "assessment", a.id, None,
                        {"project_id": a.project_id, "on": _iso(a.on_date), "draft": a.is_draft, "answers": audit})
        return a.id

    def assessments(self, pid: int) -> list[AssessmentRecord]:
        """Ordered by date, then by entry order (the last one entered on a day wins)."""
        out = []
        for r in self.conn.execute("SELECT * FROM assessments WHERE project_id = ? ORDER BY on_date, id", (pid,)):
            answers = {}
            for x in self.conn.execute(
                    "SELECT a.criterion_key, a.answer, e.id AS eid, e.doc_type, e.number, e.doc_date, e.file_path "
                    "FROM assessment_answers a LEFT JOIN evidence_documents e ON e.id = a.evidence_id "
                    "WHERE a.assessment_id = ?", (r["id"],)):
                ev = EvidenceDoc(x["doc_type"], x["number"], _d(x["doc_date"]), x["file_path"], x["eid"]) \
                    if x["eid"] else None
                answers[x["criterion_key"]] = Answer(x["answer"], ev)
            out.append(AssessmentRecord(pid, _d(r["on_date"]), answers, bool(r["is_draft"]), r["note"], r["actor"],
                                        r["role"], r["created_at"], r["id"]))
        return out

    # ---- costs (M4) --------------------------------------------------
    def _cost_values(self, c: CostRecord) -> dict:
        if c.category not in engine.ALL_CATEGORIES:
            raise ValueError(f"unknown category {c.category!r}")
        return {"project_id": c.project_id, "on_date": _iso(c.on_date), "amount": _money(c.amount, False),
                "category": c.category, "document": c.document, "comment": c.comment}

    def add_cost(self, c: CostRecord, user: User) -> int:
        self.authorize(user, "cost")
        vals = self._cost_values(c)
        with self._tx():
            c.id = self.conn.execute(
                f"INSERT INTO costs ({', '.join(vals)}, created_at) VALUES ({', '.join('?' * len(vals))}, ?)",
                (*vals.values(), _now())).lastrowid
            self._audit(user, "create", "cost", c.id, None, vals)
        return c.id

    def add_costs(self, costs: list[CostRecord], user: User) -> int:
        self.authorize(user, "cost")
        with self._tx():
            for c in costs:
                self.add_cost(c, user)
        return len(costs)

    def update_cost(self, c: CostRecord, user: User):
        self.authorize(user, "cost")
        vals = self._cost_values(c)
        before = self.conn.execute(f"SELECT {', '.join(vals)} FROM costs WHERE id = ?", (c.id,)).fetchone()
        if before is None:
            raise KeyError(c.id)
        before = dict(before)
        diff_b = {k: before[k] for k in vals if before[k] != vals[k]}
        if not diff_b:
            return
        with self._tx():
            self.conn.execute(f"UPDATE costs SET {', '.join(f'{k} = ?' for k in vals)} WHERE id = ?",
                              (*vals.values(), c.id))
            self._audit(user, "update", "cost", c.id, diff_b, {k: vals[k] for k in diff_b})

    def delete_cost(self, cost_id: int, user: User):
        self.authorize(user, "cost")
        r = self.conn.execute("SELECT * FROM costs WHERE id = ?", (cost_id,)).fetchone()
        if r is None:
            raise KeyError(cost_id)
        with self._tx():
            self.conn.execute("DELETE FROM costs WHERE id = ?", (cost_id,))
            self._audit(user, "delete", "cost", cost_id, dict(r), None)

    def costs(self, pid: int) -> list[CostRecord]:
        return [CostRecord(r["project_id"], _d(r["on_date"]), r["amount"], r["category"], r["document"],
                           r["comment"], r["id"])
                for r in self.conn.execute("SELECT * FROM costs WHERE project_id = ? ORDER BY on_date, id", (pid,))]

    # ---- impairment ---------------------------------------------------
    def set_impairment_event(self, pid: int, on: Optional[date], recoverable: Optional[int], user: User):
        """One impairment event per project (v1 engine). on=None removes it."""
        self.authorize(user, "impairment")
        old = self.impairment_event(pid)
        before = {"on": _iso(old[0]), "recoverable_amount": old[1]} if old else None
        with self._tx():
            self.conn.execute("DELETE FROM impairment_events WHERE project_id = ?", (pid,))
            after = None
            if on is not None:
                self.conn.execute("INSERT INTO impairment_events (project_id, on_date, recoverable_amount) "
                                  "VALUES (?,?,?)", (pid, _iso(on), _money(recoverable, False)))
                after = {"on": _iso(on), "recoverable_amount": recoverable}
            if before != after:
                self._audit(user, "update" if before and after else ("create" if after else "delete"),
                            "impairment_event", pid, before, after)

    def impairment_event(self, pid: int) -> Optional[tuple]:
        r = self.conn.execute("SELECT on_date, recoverable_amount FROM impairment_events WHERE project_id = ?",
                              (pid,)).fetchone()
        return (_d(r["on_date"]), r["recoverable_amount"]) if r else None

    def add_impairment_test(self, t: ImpairmentTest, user: User) -> int:
        self.authorize(user, "impairment")
        with self._tx():
            t.id = self.conn.execute("INSERT INTO impairment_tests (project_id, on_date, note) VALUES (?,?,?)",
                                     (t.project_id, _iso(t.on_date), t.note)).lastrowid
            self._audit(user, "create", "impairment_test", t.id, None, _plain(t))
        return t.id

    def delete_impairment_test(self, test_id: int, user: User):
        self.authorize(user, "impairment")
        r = self.conn.execute("SELECT * FROM impairment_tests WHERE id = ?", (test_id,)).fetchone()
        if r is None:
            raise KeyError(test_id)
        with self._tx():
            self.conn.execute("DELETE FROM impairment_tests WHERE id = ?", (test_id,))
            self._audit(user, "delete", "impairment_test", test_id, dict(r), None)

    def impairment_tests(self, pid: int) -> list[ImpairmentTest]:
        return [ImpairmentTest(r["project_id"], _d(r["on_date"]), r["note"], r["id"])
                for r in self.conn.execute("SELECT * FROM impairment_tests WHERE project_id = ? ORDER BY on_date",
                                           (pid,))]

    # ---- engine model ---------------------------------------------------
    def engine_project(self, pid: int) -> engine.Project:
        p = self.project(pid)
        asm = [engine.Assessment(a.on_date, {k: v.answer for k, v in a.answers.items()},
                                 {k: v.evidence.ref() for k, v in a.answers.items() if v.evidence})
               for a in self.assessments(pid)]
        costs = [engine.Cost(c.on_date, c.amount, c.category, c.comment) for c in self.costs(pid)]
        return engine.Project(
            name=p.code, phases_separable=p.phases_separable, development_start=p.development_start,
            available_for_use=p.available_for_use, abandoned_on=p.abandoned_on,
            useful_life_months=p.useful_life_months, assessments=asm, costs=costs, scope=p.scope,
            impairment_event=self.impairment_event(pid), expected_net_benefit=p.expected_net_benefit,
            impairment_test_dates=[t.on_date for t in self.impairment_tests(pid)])
