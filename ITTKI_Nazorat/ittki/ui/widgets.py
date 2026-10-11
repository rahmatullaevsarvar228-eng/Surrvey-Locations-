"""Small reusable widgets: dates (dd.mm.yyyy), integer money input, tables, cards, messages."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDateEdit, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..i18n import uz

DATE_FMT = "dd.MM.yyyy"


def to_qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def from_qdate(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class DateEdit(QDateEdit):
    def __init__(self, value: Optional[date] = None, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat(DATE_FMT)
        self.setDate(to_qdate(value or date.today()))
        self.setMinimumWidth(110)

    def value(self) -> date:
        return from_qdate(self.date())

    def setValue(self, d: date):
        self.setDate(to_qdate(d))


class OptionalDate(QWidget):
    """Date that may be empty: a checkbox enables the date editor."""

    def __init__(self, value: Optional[date] = None, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.check = QCheckBox()
        self.edit = DateEdit(value)
        self.empty = QLabel(uz.t("f.not_set"))
        self.empty.setObjectName("Muted")
        lay.addWidget(self.check)
        lay.addWidget(self.edit)
        lay.addWidget(self.empty)
        lay.addStretch()
        self.check.toggled.connect(self._sync)
        self.setValue(value)

    def _sync(self, on):
        self.edit.setVisible(on)
        self.empty.setVisible(not on)

    def value(self) -> Optional[date]:
        return self.edit.value() if self.check.isChecked() else None

    def setValue(self, d: Optional[date]):
        if d:
            self.edit.setValue(d)
        self.check.setChecked(d is not None)
        self._sync(d is not None)

    def setReadOnly(self, ro: bool):
        self.check.setEnabled(not ro)
        self.edit.setReadOnly(ro)


class MoneyEdit(QLineEdit):
    """Integer so'm. Accepts digits with spaces; never float."""

    def __init__(self, value: Optional[int] = None, parent=None, allow_empty: bool = True):
        super().__init__(parent)
        self.allow_empty = allow_empty
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setPlaceholderText("0")
        self.editingFinished.connect(self._reformat)
        self.setValue(value)

    def _reformat(self):
        v = self.value()
        if v is not None:
            self.setText(uz.money(v))

    def value(self) -> Optional[int]:
        raw = self.text().replace(" ", "").replace(" ", "")
        if not raw:
            return None if self.allow_empty else 0
        if not raw.isdigit():
            raise ValueError(raw)
        return int(raw)

    def setValue(self, v: Optional[int]):
        self.setText("" if v is None else uz.money(v))


@dataclass
class Cell:
    text: Any
    align: str = "left"         # left | right | center
    fg: Optional[str] = None
    bg: Optional[str] = None
    data: Any = None
    bold: bool = False


def money_cell(v, **kw) -> Cell:
    return Cell(uz.money(v), "right", **kw)


def make_table(headers: list[str], stretch: Optional[int] = None) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(26)
    h = t.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeToContents)
    h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    if stretch is not None:
        h.setSectionResizeMode(stretch, QHeaderView.Stretch)
    else:
        h.setStretchLastSection(True)
    t.setWordWrap(False)
    return t


_ALIGN = {"left": Qt.AlignLeft | Qt.AlignVCenter, "right": Qt.AlignRight | Qt.AlignVCenter,
          "center": Qt.AlignCenter}


def fill_table(t: QTableWidget, rows: list[list]):
    t.setSortingEnabled(False)
    t.setRowCount(len(rows))
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = v if isinstance(v, Cell) else Cell("" if v is None else v)
            it = QTableWidgetItem(str(c.text))
            if len(str(c.text)) > 25:
                it.setToolTip(str(c.text))
            it.setTextAlignment(_ALIGN[c.align])
            if c.fg:
                it.setForeground(QBrush(QColor(c.fg)))
            if c.bg:
                it.setBackground(QBrush(QColor(c.bg)))
            if c.bold:
                f = it.font(); f.setBold(True); it.setFont(f)
            if c.data is not None:
                it.setData(Qt.UserRole, c.data)
            t.setItem(i, j, it)


def wrap_rows(t: QTableWidget):
    """Let long text wrap inside cells (call after fill_table)."""
    t.setWordWrap(True)
    t.resizeRowsToContents()


def selected_data(t: QTableWidget, col: int = 0):
    r = t.currentRow()
    if r < 0 or t.item(r, col) is None:
        return None
    return t.item(r, col).data(Qt.UserRole)


def page_title(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("PageTitle")
    return lb


def card(label: str, value: str, sub: str = "") -> QFrame:
    f = QFrame()
    f.setObjectName("Card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(14, 10, 14, 10)
    v = QLabel(value); v.setObjectName("CardValue")
    lb = QLabel(label); lb.setObjectName("CardLabel")
    lay.addWidget(lb)
    lay.addWidget(v)
    if sub:
        s = QLabel(sub); s.setObjectName("CardLabel"); lay.addWidget(s)
    f.value_label = v
    return f


def badge(text: str, fg: str, bg: str) -> QLabel:
    lb = QLabel(text)
    lb.setStyleSheet(f"background:{bg}; color:{fg}; border:1px solid {fg}; border-radius:3px; "
                     f"padding:6px 10px; font-weight:600;")
    lb.setWordWrap(True)
    return lb


def _box(parent, icon, title, text, buttons):
    m = QMessageBox(icon, title, text, QMessageBox.NoButton, parent)
    out = [m.addButton(label, role) for label, role in buttons]
    m.exec()
    return out.index(m.clickedButton()) if m.clickedButton() in out else -1


def info(parent, text: str):
    _box(parent, QMessageBox.Information, uz.t("msg.info"), text, [(uz.t("btn.close"), QMessageBox.AcceptRole)])


def error(parent, text: str):
    _box(parent, QMessageBox.Warning, uz.t("msg.error"), text, [(uz.t("btn.close"), QMessageBox.AcceptRole)])


def confirm(parent, text: str) -> bool:
    return _box(parent, QMessageBox.Question, uz.t("msg.confirm"), text,
                [(uz.t("yes"), QMessageBox.YesRole), (uz.t("no"), QMessageBox.NoRole)]) == 0


def choose(parent, text: str, options: list[str]) -> int:
    """Index of the chosen option, -1 if closed."""
    return _box(parent, QMessageBox.Warning, uz.t("msg.confirm"), text,
                [(o, QMessageBox.ActionRole) for o in options])
