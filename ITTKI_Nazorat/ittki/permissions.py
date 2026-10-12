"""Role permissions — the ONLY place where rights are defined and checked.

The service layer (ittki.services.Service) calls `enforce()` before every action; the repository
calls the same `enforce()` as a safety net for direct calls. The interface only reads `allowed()`
to enable or disable buttons.
"""
from __future__ import annotations

LEADER, ACCOUNTANT, AUDITOR = "leader", "accountant", "auditor"
ALL = frozenset({LEADER, ACCOUNTANT, AUDITOR})

# action -> roles allowed (table from the specification, one row per action)
PERMISSIONS = {
    "view": ALL,                                   # all windows, tabs, audit log
    "project": frozenset({LEADER, ACCOUNTANT}),    # create a project, save the passport (Ma'lumot)
    "stage": frozenset({LEADER}),                  # change project stage
    "assessment": frozenset({LEADER}),             # criteria assessment (incl. draft)
    "cost": frozenset({ACCOUNTANT}),               # costs: add / edit / delete
    "import": frozenset({ACCOUNTANT}),             # cost import from Excel
    "impairment": frozenset({ACCOUNTANT}),         # impairment event and impairment tests
    "settings": frozenset({ACCOUNTANT}),           # save settings
    "demo": frozenset({ACCOUNTANT}),               # load demo data (only into an empty database)
    "report": ALL,                                 # all reports and exports (Excel, Word, PDF, schedule)
    "backup": ALL,                                 # database backup
}


class PermissionDenied(PermissionError):
    """The role may not perform the action. Message in Uzbek; the attempt is in the audit log."""

    def __init__(self, message: str, action: str, role: str):
        super().__init__(message)
        self.action, self.role = action, role


class ReadOnlyRole(PermissionDenied):
    """Ichki auditor: view only."""


def allowed(role: str, action: str) -> bool:
    return role in PERMISSIONS[action]


def message(role: str, action: str) -> str:
    from .i18n import uz
    return uz.t("perm.denied", action=uz.PERM_ACTION[action], role=uz.ROLE.get(role, role),
                allowed=", ".join(uz.ROLE[r] for r in ("leader", "accountant", "auditor")
                                  if r in PERMISSIONS[action]))


def enforce(repo, user, action: str):
    """Check `user` may do `action`; otherwise write 'denied' to the audit log (committed on its own)
    and raise PermissionDenied (ReadOnlyRole for the auditor)."""
    if action not in PERMISSIONS:
        raise KeyError(action)
    if allowed(user.role, action):
        return
    repo.audit_denied(user, action)
    raise (ReadOnlyRole if user.role == AUDITOR else PermissionDenied)(message(user.role, action), action,
                                                                         user.role)
