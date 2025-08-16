import os, sys, json, signal, time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtNetwork import QUdpSocket, QHostAddress

from controller.page import Page

# ---- Small page cycler that swaps the Page widget ----
class PageCycler:
    def __init__(self, container: QWidget, paths: list[str]):
        self.container = container
        self.paths = [p for p in paths if p] or []
        if not self.paths:
            raise RuntimeError("No page JSON paths configured.")
        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.current = None
        self.index = -1
        self.next_page()  # show first page

    def next_page(self):
        self.index = (self.index + 1) % len(self.paths)
        path = self.paths[self.index]
        new_page = Page(path)
        if self.current:
            self.layout.removeWidget(self.current)
            self.current.hide()
            self.current.deleteLater()
        self.layout.addWidget(new_page)
        new_page.show()
        self.current = new_page
        print(f"[ui] Showing {path}")