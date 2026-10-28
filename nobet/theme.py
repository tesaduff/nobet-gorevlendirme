"""Modern görünüm: renkler, Qt stil sayfası ve sol menülü sayfa gezgini."""
import os
import sys

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

# Ayarlar'dan seçilebilen vurgu renkleri: ad -> (ana renk, üzerine gelince, açık ton, menü zemini)
ACCENTS = {
    "Mor": ("#4f46e5", "#4338ca", "#eef2ff", "#1e1b4b"),
    "Mavi": ("#2563eb", "#1d4ed8", "#eff6ff", "#172554"),
    "Yeşil": ("#059669", "#047857", "#ecfdf5", "#022c22"),
    "Turuncu": ("#ea580c", "#c2410c", "#fff7ed", "#431407"),
    "Kırmızı": ("#dc2626", "#b91c1c", "#fef2f2", "#450a0a"),
    "Gri": ("#475569", "#334155", "#f1f5f9", "#0f172a"),
}

# Tablo satır renkleri: arayüz bu nesneleri kullanır, tema değişince yerinde güncellenir.
GREEN, YELLOW, RED, BLUE = QColor(), QColor(), QColor(), QColor()
_ROWS = {False: ("#e7f8ee", "#fff6db", "#fde7e7", "#e8edff"),
         True: ("#123527", "#3d3315", "#47201f", "#252b4d")}

ACCENT = ACCENTS["Mor"][0]
MUTED = "#64748b"


def resource(name):
    """Paketlenmiş (PyInstaller) veya kaynak koddan çalışırken assets/ içindeki dosya."""
    base = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base, "assets", name)


def app_icon():
    return QIcon(resource("icon.png"))


def build_style(accent="Mor", dark=False):
    global ACCENT, MUTED
    a, a_hover, a_soft, side = ACCENTS.get(accent, ACCENTS["Mor"])
    if dark:
        BG, CARD, BORDER, TEXT, MUTED = "#0f172a", "#1e293b", "#334155", "#e2e8f0", "#94a3b8"
        INPUT_BORDER, HOVER, HEAD, ALT = "#475569", "#273449", "#172033", "#223047"
        a_soft = "#2b3357"
        side = "#0b1120"
    else:
        BG, CARD, BORDER, TEXT, MUTED = "#f4f6fb", "#ffffff", "#e2e8f0", "#1e293b", "#64748b"
        INPUT_BORDER, HOVER, HEAD, ALT = "#cbd5e1", "#f1f5f9", "#f8fafc", "#fafbfe"
    ACCENT = a
    for color, value in zip((GREEN, YELLOW, RED, BLUE), _ROWS[dark]):
        color.setRgb(QColor(value).rgb())
    values = dict(locals())
    values["MUTED"] = MUTED
    return STYLE.format(**values)


STYLE = """
QWidget {{ color: {TEXT}; }}
QMainWindow, QDialog, #page, QScrollArea#page > QWidget > QWidget {{ background: {BG}; }}
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
QFrame#hint {{ background: {a_soft}; border: 1px solid {a}; border-radius: 12px; }}

/* Düğmeler */
QPushButton {{
    background: {CARD}; border: 1px solid {INPUT_BORDER}; border-radius: 8px;
    padding: 7px 14px; font-weight: 500;
}}
QPushButton:hover {{ background: {HOVER}; border-color: #94a3b8; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {MUTED}; background: {HEAD}; border-color: {BORDER}; }}
QPushButton[variant="primary"] {{
    background: {a}; color: white; border: none; font-weight: 600; padding: 9px 18px;
}}
QPushButton[variant="primary"]:hover {{ background: {a_hover}; }}
QPushButton[variant="primary"]:disabled {{ background: #a5b4fc; color: #eef2ff; }}
QPushButton[variant="danger"] {{ color: #ef4444; border-color: #fca5a5; }}
QPushButton[variant="danger"]:hover {{ background: {HOVER}; }}
QPushButton[variant="step"] {{
    text-align: left; padding: 14px 16px; font-size: 11pt; font-weight: 600;
    background: {CARD}; border: 1px solid {a}; border-radius: 10px;
}}
QPushButton[variant="step"]:hover {{ background: {a_soft}; border-color: {a}; }}

/* Giriş alanları */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QPlainTextEdit {{
    background: {CARD}; border: 1px solid {INPUT_BORDER}; border-radius: 7px; padding: 5px 8px;
    selection-background-color: {a};
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {a};
}}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {CARD}; border: 1px solid {BORDER}; selection-background-color: {a_soft};
    selection-color: {TEXT}; outline: none;
}}
QCheckBox {{ spacing: 8px; }}

/* Tablolar ve listeler */
QTableWidget, QListWidget#list {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px;
    gridline-color: #eef2f7; alternate-background-color: {ALT};
    selection-background-color: {a_soft}; selection-color: {TEXT};
}}
QHeaderView::section {{
    background: {HEAD}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 7px 6px; font-weight: 600;
}}
QTableCornerButton::section {{ background: {HEAD}; border: none; }}
QListWidget#list::item {{ padding: 7px 8px; border-radius: 6px; }}
QListWidget#list::item:selected {{ background: {a_soft}; color: {TEXT}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #cbd5e1; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #cbd5e1; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QSplitter::handle {{ background: transparent; width: 8px; }}
QStatusBar {{ background: {CARD}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
QProgressDialog {{ background: {CARD}; }}

/* Sol menü */
QFrame#sidebar {{ background: {side}; }}
QLabel#brand {{ color: white; font-size: 13pt; font-weight: 700; }}
QLabel#brandSub {{ color: #c7d2fe; font-size: 9pt; }}
QListWidget#nav {{ background: transparent; border: none; outline: none; }}
QListWidget#nav::item {{
    color: #c7d2fe; padding: 11px 14px; margin: 2px 10px; border-radius: 8px; font-size: 10.5pt;
}}
QListWidget#nav::item:hover {{ background: rgba(255, 255, 255, 0.08); color: white; }}
QListWidget#nav::item:selected {{ background: {a}; color: white; font-weight: 600; }}

/* Sayfa başlıkları ve özet kutucukları */
QLabel#title {{ font-size: 17pt; font-weight: 700; color: {TEXT}; }}
QLabel#subtitle {{ color: {MUTED}; }}
QFrame#stat {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}
QLabel#statValue {{ font-size: 20pt; font-weight: 700; }}
QLabel#statLabel {{ color: {MUTED}; font-size: 9pt; }}
"""


FONT_SIZES = {"Küçük": 9, "Normal": 10, "Büyük": 11, "Çok büyük": 12.5}
DENSITIES = {"Sıkı": 30, "Normal": 36, "Rahat": 44}
ROW_HEIGHT = 36


def apply(app, accent="Mor", dark=False, font_size="Normal", density="Normal"):
    global ROW_HEIGHT
    size = FONT_SIZES.get(font_size, 10)
    ROW_HEIGHT = int(DENSITIES.get(density, 36) * size / 10)
    font = QFont("Segoe UI")
    font.setPointSizeF(size)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)
    app.setStyle("Fusion")
    app.setStyleSheet(build_style(accent, dark))
    app.setWindowIcon(app_icon())


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


class StepBar(QFrame):
    """Kademeli sayfaların üstündeki adım göstergesi: ① Öğretmen seç  ›  ② …"""

    def __init__(self, titles):
        super().__init__()
        self.setObjectName("card")
        self.labels = []
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 8, 14, 8)
        for i, t in enumerate(titles):
            if i:
                arrow = QLabel("›")
                arrow.setObjectName("subtitle")
                arrow.setStyleSheet("font-size:14pt")
                h.addWidget(arrow)
            lab = QLabel(f"{i + 1}  {t}")
            lab.setContentsMargins(10, 4, 10, 4)
            self.labels.append(lab)
            h.addWidget(lab)
        h.addStretch()
        self.set(0)

    def set(self, index):
        for i, lab in enumerate(self.labels):
            if i == index:
                lab.setStyleSheet(f"background:{ACCENT}; color:white; border-radius:8px;"
                                  " font-weight:700")
            elif i < index:
                lab.setStyleSheet(f"color:{ACCENT}; font-weight:600")
            else:
                lab.setStyleSheet(f"color:{MUTED}")


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
        side.setFixedWidth(210)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 22, 0, 16)
        sv.setSpacing(4)
        self.logo = QLabel()
        self.logo.setFixedHeight(64)
        self.logo.setContentsMargins(22, 0, 16, 6)
        sv.addWidget(self.logo)
        self.brand = b = QLabel(brand)
        b.setObjectName("brand")
        b.setWordWrap(True)
        self.brand_sub = s = QLabel(subtitle)
        s.setObjectName("brandSub")
        s.setWordWrap(True)
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

    def set_brand(self, title, subtitle, pixmap=None):
        self.brand.setText(title)
        self.brand_sub.setText(subtitle)
        if pixmap and not pixmap.isNull():
            self.logo.setPixmap(pixmap.scaled(58, 58, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def addTab(self, widget, label, min_height=0):
        """Sayfayı kaydırılabilir alana koyar: küçük ekranlarda içerik sıkışmaz, kaydırılır."""
        page = QWidget()
        page.setObjectName("page")
        v = QVBoxLayout(page)
        v.setContentsMargins(18, 14, 18, 12)
        v.addWidget(widget)
        if min_height:
            page.setMinimumHeight(min_height)
        scroll = QScrollArea()
        scroll.setObjectName("page")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(page)
        self._widgets = getattr(self, "_widgets", []) + [widget]
        self.stack.addWidget(scroll)
        item = QListWidgetItem(label)
        item.setSizeHint(QSize(0, int(ROW_HEIGHT * 1.25)))
        self.nav.addItem(item)
        if self.nav.count() == 1:
            self.nav.setCurrentRow(0)

    def _go(self, i):
        self.stack.setCurrentIndex(i)
        self.currentChanged.emit(i)

    def widget(self, i):
        widgets = getattr(self, "_widgets", [])
        return widgets[i] if 0 <= i < len(widgets) else None

    def setCurrentWidget(self, widget):
        for i in range(self.stack.count()):
            if self.widget(i) is widget:
                self.nav.setCurrentRow(i)
                return
