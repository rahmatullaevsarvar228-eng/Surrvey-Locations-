"""Strict business style: light theme, Segoe UI, no animation."""

FONT_FAMILY = "Segoe UI"
FONT_SIZE = 10

GREEN = "#1e7b34"
GREEN_BG = "#e3f1e6"
RED = "#b3261e"
RED_BG = "#f8e3e1"
YELLOW = "#8a6100"
YELLOW_BG = "#fbf0d0"
GREY = "#5f6368"
GREY_BG = "#eceff1"
ACCENT = "#1f4e79"

QSS = f"""
QWidget {{ background: #ffffff; color: #1f2328; font-family: "{FONT_FAMILY}"; font-size: {FONT_SIZE}pt; }}
QMainWindow, QDialog {{ background: #f6f7f9; }}
#Sidebar {{ background: #1f2d3d; border: none; }}
#Sidebar QPushButton {{ background: transparent; color: #d5dde6; border: none; text-align: left;
                        padding: 9px 18px; font-size: 10.5pt; }}
#Sidebar QPushButton:checked {{ background: #2e4a66; color: #ffffff; border-left: 3px solid #7fb2e5; }}
#Sidebar QPushButton:hover {{ background: #27394d; }}
#SidebarTitle {{ background: transparent; color: #ffffff; font-size: 13pt; font-weight: 600; padding: 16px 18px 4px; }}
#SidebarSub {{ background: transparent; color: #9fb0c2; font-size: 8.5pt; padding: 0 18px 14px; }}
#SidebarUser {{ background: transparent; color: #c2cdd8; font-size: 9pt; padding: 10px 18px; }}
#Page {{ background: #f6f7f9; }}
#PageTitle {{ background: transparent; font-size: 15pt; font-weight: 600; color: {ACCENT}; padding: 2px 0 8px; }}
#Card {{ background: #ffffff; border: 1px solid #d9dde3; border-radius: 4px; }}
#CardValue {{ background: transparent; font-size: 15pt; font-weight: 600; color: #1f2328; }}
#CardLabel {{ background: transparent; color: {GREY}; font-size: 9pt; }}
#Muted {{ background: transparent; color: {GREY}; }}
#DemoMark {{ background: {YELLOW_BG}; color: {YELLOW}; border: 1px solid #ecd798; padding: 4px 8px; }}
QLabel {{ background: transparent; }}
QGroupBox {{ background: #ffffff; border: 1px solid #d9dde3; border-radius: 4px; margin-top: 14px; padding: 10px 8px 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {ACCENT}; font-weight: 600; }}
QPushButton {{ background: #ffffff; border: 1px solid #b9c0c9; border-radius: 3px; padding: 5px 14px; }}
QPushButton:hover {{ background: #eef2f6; }}
QPushButton:disabled {{ color: #9aa0a6; border-color: #dde1e6; }}
QPushButton#Primary {{ background: {ACCENT}; color: #ffffff; border-color: {ACCENT}; }}
QPushButton#Primary:hover {{ background: #26608f; }}
QPushButton#Primary:disabled {{ background: #9fb3c8; border-color: #9fb3c8; }}
QLineEdit, QComboBox, QDateEdit, QSpinBox, QPlainTextEdit {{ border: 1px solid #b9c0c9; border-radius: 3px;
    padding: 3px 6px; background: #ffffff; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}
QLineEdit:read-only {{ background: #f3f4f6; }}
QTableWidget, QTableView {{ border: 1px solid #d9dde3; gridline-color: #e6e8eb; selection-background-color: #d6e4f2;
    selection-color: #1f2328; alternate-background-color: #f9fafb; }}
QHeaderView::section {{ background: #eef1f4; border: none; border-right: 1px solid #d9dde3;
    border-bottom: 1px solid #d9dde3; padding: 5px 6px; font-weight: 600; color: #3c4043; }}
QTabWidget::pane {{ border: 1px solid #d9dde3; background: #ffffff; top: -1px; }}
QTabBar::tab {{ background: #eef1f4; border: 1px solid #d9dde3; padding: 6px 14px; margin-right: 2px; }}
QTabBar::tab:selected {{ background: #ffffff; border-bottom-color: #ffffff; color: {ACCENT}; font-weight: 600; }}
QScrollArea {{ border: none; background: transparent; }}
"""


def decision_colors(decision: str, status: str = "met"):
    """(foreground, background) for a decision: green capitalized, red expensed/written off,
    yellow while criteria are pending, grey out of scope."""
    if decision == "KAPITALLASHTIRILADI":
        return GREEN, GREEN_BG
    if decision == "STANDART QO'LLANILMAYDI":
        return GREY, GREY_BG
    if decision == "XARAJAT SIFATIDA TAN OLINADI" and status == "pending":
        return YELLOW, YELLOW_BG
    return RED, RED_BG


def status_colors(status: str):
    return {"met": (GREEN, GREEN_BG), "no": (RED, RED_BG)}.get(status, (YELLOW, YELLOW_BG))


def level_colors(level: str):
    return {"high": (RED, RED_BG), "medium": (YELLOW, YELLOW_BG)}.get(level, (GREY, GREY_BG))


def treatment_colors(treatment: str):
    return (GREEN, GREEN_BG) if treatment == "capitalize" else (RED, RED_BG)
