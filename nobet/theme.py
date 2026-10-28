"""Modern görünüm: renkler, Qt stil sayfası ve sol menülü sayfa gezgini."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QStackedWidget, QVBoxLayout, QWidget)

ACCENT = "#4f46e5"
ACCENT_HOVER = "#4338ca"
ACCENT_SOFT = "#eef2ff"
BG = "#f4f6fb"
CARD = "#ffffff"
BORDER = "#e2e8f0"
TEXT = "#1e293b"
MUTED = "#64748b"
SIDEBAR = "#1e1b4b"

# Tablo satır renkleri
GREEN = QColor("#e7f8ee")
YELLOW = QColor("#fff6db")
RED = QColor("#fde7e7")
BLUE = QColor("#e8edff")

STYLE = f"""
QWidget {{ color: {TEXT}; font-size: 10pt; }}
QMainWindow, QDialog, #page {{ background: {BG}; }}
QToolTip {{ background: {TEXT}; color: white; border: none; padding: 6px; border-radius: 4px; }}

/* Kartlar */
QGroupBox {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px;
    margin-top: 14px; padding: 14px 12px 12px 12px; font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 14px; padding: 2px 6px; color: {TEXT};
    background: transparent;
}}
QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#hint {{ background: {ACCENT_SOFT}; border: 1px solid #c7d2fe; border-radius: 12px; }}

/* Düğmeler */
QPushButton {{
    background: {CARD}; border: 1px solid #cbd5e1; border-radius: 8px;
    padding: 7px 14px; font-weight: 500;
}}
QPushButton:hover {{ background: #f1f5f9; border-color: #94a3b8; }}
QPushButton:pressed {{ background: #e2e8f0; }}
QPushButton:disabled {{ color: #a0aec0; background: #f8fafc; border-color: {BORDER}; }}
QPushButton[variant="primary"] {{
    background: {ACCENT}; color: white; border: none; font-weight: 600; padding: 9px 18px;
}}
QPushButton[variant="primary"]:hover {{ background: {ACCENT_HOVER}; }}
QPushButton[variant="primary"]:disabled {{ background: #a5b4fc; color: #eef2ff; }}
QPushButton[variant="danger"] {{ color: #b91c1c; border-color: #fecaca; }}
QPushButton[variant="danger"]:hover {{ background: #fef2f2; }}
QPushButton[variant="step"] {{
    text-align: left; padding: 14px 16px; font-size: 11pt; font-weight: 600;
    background: {CARD}; border: 1px solid #c7d2fe; border-radius: 10px;
}}
QPushButton[variant="step"]:hover {{ background: #f5f7ff; border-color: {ACCENT}; }}

/* Giriş alanları */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QPlainTextEdit {{
    background: {CARD}; border: 1px solid #cbd5e1; border-radius: 7px; padding: 5px 8px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {CARD}; border: 1px solid {BORDER}; selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT}; outline: none;
}}
QCheckBox {{ spacing: 8px; }}

/* Tablolar ve listeler */
QTableWidget, QListWidget#list {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px;
    gridline-color: #eef2f7; alternate-background-color: #fafbfe;
    selection-background-color: {ACCENT_SOFT}; selection-color: {TEXT};
}}
QHeaderView::section {{
    background: #f8fafc; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 7px 6px; font-weight: 600;
}}
QTableCornerButton::section {{ background: #f8fafc; border: none; }}
QListWidget#list::item {{ padding: 7px 8px; border-radius: 6px; }}
QListWidget#list::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #cbd5e1; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #cbd5e1; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QSplitter::handle {{ background: transparent; width: 8px; }}
QStatusBar {{ background: {CARD}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
QProgressDialog {{ background: {CARD}; }}

/* Sol menü */
QFrame#sidebar {{ background: {SIDEBAR}; }}
QLabel#brand {{ color: white; font-size: 13pt; font-weight: 700; }}
QLabel#brandSub {{ color: #a5b4fc; font-size: 9pt; }}
QListWidget#nav {{ background: transparent; border: none; outline: none; }}
QListWidget#nav::item {{
    color: #c7d2fe; padding: 11px 14px; margin: 2px 10px; border-radius: 8px; font-size: 10.5pt;
}}
QListWidget#nav::item:hover {{ background: rgba(255, 255, 255, 0.08); color: white; }}
QListWidget#nav::item:selected {{ background: {ACCENT}; color: white; font-weight: 600; }}

/* Sayfa başlıkları ve özet kutucukları */
QLabel#title {{ font-size: 17pt; font-weight: 700; color: {TEXT}; }}
QLabel#subtitle {{ color: {MUTED}; font-size: 10pt; }}
QFrame#stat {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}
QLabel#statValue {{ font-size: 20pt; font-weight: 700; }}
QLabel#statLabel {{ color: {MUTED}; font-size: 9pt; }}
"""


def apply(app):
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)


def variant(button, name):
    """Düğmeye stil türü verir: primary, danger, step."""
    button.setProperty("variant", name)
    button.setCursor(Qt.PointingHandCursor)
    return button


def page_header(title, subtitle=""):
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(2, 0, 0, 6)
    v.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("title")
    v.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("subtitle")
        s.setWordWrap(True)
        v.addWidget(s)
    return w


class StatCard(QFrame):
    def __init__(self, label, color=ACCENT):
        super().__init__()
        self.setObjectName("stat")
        self.value = QLabel("—")
        self.value.setObjectName("statValue")
        self.value.setStyleSheet(f"color:{color}")
        text = QLabel(label)
        text.setObjectName("statLabel")
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 10, 16, 10)
        v.setSpacing(0)
        v.addWidget(self.value)
        v.addWidget(text)

    def set(self, value):
        self.value.setText(str(value))


class NavPages(QWidget):
    """QTabWidget yerine sol menülü sayfa gezgini (aynı temel arayüzle)."""

    currentChanged = Signal(int)

    def __init__(self, brand, subtitle):
        super().__init__()
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 22, 0, 16)
        sv.setSpacing(4)
        b = QLabel(brand)
        b.setObjectName("brand")
        b.setWordWrap(True)
        s = QLabel(subtitle)
        s.setObjectName("brandSub")
        for lab in (b, s):
            lab.setContentsMargins(22, 0, 16, 0)
            sv.addWidget(lab)
        sv.addSpacing(18)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setCursor(Qt.PointingHandCursor)
        sv.addWidget(self.nav, 1)
        self.footer = QLabel()
        self.footer.setObjectName("brandSub")
        self.footer.setContentsMargins(22, 0, 16, 0)
        self.footer.setWordWrap(True)
        sv.addWidget(self.footer)

        self.stack = QStackedWidget()
        self.stack.setObjectName("page")
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(side)
        h.addWidget(self.stack, 1)
        self.nav.currentRowChanged.connect(self._go)

    def addTab(self, widget, label):
        page = QWidget()
        page.setObjectName("page")
        v = QVBoxLayout(page)
        v.setContentsMargins(22, 18, 22, 14)
        v.addWidget(widget)
        widget.setParent(page)
        self.stack.addWidget(page)
        self.nav.addItem(QListWidgetItem(label))
        if self.nav.count() == 1:
            self.nav.setCurrentRow(0)

    def _go(self, i):
        self.stack.setCurrentIndex(i)
        self.currentChanged.emit(i)

    def widget(self, i):
        page = self.stack.widget(i)
        return page.layout().itemAt(0).widget() if page else None

    def setCurrentWidget(self, widget):
        for i in range(self.stack.count()):
            if self.widget(i) is widget:
                self.nav.setCurrentRow(i)
                return
