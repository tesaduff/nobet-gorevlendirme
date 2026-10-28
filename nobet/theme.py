"""Modern görünüm: renkler, Qt stil sayfası ve sol menülü sayfa gezgini."""
import os
import sys

from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractScrollArea, QAbstractSpinBox, QComboBox, QFrame,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

# Ayarlar'dan seçilebilen vurgu renkleri: ad -> (ana renk, üzerine gelince, açık ton, menü zemini)
ACCENTS = {
    "Mor": ("#4f46e5", "#4338ca", "#eef2ff", "#1e1b4b"),
    "Mavi": ("#2563eb", "#1d4ed8", "#eff6ff", "#172554"),
    "Yeşil": ("#059669", "#047857", "#ecfdf5", "#022c22"),
    "Turuncu": ("#ea580c", "#c2410c", "#fff7ed", "#431407"),
    "Kırmızı": ("#dc2626", "#b91c1c", "#fef2f2", "#450a0a"),
    "Gri": ("#475569", "#334155", "#f1f5f9", "#0f172a"),
    "Lacivert": ("#1e40af", "#1e3a8a", "#eff6ff", "#0b1a3e"),
    "Turkuaz": ("#0891b2", "#0e7490", "#ecfeff", "#083344"),
    "Pembe": ("#db2777", "#be185d", "#fdf2f8", "#500724"),
    "Mor-Lila": ("#9333ea", "#7e22ce", "#faf5ff", "#3b0764"),
    "Kahve": ("#92400e", "#78350f", "#fffbeb", "#2b1505"),
    "Zeytin": ("#4d7c0f", "#3f6212", "#f7fee7", "#1a2e05"),
}
RADII = {"Keskin": 3, "Normal": 8, "Yuvarlak": 14}
# Arka plan: ad -> (açık zemin, koyu zemin); None = düz renk yerine tema renginden geçiş
BACKGROUNDS = {"Sade": ("#f4f6fb", "#0f172a"), "Renk geçişli": (None, None),
               "Sıcak": ("#f8f3ea", "#1c1917"), "Serin": ("#eaf1f8", "#0b1726"),
               "Beyaz": ("#ffffff", "#111827")}
FONTS = ["Segoe UI", "Calibri", "Arial", "Tahoma", "Verdana", "Trebuchet MS"]

# Tablo satır renkleri: arayüz bu nesneleri kullanır, tema değişince yerinde güncellenir.
GREEN, YELLOW, RED, BLUE = QColor(), QColor(), QColor(), QColor()
_ROWS = {False: ("#e7f8ee", "#fff6db", "#fde7e7", "#e8edff"),
         True: ("#123527", "#3d3315", "#47201f", "#252b4d")}

ACCENT = ACCENTS["Mor"][0]
MUTED = "#64748b"


def resource(name):
    """Paketlenmiş (PyInstaller) veya kaynak koddan çalışırken assets/ içindeki dosya."""
    base = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(__file__), ".."))
    return os.path.abspath(os.path.join(base, "assets", name))


def app_icon():
    return QIcon(resource("icon.png"))


def build_style(accent="Mor", dark=False, radius="Normal", background="Sade"):
    global ACCENT, MUTED
    R = RADII.get(radius, 8)
    R2 = R + 4
    a, a_hover, a_soft, side = ACCENTS.get(accent, ACCENTS["Mor"])
    if dark:
        BG, CARD, BORDER, TEXT, MUTED = "#0f172a", "#1e293b", "#334155", "#e2e8f0", "#94a3b8"
        INPUT_BORDER, HOVER, HEAD, ALT = "#475569", "#273449", "#172033", "#223047"
        a_soft = "#2b3357"
        side = "#0b1120"
    else:
        BG, CARD, BORDER, TEXT, MUTED = "#f4f6fb", "#ffffff", "#e2e8f0", "#1e293b", "#64748b"
        INPUT_BORDER, HOVER, HEAD, ALT = "#cbd5e1", "#f1f5f9", "#f8fafc", "#fafbfe"
    plain, plain_dark = BACKGROUNDS.get(background, BACKGROUNDS["Sade"])
    if plain is None:
        # Sayfa zemini tema renginin açık tonundan yumuşakça açılır
        PAGE_BG = (f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {a_soft}, stop:0.55 {BG}, "
                   f"stop:1 {BG})")
    else:
        BG = plain_dark if dark else plain
        PAGE_BG = BG
    CHECK = resource("check_white.png").replace("\\", "/")
    ACCENT = a
    for color, value in zip((GREEN, YELLOW, RED, BLUE), _ROWS[dark]):
        color.setRgb(QColor(value).rgb())
    tone = "light" if dark else "dark"
    ARROW_DOWN = resource(f"chevron_down_{tone}.png").replace("\\", "/")
    ARROW_UP = resource(f"chevron_up_{tone}.png").replace("\\", "/")
    values = dict(locals())
    values["MUTED"] = MUTED
    return STYLE.format(**values)


STYLE = """
QWidget {{ color: {TEXT}; }}
QMainWindow, QDialog {{ background: {BG}; }}
#page, QScrollArea#page > QWidget > QWidget {{ background: {PAGE_BG}; }}
QToolTip {{ background: {TEXT}; color: white; border: none; padding: 6px; border-radius: 4px; }}

/* Kartlar */
QGroupBox {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: {R2}px;
    margin-top: 14px; padding: 14px 12px 12px 12px; font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 14px; padding: 2px 8px; color: {a};
    background: transparent;
}}
QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: {R2}px; }}
QFrame#hint {{ background: {a_soft}; border: 1px solid {a}; border-radius: {R2}px; }}

/* Düğmeler */
QPushButton {{
    background: {CARD}; border: 1px solid {INPUT_BORDER}; border-radius: {R}px;
    padding: 7px 14px; font-weight: 500;
}}
QPushButton:hover {{ background: {HOVER}; border-color: #94a3b8; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {MUTED}; background: {HEAD}; border-color: {BORDER}; }}
QPushButton[variant="primary"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {a}, stop:1 {a_hover});
    color: white; border: none; font-weight: 600; padding: 9px 18px;
}}
QPushButton[variant="primary"]:hover {{ background: {a_hover}; }}
QPushButton[variant="primary"]:disabled {{ background: #a5b4fc; color: #eef2ff; }}
QPushButton[variant="success"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16a34a, stop:1 #059669);
    color: white; border: none; font-weight: 700; padding: 9px 18px;
}}
QPushButton[variant="success"]:hover {{ background: #15803d; }}
QPushButton[variant="success"]:disabled {{ background: #bbf7d0; color: #166534; }}
QPushButton[variant="danger"] {{ color: #ef4444; border-color: #fca5a5; }}
QPushButton[variant="danger"]:hover {{ background: {HOVER}; }}
QPushButton[variant="step"] {{
    text-align: left; padding: 14px 16px; font-size: 11pt; font-weight: 600;
    background: {CARD}; border: 1px solid {a}; border-radius: {R2}px;
}}
QPushButton[variant="step"]:hover {{ background: {a_soft}; border-color: {a}; }}

QPushButton#choice {{ text-align: left; padding: 5px 10px; font-weight: 500; }}

/* Giriş alanları */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QPlainTextEdit {{
    background: {CARD}; border: 1px solid {INPUT_BORDER}; border-radius: {R}px; padding: 5px 8px;
    selection-background-color: {a};
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {a};
}}
QComboBox, QDateEdit {{ padding-right: 30px; }}
QComboBox::drop-down, QDateEdit::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right; width: 28px; border: none;
}}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url({ARROW_DOWN}); width: 12px; height: 12px; }}
QComboBox::down-arrow:on {{ image: url({ARROW_UP}); }}
QSpinBox {{ padding-right: 24px; }}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border; width: 22px; border: none; background: transparent;
}}
QSpinBox::up-button {{ subcontrol-position: top right; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; }}
QSpinBox::up-arrow {{ image: url({ARROW_UP}); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url({ARROW_DOWN}); width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{
    background: {CARD}; border: 1px solid {BORDER}; selection-background-color: {a_soft};
    selection-color: {TEXT}; outline: none;
}}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QTableView::indicator, QListView::indicator {{
    width: 18px; height: 18px; border: 2px solid {MUTED}; border-radius: 5px; background: {CARD};
}}
QCheckBox::indicator:hover, QTableView::indicator:hover, QListView::indicator:hover {{
    border-color: {a};
}}
QCheckBox::indicator:checked, QTableView::indicator:checked, QListView::indicator:checked {{
    background: {a}; border-color: {a}; image: url({CHECK});
}}
QCheckBox::indicator:disabled {{ background: {HEAD}; border-color: {BORDER}; }}
QRadioButton::indicator {{
    width: 14px; height: 14px; border: 2px solid {MUTED}; border-radius: 9px; background: {CARD};
}}
QRadioButton::indicator:hover {{ border-color: {a}; }}
QRadioButton::indicator:checked {{
    border-color: {a};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 {a},
                                stop:0.55 {a}, stop:0.62 {CARD}, stop:1 {CARD});
}}

/* Tablolar ve listeler */
QTableWidget, QListWidget#list {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: {R2}px;
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
QFrame#sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0.4, y2:1, stop:0 {a_hover}, stop:0.45 {side},
                                stop:1 {side});
}}
QLabel#brand {{ color: white; font-size: 13pt; font-weight: 700; }}
QLabel#brandSub {{ color: #c7d2fe; font-size: 9pt; }}
QFrame#brandLine {{ background: rgba(255, 255, 255, 0.16); max-height: 1px; margin: 0 22px; }}
QPushButton#exit {{
    background: rgba(255, 255, 255, 0.08); color: #fecaca; border: 1px solid rgba(255,255,255,0.18);
    border-radius: 8px; padding: 9px 12px; margin: 0 14px; font-weight: 600; text-align: center;
}}
QPushButton#exit:hover {{ background: #dc2626; color: white; border-color: #dc2626; }}
QListWidget#nav {{ background: transparent; border: none; outline: none; }}
QListWidget#nav::item {{
    color: #c7d2fe; padding: 8px 14px; margin: 1px 10px; border-radius: 8px; font-size: 10.5pt;
}}
QListWidget#nav::item:hover {{ background: rgba(255, 255, 255, 0.08); color: white; }}
QListWidget#nav::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {a}, stop:1 {a_hover});
    color: white; font-weight: 700; border-left: 4px solid white;
}}

/* Sayfa başlıkları ve özet kutucukları */
QFrame#header {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {a_soft}, stop:1 {BG});
    border: none; border-left: 5px solid {a}; border-radius: {R}px;
}}
QLabel#title {{ font-size: 17pt; font-weight: 800; color: {a}; background: transparent; }}
QLabel#subtitle {{ color: {MUTED}; background: transparent; }}
QFrame#stat {{
    background: {CARD}; border: 1px solid {BORDER}; border-top: 4px solid {a};
    border-radius: {R2}px;
}}
QLabel#logoBox {{
    background: {a_soft}; border: 2px dashed {a}; border-radius: {R2}px; color: {MUTED};
}}
QLabel#stepOn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {a}, stop:1 {a_hover});
    color: white; border-radius: 12px; font-weight: 700; padding: 4px 10px;
}}
QLabel#stepDone {{
    background: {a_soft}; color: {a}; border-radius: 12px; font-weight: 600; padding: 4px 10px;
}}
QLabel#stepTodo {{
    background: {HEAD}; color: {MUTED}; border: 1px solid {BORDER}; border-radius: 12px;
    padding: 3px 9px;
}}
QLabel#statValue {{ font-size: 20pt; font-weight: 700; }}
QLabel#statLabel {{ color: {MUTED}; font-size: 9pt; }}
"""


FONT_SIZES = {"Küçük": 9, "Normal": 10, "Büyük": 11, "Çok büyük": 12.5}
DENSITIES = {"Sıkı": 30, "Normal": 36, "Rahat": 44}
ROW_HEIGHT = 36


class WheelGuard(QObject):
    """Fare tekerleği, tıklanmamış açılır kutu / sayı kutusunun değerini değiştirmesin;
    bunun yerine sayfayı kaydırsın."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and isinstance(obj, (QComboBox, QAbstractSpinBox)) \
                and not obj.hasFocus():
            w = obj.parentWidget()
            while w is not None and not isinstance(w, QAbstractScrollArea):
                w = w.parentWidget()
            if w is not None:
                bar = w.verticalScrollBar()
                bar.setValue(bar.value() - event.angleDelta().y())
            return True
        return False


_guard = None


def apply(app, accent="Mor", dark=False, font_size="Normal", density="Normal",
          radius="Normal", family="Segoe UI", background="Sade"):
    global ROW_HEIGHT, _guard
    size = FONT_SIZES.get(font_size, 10)
    ROW_HEIGHT = int(DENSITIES.get(density, 36) * size / 10)
    font = QFont(family or "Segoe UI")
    font.setPointSizeF(size)
    font.setStyleHint(QFont.SansSerif)
    # Yalnızca değişen ayar uygulanır: her uygulama tüm pencereyi yeniden çizdirir.
    if app.font() != font:
        app.setFont(font)
    if _guard is None:
        app.setStyle("Fusion")
        app.setWindowIcon(app_icon())
    style = build_style(accent, dark, radius, background)
    if app.styleSheet() != style:
        app.setStyleSheet(style)
    if _guard is None:
        _guard = WheelGuard(app)
        app.installEventFilter(_guard)


def variant(button, name):
    """Düğmeye stil türü verir: primary, success, danger, step."""
    button.setProperty("variant", name)
    button.setCursor(Qt.PointingHandCursor)
    return button


def page_header(title, subtitle=""):
    w = QFrame()
    w.setObjectName("header")
    v = QVBoxLayout(w)
    v.setContentsMargins(16, 10, 12, 10)
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
        h.setContentsMargins(10, 6, 10, 6)
        h.setSpacing(4)
        for i, t in enumerate(titles):
            if i:
                arrow = QLabel("›")
                arrow.setObjectName("subtitle")
                arrow.setStyleSheet("font-size:14pt")
                h.addWidget(arrow)
            lab = QLabel(f"{i + 1}  {t}")
            self.labels.append(lab)
            h.addWidget(lab)
        h.addStretch()
        self.set(0)

    def set(self, index):
        # Renkler stil sayfasından gelir: tema değişince adım çubuğu da hemen değişir.
        for i, lab in enumerate(self.labels):
            name = "stepOn" if i == index else "stepDone" if i < index else "stepTodo"
            text = lab.text().split("  ", 1)[1]
            lab.setText(f"✓  {text}" if i < index else f"{i + 1}  {text}")
            lab.setObjectName(name)
            lab.style().unpolish(lab)
            lab.style().polish(lab)


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
        self.logo.setFixedHeight(68)
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setContentsMargins(0, 0, 0, 6)
        sv.addWidget(self.logo)
        self.brand = b = QLabel(brand)
        b.setObjectName("brand")
        b.setWordWrap(True)
        self.brand_sub = s = QLabel(subtitle)
        s.setObjectName("brandSub")
        s.setWordWrap(True)
        for lab in (b, s):
            lab.setAlignment(Qt.AlignCenter)
            lab.setContentsMargins(14, 0, 14, 0)
            sv.addWidget(lab)
        sv.addSpacing(12)
        line = QFrame()
        line.setObjectName("brandLine")
        line.setFixedHeight(1)
        sv.addWidget(line)
        sv.addSpacing(10)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setCursor(Qt.PointingHandCursor)
        sv.addWidget(self.nav, 1)
        self.footer = QLabel()
        self.footer.setObjectName("brandSub")
        self.footer.setContentsMargins(14, 6, 14, 0)
        self.footer.setAlignment(Qt.AlignCenter)
        self.footer.setWordWrap(True)
        self.exit_btn = QPushButton("⏻   Çıkış")
        self.exit_btn.setObjectName("exit")
        self.exit_btn.setCursor(Qt.PointingHandCursor)
        sv.addWidget(self.exit_btn)
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
            self.logo.setPixmap(pixmap.scaled(62, 62, Qt.KeepAspectRatio, Qt.SmoothTransformation))

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
        item.setSizeHint(QSize(0, int(ROW_HEIGHT * 1.12)))
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
