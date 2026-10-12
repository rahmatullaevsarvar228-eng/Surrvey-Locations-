"""Role-based permissions (who may save what). Ichki auditor may only view."""

LEADER, ACCOUNTANT, AUDITOR = "leader", "accountant", "auditor"

PERMISSIONS = {
    "project": {LEADER, ACCOUNTANT},      # project card (Ma'lumot), new project
    "stage": {LEADER},                    # stage changes (M2)
    "assessment": {LEADER},               # criteria assessments and evidence (M3)
    "cost": {ACCOUNTANT},                 # costs: add / edit / delete (M4)
    "import": {ACCOUNTANT},               # cost import from Excel
    "impairment": {ACCOUNTANT},           # impairment event and impairment tests
    "settings": {ACCOUNTANT},             # M12
    "report": {ACCOUNTANT},               # Excel / Word / PDF reports and exports
}


def allowed(role: str, action: str) -> bool:
    return role in PERMISSIONS[action]
