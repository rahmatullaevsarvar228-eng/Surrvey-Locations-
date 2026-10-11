"""Main window: sidebar navigation + pages; project cards open in their own windows."""
from __future__ import annotations

from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..db.repository import User
from ..i18n import uz
from ..services import Service
from .dialogs import LoginDialog
from .pages import AuditPage, ControlsPage, HomePage, ProjectsPage, ReportsPage, SettingsPage
from .project_card import ProjectCard

NAV = (("nav.home", HomePage), ("nav.projects", ProjectsPage), ("nav.controls", ControlsPage),
       ("nav.reports", ReportsPage), ("nav.settings", SettingsPage), ("nav.audit", AuditPage))


class MainWindow(QMainWindow):
    def __init__(self, service: Service, user: User):
        super().__init__()
        self.service, self.user = service, user
        self.cards: dict[int, ProjectCard] = {}
        self.setWindowTitle(f"{uz.APP_NAME} — {service.settings.organization}")
        self.resize(1360, 840)
        self._build()

    def _build(self):
        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QWidget(); side.setObjectName("Sidebar"); side.setFixedWidth(230)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)
        t = QLabel(uz.APP_NAME); t.setObjectName("SidebarTitle")
        s = QLabel("BHMS 11 (2024) | IAS 38"); s.setObjectName("SidebarSub")
        sv.addWidget(t)
        sv.addWidget(s)
        self.stack = QStackedWidget()
        self.group = QButtonGroup(self)
        self.pages = []
        for i, (key, cls) in enumerate(NAV):
            b = QPushButton(uz.t(key)); b.setCheckable(True)
            self.group.addButton(b, i)
            sv.addWidget(b)
            page = cls(self.service, self.user)
            page.open_project.connect(self.open_project)
            page.changed.connect(self.refresh_all)
            self.pages.append(page)
            self.stack.addWidget(page)
        sv.addStretch()
        self.user_label = QLabel(); self.user_label.setObjectName("SidebarUser"); self.user_label.setWordWrap(True)
        sv.addWidget(self.user_label)
        sw = QPushButton(uz.t("user.change"))
        sw.clicked.connect(self._switch_user)
        sv.addWidget(sw)
        sv.addSpacing(10)
        self.group.idClicked.connect(self.show_page)
        h.addWidget(side)
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self._update_user()
        self.show_page(0)

    def _update_user(self):
        ro = f"\n{uz.t('user.readonly')}" if self.user.role == "auditor" else ""
        self.user_label.setText(f"{self.user.name}\n{uz.ROLE[self.user.role]}{ro}")

    def show_page(self, i: int):
        self.group.button(i).setChecked(True)
        self.stack.setCurrentIndex(i)
        self.pages[i].refresh()

    def refresh_all(self):
        self.pages[self.stack.currentIndex()].refresh()
        for c in list(self.cards.values()):
            c.refresh()

    def open_project(self, pid: int) -> ProjectCard:
        c = self.cards.get(pid)
        if c is None or not c.isVisible():
            c = ProjectCard(self.service, self.user, pid, on_change=self._card_changed)
            self.cards[pid] = c
        c.show()
        c.raise_()
        c.activateWindow()
        return c

    def _card_changed(self):
        self.pages[self.stack.currentIndex()].refresh()

    def _switch_user(self):
        d = LoginDialog(self, self.user)
        if d.exec():
            for c in self.cards.values():
                c.close()
            self.cards.clear()
            self.user = d.user()
            old = self.centralWidget()
            self._build()
            old.deleteLater()

    def closeEvent(self, e):
        for c in self.cards.values():
            c.close()
        super().closeEvent(e)
