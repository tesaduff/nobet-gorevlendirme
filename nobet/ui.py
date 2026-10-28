"""Ana pencere ve diyaloglar (PySide6)."""
import datetime as dt
import os
import shutil

from PySide6.QtCore import QDate, QLocale, QStandardPaths, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QImage, QPageLayout, QPixmap, QTextDocument
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QBoxLayout, QCheckBox, QComboBox,
                               QStackedWidget,
                               QFrame,
                               QCompleter, QDateEdit, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog,
                               QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
                               QProgressDialog, QPushButton, QSpinBox, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from . import export, theme, updater
from .theme import BLUE, GREEN, RED, YELLOW, page_header, variant
from .db import Database, data_dir
from .names import DAYS, NameMatcher, clean_name, normalize, split_info
from .parse_duty import DutyEntry, is_admin_place, parse_duty
from .parse_schedule import parse_schedule
from .reader import ReadError, read_document
from .scheduler import KIND_LABELS, options_for, plan_day, teachers_with_lessons
from .version import __version__

STATUSES = ["Okulda", "Raporlu", "İzinli", "Görevli", "Sevkli", "Kurs / Seminer", "Diğer…"]
OTHER = "Diğer…"
FILE_FILTER = "Belgeler (*.pdf *.xlsx *.xlsm *.csv);;PDF (*.pdf);;Excel (*.xlsx *.xlsm)"


def _item(text, editable=False):
    it = QTableWidgetItem("" if text is None else str(text))
    if not editable:
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


def _qdate(iso):
    return QDate.fromString(iso, "yyyy-MM-dd")


def _iso(qdate):
    return qdate.toString("yyyy-MM-dd")


def _info(parent, text, title="Bilgi"):
    QMessageBox.information(parent, title, text)


def _ask(parent, text, title="Onay"):
    return QMessageBox.question(parent, title, text) == QMessageBox.Yes


def _stretch(table, *cols):
    table.setAlternatingRowColors(True)
    table.verticalHeader().setDefaultSectionSize(34)
    table.setShowGrid(False)
    h = table.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeToContents)
    for c in cols:
        h.setSectionResizeMode(c, QHeaderView.Stretch)


class Worker(QThread):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, fn, *args, with_progress=False):
        super().__init__()
        self.fn, self.args, self.with_progress = fn, args, with_progress

    def run(self):
        try:
            if self.with_progress:
                res = self.fn(*self.args, progress=lambda d, t: self.progress.emit(d, t))
            else:
                res = self.fn(*self.args)
            self.done.emit(res)
        except Exception as e:  # noqa: BLE001 - kullanıcıya gösterilecek
            self.failed.emit(str(e))


class WeekGrid(QTableWidget):
    """Bir öğretmenin haftalık programı (satır: saat, sütun: gün)."""

    def __init__(self, hours=8, editable=False):
        super().__init__(hours, 5)
        self.editable = editable
        self.setHorizontalHeaderLabels(DAYS)
        self.setVerticalHeaderLabels([f"{h}. ders" for h in range(1, hours + 1)])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setWordWrap(True)

    def load(self, slots, hours=None):
        hours = max(hours or 8, max((h for _, h in slots), default=0))
        self.clearContents()
        self.setRowCount(hours)
        self.setVerticalHeaderLabels([f"{h}. ders" for h in range(1, hours + 1)])
        for (d, h), info in slots.items():
            if 0 <= d < 5 and h >= 1:
                it = _item(info, self.editable)
                it.setBackground(GREEN)
                self.setItem(h - 1, d, it)
        for r in range(self.rowCount()):
            for c in range(5):
                if not self.item(r, c):
                    self.setItem(r, c, _item("", self.editable))

    def slots(self):
        out = {}
        for r in range(self.rowCount()):
            for c in range(5):
                it = self.item(r, c)
                if it and it.text().strip():
                    out[(c, r + 1)] = it.text().strip()
        return out


# ---------------------------------------------------------------- diyaloglar

class ScheduleReviewDialog(QDialog):
    """Okunan ders programını kaydetmeden önce gösterir; isim düzeltme/birleştirme yapılabilir."""

    def __init__(self, parent, result, source, valid_from):
        super().__init__(parent)
        self.setWindowTitle("Ders programı önizleme — kontrol edip kaydedin")
        self.resize(1100, 700)
        self.result = result
        self.names = sorted(result.teachers, key=normalize)

        self.table = QTableWidget(len(self.names), 3)
        self.table.setHorizontalHeaderLabels(["Al", "Öğretmen (düzeltilebilir)", "Ders"])
        for r, n in enumerate(self.names):
            chk = _item("")
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Checked)
            self.table.setItem(r, 0, chk)
            it = _item(n, editable=True)
            if n.startswith("Bilinmeyen"):
                it.setBackground(RED)
            self.table.setItem(r, 1, it)
            self.table.setItem(r, 2, _item(len(result.teachers[n])))
        _stretch(self.table, 1)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.currentCellChanged.connect(self._show)

        self.grid = WeekGrid(result.max_hour)
        self.date = QDateEdit(_qdate(valid_from))
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd.MM.yyyy")

        warn = QPlainTextEdit("\n".join(result.warnings) or "Uyarı yok.")
        warn.setReadOnly(True)
        warn.setMaximumHeight(110)
        layouts = ", ".join(sorted(set(result.layouts))) or "—"

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.addWidget(QLabel(f"<b>{len(self.names)} öğretmen bulundu.</b> Algılanan yerleşim: "
                            f"{layouts}<br>Yanlış okunan isimleri çift tıklayıp düzeltin. Aynı "
                            "ada çevrilen satırlar birleştirilir."))
        lv.addWidget(self.table)
        split = QSplitter()
        split.addWidget(left)
        split.addWidget(self.grid)
        split.setSizes([420, 680])

        form = QFormLayout()
        form.addRow("Program şu tarihten itibaren geçerli:", self.date)
        form.addRow(QLabel(f"Kaynak: {os.path.basename(source)}"))
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Kaydet")
        buttons.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        v = QVBoxLayout(self)
        v.addWidget(split, 1)
        v.addWidget(QLabel("Uyarılar:"))
        v.addWidget(warn)
        v.addLayout(form)
        v.addWidget(buttons)
        if self.names:
            self.table.selectRow(0)
            self._show(0, 0, -1, -1)

    def _show(self, row, *_):
        if 0 <= row < len(self.names):
            self.grid.load(self.result.teachers[self.names[row]], self.result.max_hour)

    def teachers(self):
        out = {}
        for r, orig in enumerate(self.names):
            if self.table.item(r, 0).checkState() != Qt.Checked:
                continue
            name = clean_name(self.table.item(r, 1).text()) or orig
            slots = out.setdefault(name, {})
            for k, v in self.result.teachers[orig].items():
                slots[k] = f"{slots[k]} + {v}" if k in slots and slots[k] != v else v
        return out

    def valid_from(self):
        return _iso(self.date.date())


SCHOOL_KEYS = [("school", "Okul adı", "Ör. Atatürk Anadolu Lisesi"),
               ("school_city", "İl / İlçe", "Ör. BOLU / MERKEZ"),
               ("principal", "Okul müdürü", "Ad Soyad"),
               ("vice_principal", "Müdür yardımcısı", "Ad Soyad (çizelgeyi düzenleyen)")]


def logo_path():
    return os.path.join(data_dir(), "logo.png")


class SchoolDialog(QDialog):
    """Okul adı, yöneticiler ve logo: çıktılarda ve sol menüde kullanılır."""

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Okul bilgileri")
        self.resize(560, 420)
        form = QFormLayout()
        self.fields = {}
        for key, label, hint in SCHOOL_KEYS:
            e = QLineEdit(db.get_setting(key, ""))
            e.setPlaceholderText(hint)
            self.fields[key] = e
            form.addRow(label + ":", e)
        self.logo = QLabel()
        self.logo.setFixedSize(96, 96)
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setStyleSheet("border:1px dashed #94a3b8; border-radius:8px")
        self.new_logo = None
        self.remove_logo = False
        self._show_logo(logo_path() if os.path.exists(logo_path()) else None)
        pick = QPushButton("Logo seç…")
        pick.clicked.connect(self._pick)
        clear = QPushButton("Logoyu kaldır")
        clear.clicked.connect(self._clear)
        lh = QHBoxLayout()
        lh.addWidget(self.logo)
        lv = QVBoxLayout()
        lv.addWidget(pick)
        lv.addWidget(clear)
        lv.addStretch()
        lh.addLayout(lv)
        lh.addStretch()
        form.addRow("Okul logosu:", lh)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Kaydet")
        variant(buttons.button(QDialogButtonBox.Save), "primary")
        buttons.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        v = QVBoxLayout(self)
        v.addWidget(page_header("Okul bilgileri",
                                "Bu bilgiler yazdırılan çizelgede ve programın sol üst köşesinde görünür."))
        v.addLayout(form)
        v.addStretch()
        v.addWidget(buttons)

    def _show_logo(self, path):
        pm = QPixmap(path) if path else QPixmap()
        if pm.isNull():
            self.logo.setText("Logo yok")
        else:
            self.logo.setPixmap(pm.scaled(88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(self, "Logo seç", "",
                                              "Resim (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            self.new_logo, self.remove_logo = path, False
            self._show_logo(path)

    def _clear(self):
        self.new_logo, self.remove_logo = None, True
        self.logo.clear()
        self.logo.setText("Logo yok")

    def _save(self):
        if not self.fields["school"].text().strip():
            _info(self, "Lütfen okul adını yazın.")
            return
        for key, e in self.fields.items():
            self.db.set_setting(key, e.text().strip())
        if self.new_logo:
            img = QImage(self.new_logo)
            if img.isNull():
                _info(self, "Seçilen resim açılamadı.")
                return
            img.scaled(512, 512, Qt.KeepAspectRatio, Qt.SmoothTransformation).save(logo_path())
        elif self.remove_logo and os.path.exists(logo_path()):
            os.remove(logo_path())
        self.accept()


class DutyEditDialog(QDialog):
    """Nöbet çizelgesini kaydetmeden önce gösterir/düzenler."""

    def __init__(self, parent, entries, teachers, month, unmatched=(), warnings=()):
        super().__init__(parent)
        self.setWindowTitle("Nöbet çizelgesi — kontrol edip kaydedin")
        self.resize(900, 650)
        self.teachers = sorted(teachers, key=normalize)
        self.matcher = NameMatcher(self.teachers)

        self.month = QDateEdit(_qdate(month + "-01"))
        self.month.setDisplayFormat("MMMM yyyy")
        self.month.setCalendarPopup(True)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Gün", "Tarih (isteğe bağlı)", "Öğretmen", "Nöbet yeri"])
        _stretch(self.table, 2, 3)
        for e in sorted(entries, key=lambda e: (e.date or "", e.weekday, e.place, e.teacher)):
            self._add_row(e)

        add = QPushButton("Satır ekle")
        add.clicked.connect(lambda: self._add_row(DutyEntry(0, "", "")))
        rem = QPushButton("Seçili satırları sil")
        rem.clicked.connect(self._remove)
        hb = QHBoxLayout()
        hb.addWidget(add)
        hb.addWidget(rem)
        hb.addStretch()

        msgs = list(warnings)
        if unmatched:
            msgs.append("Ders programında bulunamayan isimler (eklenmedi): " + ", ".join(unmatched))
        info = QLabel("\n".join(msgs) or "Tüm isimler ders programıyla eşleşti.")
        info.setWordWrap(True)
        if msgs:
            info.setStyleSheet("color:#a05a00")

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Kaydet")
        buttons.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Çizelge şu aydan itibaren geçerli:", self.month)
        v = QVBoxLayout(self)
        v.addLayout(form)
        v.addWidget(QLabel("Tarih sütunu boşsa çizelge her hafta o gün için geçerlidir."))
        v.addWidget(self.table, 1)
        v.addLayout(hb)
        v.addWidget(info)
        v.addWidget(buttons)

    def _add_row(self, e):
        r = self.table.rowCount()
        self.table.insertRow(r)
        day = QComboBox()
        day.addItems(DAYS)
        day.setCurrentIndex(e.weekday)
        self.table.setCellWidget(r, 0, day)
        self.table.setItem(r, 1, _item(e.date and _qdate(e.date).toString("dd.MM.yyyy"), True))
        who = QComboBox()
        who.setEditable(True)
        who.addItems(self.teachers)
        who.setCurrentText(e.teacher)
        comp = QCompleter(self.teachers)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        who.setCompleter(comp)
        self.table.setCellWidget(r, 2, who)
        self.table.setItem(r, 3, _item(e.place, True))
        if e.teacher and e.teacher not in self.teachers:
            who.setStyleSheet("background:#ffd6d6")
            who.setToolTip("Ders programında yok: bu öğretmenin hiç dersi yokmuş gibi "
                           "davranılır. Yanlış okunduysa düzeltin ya da satırı silin.")

    def _remove(self):
        for r in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(r)

    def _accept(self):
        bad = []
        for r in range(self.table.rowCount()):
            name = self.table.cellWidget(r, 2).currentText().strip()
            if name and name not in self.teachers and not self.matcher.match(name):
                bad.append(name)
        if bad and not _ask(self, "Şu isimler ders programında yok:\n" + "\n".join(bad) +
                            "\n\nYine de kaydedilsin mi? (Bu öğretmenlerin dersi olmadığı varsayılır)"):
            return
        self.accept()

    def entries(self):
        out = []
        for r in range(self.table.rowCount()):
            name = self.table.cellWidget(r, 2).currentText().strip()
            if not name:
                continue
            name = name if name in self.teachers else (self.matcher.match(name) or clean_name(name))
            wd = self.table.cellWidget(r, 0).currentIndex()
            raw = self.table.item(r, 1).text().strip() if self.table.item(r, 1) else ""
            date = None
            if raw:
                q = QDate.fromString(raw, "dd.MM.yyyy")
                if q.isValid():
                    date = _iso(q)
                    wd = min(q.dayOfWeek() - 1, 4)
            place = self.table.item(r, 3).text().strip() if self.table.item(r, 3) else ""
            out.append(DutyEntry(wd, name, place, date))
        return out

    def month_key(self):
        return self.month.date().toString("yyyy-MM")


# ---------------------------------------------------------------- sekmeler

class DailyTab(QWidget):
    """Kademeli görevlendirme: 1) tarih + gelmeyenler  2) boş dersler + nöbetçiler
    3) sonuç (değiştir, yazdır). Her adım tam sayfadır."""

    def __init__(self, win):
        super().__init__()
        self.win, self.db = win, win.db
        self.plan = None
        self.schedule = {}
        self.duty = []
        self.admins = set()
        self.row_index = {}

        self.stepbar = theme.StepBar(["Gelmeyen öğretmenleri seçin", "Boş dersler ve nöbetçiler",
                                      "Görevlendirme"])
        self.steps = QStackedWidget()

        # ---------- Adım 1: tarih ve o gün dersi olan öğretmenler
        self.date = QDateEdit(_qdate(_next_school_day(dt.date.today()).isoformat()))
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("d MMMM yyyy, dddd")
        self.date.setMinimumHeight(40)
        self.date.setMinimumWidth(280)
        self.date.setStyleSheet("font-size:12pt; font-weight:600")
        self.date.dateChanged.connect(self.refresh)
        prev_b, next_b = QPushButton("◀"), QPushButton("▶")
        for btn in (prev_b, next_b):
            btn.setFixedSize(40, 40)
            btn.setStyleSheet("padding:0px; font-size:11pt")
            btn.setCursor(Qt.PointingHandCursor)
        prev_b.clicked.connect(lambda: self._shift(-1))
        next_b.clicked.connect(lambda: self._shift(1))
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("🔍  Öğretmen ara…")
        self.filter.setMinimumHeight(38)
        self.filter.textChanged.connect(self._filter)
        top = QHBoxLayout()
        top.addWidget(QLabel("<b>Tarih</b>"))
        top.addWidget(prev_b)
        top.addWidget(self.date)
        top.addWidget(next_b)
        top.addSpacing(16)
        top.addWidget(self.filter, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.saved_bar = QFrame()
        self.saved_bar.setObjectName("hint")
        sb = QHBoxLayout(self.saved_bar)
        sb.setContentsMargins(14, 8, 8, 8)
        sb.addWidget(QLabel("✅ Bu gün için kayıtlı bir görevlendirme var."), 1)
        show_saved = variant(QPushButton("Görevlendirmeyi göster"), "primary")
        show_saved.clicked.connect(lambda: self.go(2))
        sb.addWidget(show_saved)
        self.people = QTableWidget(0, 3)
        self.people.setHorizontalHeaderLabels(["O gün dersi olan öğretmenler", "Bugünkü dersleri",
                                               "Durum"])
        _stretch(self.people, 0)
        self.people.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.people.setColumnWidth(2, 200)
        self.people.verticalHeader().hide()
        self.people.verticalHeader().setDefaultSectionSize(40)
        self.people.setSelectionMode(QAbstractItemView.NoSelection)
        self.people.setFocusPolicy(Qt.NoFocus)
        self.people.setMinimumHeight(170)
        self.next1 = variant(QPushButton("Devam  →"), "primary")
        self.next1.setMinimumHeight(46)
        self.next1.setStyleSheet("font-size:12pt")
        self.next1.clicked.connect(lambda: self.go(1))
        self.picked = QLabel()
        self.picked.setObjectName("subtitle")
        self.picked.setWordWrap(True)
        f1 = QHBoxLayout()
        f1.addWidget(self.picked, 1)
        f1.addWidget(self.next1)
        p1 = QWidget()
        v1 = QVBoxLayout(p1)
        v1.setContentsMargins(0, 0, 0, 0)
        v1.addLayout(top)
        v1.addWidget(self.status)
        v1.addWidget(self.saved_bar)
        hint = QLabel("Gelmeyen öğretmenin satırında <b>Durum</b>u <b>Raporlu, İzinli, Görevli…</b> "
                      "yapın, sonra <b>Devam</b>'a basın.")
        hint.setObjectName("subtitle")
        v1.addWidget(hint)
        v1.addWidget(self.people, 1)
        v1.addLayout(f1)

        # ---------- Adım 2: boş kalan dersler ve nöbetçiler
        self.gaps = QTableWidget(0, 3)
        self.gaps.setHorizontalHeaderLabels(["Saat", "Sınıf", "Ders"])
        self.dutyt = QTableWidget(0, 2)
        self.dutyt.setHorizontalHeaderLabels(["Nöbetçi öğretmen", "Boş olduğu ders saatleri"])
        for t, stretch_col in ((self.gaps, 2), (self.dutyt, 1)):
            _stretch(t, stretch_col)
            t.setMinimumHeight(150)
            t.verticalHeader().hide()
            t.verticalHeader().setDefaultSectionSize(38)
            t.setSelectionMode(QAbstractItemView.NoSelection)
            t.setFocusPolicy(Qt.NoFocus)
        self.gaps_box = QGroupBox("Gelmeyen öğretmenlerin dersleri")
        QVBoxLayout(self.gaps_box).addWidget(self.gaps)
        self.duty_box = QGroupBox("Bugünün nöbetçileri")
        QVBoxLayout(self.duty_box).addWidget(self.dutyt)
        g2 = QHBoxLayout()
        g2.setSpacing(14)
        g2.addWidget(self.gaps_box, 1)
        g2.addWidget(self.duty_box, 1)
        back2 = QPushButton("←  Geri")
        back2.setMinimumHeight(46)
        back2.clicked.connect(lambda: self.go(0))
        self.run_btn = variant(QPushButton("Görevlendir  ▶"), "primary")
        self.run_btn.setMinimumHeight(46)
        self.run_btn.setStyleSheet("font-size:12pt")
        self.run_btn.clicked.connect(lambda: self.run())
        f2 = QHBoxLayout()
        f2.addWidget(back2)
        info2 = QLabel("Program, o saatte dersi olmayan nöbetçilerden bu ay en az derse girmiş "
                       "olanı seçer; boş nöbetçi yoksa diğer boş öğretmenlerden seçer.")
        info2.setObjectName("subtitle")
        info2.setWordWrap(True)
        f2.addWidget(info2, 1)
        f2.addWidget(self.run_btn)
        p2 = QWidget()
        v2 = QVBoxLayout(p2)
        v2.setContentsMargins(0, 0, 0, 0)
        v2.addLayout(g2, 1)
        v2.addLayout(f2)

        # ---------- Adım 3: sonuç
        self.result = QTableWidget(0, 4)
        self.result.setHorizontalHeaderLabels(["Saat", "Sınıf", "Ders", "Derse girecek öğretmen"])
        _stretch(self.result, 3)
        self.result.setAlternatingRowColors(False)
        self.result.verticalHeader().hide()
        self.result.verticalHeader().setDefaultSectionSize(42)
        self.result.setSelectionMode(QAbstractItemView.NoSelection)
        self.result.setFocusPolicy(Qt.NoFocus)
        self.result.setMinimumHeight(170)
        self.summary = QLabel()
        self.summary.setObjectName("subtitle")
        self.summary.setWordWrap(True)
        back3 = QPushButton("←  Geri")
        back3.clicked.connect(lambda: self.go(1))
        prt = variant(QPushButton("🖨  Yazdır"), "primary")
        prt.clicked.connect(self.print_)
        xlsx = QPushButton("Excel")
        xlsx.clicked.connect(self.to_excel)
        new = QPushButton("Yeni görevlendirme")
        new.clicked.connect(lambda: self.go(0))
        delete = variant(QPushButton("Bu günün görevlendirmesini sil"), "danger")
        delete.clicked.connect(self.delete)
        f3 = QHBoxLayout()
        for btn in (back3, prt, xlsx, new):
            btn.setMinimumHeight(40)
            f3.addWidget(btn)
        f3.addStretch()
        f3.addWidget(delete)
        hint3 = QLabel("Değiştirmek istediğiniz satırda <b>Derse girecek öğretmen</b> kutusundan "
                       "başka birini seçebilirsiniz; değişiklik hemen kaydedilir.")
        hint3.setObjectName("subtitle")
        p3 = QWidget()
        v3 = QVBoxLayout(p3)
        v3.setContentsMargins(0, 0, 0, 0)
        v3.addWidget(hint3)
        v3.addWidget(self.result, 1)
        v3.addWidget(self.summary)
        v3.addLayout(f3)

        for page in (p1, p2, p3):
            self.steps.addWidget(page)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        v.addWidget(page_header("3  Görevlendirme"))
        v.addWidget(self._build_setup())
        v.addWidget(self.stepbar)
        v.addWidget(self.steps, 1)
        self.refresh()

    def go(self, index):
        if index >= 1 and not self.absences():
            _info(self, "Önce gelmeyen öğretmenin durumunu seçin (Raporlu, İzinli, Görevli…).")
            return
        if index == 2 and not self.plan:
            self.run()
            return
        if index == 1:
            self._sections()
        self.steps.setCurrentIndex(index)
        self.stepbar.set(index)

    def _build_setup(self):
        """Ders programı veya nöbet çizelgesi yoksa gösterilen 'Başlarken' bölümü."""
        self.setup = QFrame()
        self.setup.setObjectName("hint")
        self.step0 = variant(QPushButton(), "step")
        self.step1 = variant(QPushButton(), "step")
        self.step2 = variant(QPushButton(), "step")
        self.step0.clicked.connect(lambda: (self.win.edit_school(), self.refresh()))
        self.step1.clicked.connect(lambda: (self.win.sched.load_file(), self.refresh()))
        self.step2.clicked.connect(lambda: (self.win.duty.load_file(), self.refresh()))
        manual = QLabel("Belgeniz okunamazsa: <b>Ders Programı</b> bölümünde <i>Öğretmen ekle</i> "
                        "ile, <b>Nöbet Çizelgesi</b> bölümünde <i>Elle oluştur / düzenle</i> "
                        "ile elle girebilirsiniz.")
        manual.setWordWrap(True)
        title = QLabel("<b style='font-size:12pt'>👋 Hoş geldiniz!</b> — Programı kullanmaya "
                       "başlamak için bu üç adımı sırayla tamamlayın:")
        lay = QVBoxLayout(self.setup)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.addWidget(title)
        h = QHBoxLayout()
        for b in (self.step0, self.step1, self.step2):
            h.addWidget(b)
        lay.addLayout(h)
        lay.addWidget(manual)
        return self.setup

    def _update_setup(self, has_schedule, has_duty):
        has_school = bool(self.db.get_setting("school", ""))
        self.step0.setText(("✅  " if has_school else "1️⃣  ") + "Okul bilgilerini girin\n"
                           "      okul adı, yöneticiler, logo")
        self.step1.setText(("✅  " if has_schedule else "2️⃣  ") + "Ders programını yükleyin\n"
                           "      PDF veya Excel")
        self.step2.setText(("✅  " if has_duty else "3️⃣  ") + "Nöbet çizelgesini yükleyin\n"
                           "      bu ayın çizelgesi")
        self.step2.setEnabled(has_schedule)
        self.setup.setVisible(not (has_school and has_schedule and has_duty))

    def _shift(self, n):
        d = self.date.date().addDays(n)
        while d.dayOfWeek() > 5:
            d = d.addDays(n)
        self.date.setDate(d)

    def date_iso(self):
        return _iso(self.date.date())

    def refresh(self):
        date = self.date_iso()
        wd = self.date.date().dayOfWeek() - 1
        self.plan = None
        self._update_setup(bool(self.db.schedule_versions()), bool(self.db.duty_months()))
        self.win.update_brand()
        self.people.setRowCount(0)
        self.saved_bar.hide()
        self.steps.setCurrentIndex(0)
        self.stepbar.set(0)
        if wd > 4:
            self.schedule, self.duty = {}, []
            self.status.setText("Hafta sonu — okul yok.")
            self._sections()
            return
        vid = self.db.schedule_version_for(date)
        self.schedule = self.db.schedule(vid) if vid else {}
        duty, month = self.db.duty_for(date)
        self.admins = self.db.admins()
        self.duty = [(t, p) for t, p in duty if t not in self.admins and not is_admin_place(p)]
        msgs = []
        if not self.schedule:
            msgs.append("<span style='color:#dc2626'>Ders programı yüklenmedi.</span>")
        if not month:
            msgs.append("<span style='color:#dc2626'>Nöbet çizelgesi yüklenmedi.</span>")
        elif month != date[:7]:
            msgs.append(f"<span style='color:#dc2626'><b>{export.month_tr(date[:7])} nöbet "
                        f"çizelgesi yüklenmedi!</b> Şimdilik {export.month_tr(month)} çizelgesi "
                        "kullanılıyor — <b>2 Nöbet Çizelgesi</b> bölümünden bu ayınkini "
                        "yükleyin.</span>")
        teaching = sorted(teachers_with_lessons(self.schedule, wd), key=normalize)
        if teaching:
            msgs.append(f"<span style='color:{theme.MUTED}'>Bugün {len(teaching)} öğretmenin dersi "
                        f"var, {len({t for t, _ in self.duty})} nöbetçi.</span>")
        self.status.setText("<br>".join(msgs))

        saved = self.db.assignments(date)
        saved_abs = self.db.absences(date)
        self.people.setRowCount(len(teaching))
        for r, n in enumerate(teaching):
            k = len(self._lessons_today(n))
            it = _item(f"{n}")
            self.people.setItem(r, 0, it)
            self.people.setItem(r, 1, _item(f"{k} ders  ({', '.join(map(str, self._lessons_today(n)))}. saat)"))
            combo = QComboBox()
            combo.addItems(STATUSES)
            if n in saved_abs:
                reason = saved_abs[n]
                if reason not in STATUSES:
                    combo.insertItem(combo.count() - 1, reason)
                combo.setCurrentText(reason)
            combo.currentTextChanged.connect(lambda _t, row=r: self._status_changed(row))
            self.people.setCellWidget(r, 2, combo)
            self._mark(r)
        self._filter(self.filter.text())
        if saved_abs:
            self.run(saved=saved)
            self.saved_bar.show()
            self.steps.setCurrentIndex(0)
            self.stepbar.set(0)
        self._update_picked()

    def _lessons_today(self, teacher):
        wd = self.date.date().dayOfWeek() - 1
        return sorted(h for (d, h) in self.schedule.get(teacher, {}) if d == wd)

    def _status_changed(self, row):
        combo = self.people.cellWidget(row, 2)
        if combo.currentText() == OTHER:
            name = self.people.item(row, 0).text()
            text, ok = QInputDialog.getText(self, "Mazeret", f"{name} için mazereti yazın:")
            text = text.strip()
            combo.blockSignals(True)
            if ok and text:
                if combo.findText(text) < 0:
                    combo.insertItem(combo.count() - 1, text)
                combo.setCurrentText(text)
            else:
                combo.setCurrentText("Okulda")
            combo.blockSignals(False)
        self._mark(row)
        self.plan = None  # seçim değişti: görevlendirme yeniden yapılmalı
        if not self.absences() and self.db.absences(self.date_iso()):
            self.db.delete_day(self.date_iso())
            self.win.write_excel()
        self._update_picked()

    def _mark(self, row):
        combo = self.people.cellWidget(row, 2)
        absent = combo.currentText() != "Okulda"
        combo.setStyleSheet("background:#fde7e7; color:#b91c1c; font-weight:600" if absent else "")
        it = self.people.item(row, 0)
        f = it.font()
        f.setBold(absent)
        it.setFont(f)

    def _filter(self, text):
        key = normalize(text)
        for r in range(self.people.rowCount()):
            self.people.setRowHidden(r, bool(key) and key not in normalize(self.people.item(r, 0).text()))

    def absences(self):
        out = {}
        for r in range(self.people.rowCount()):
            combo = self.people.cellWidget(r, 2)
            s = combo.currentText() if combo else "Okulda"
            if s != "Okulda":
                out[self.people.item(r, 0).text()] = s
        return out

    def _update_picked(self):
        absent = self.absences()
        if absent:
            n = sum(len(self._lessons_today(t)) for t in absent)
            self.picked.setText(f"<b>{len(absent)}</b> gelmeyen öğretmen seçildi: "
                                + ", ".join(f"{t} ({r})" for t, r in absent.items())
                                + f" — <b>{n}</b> ders boş kalıyor.")
        else:
            self.picked.setText("Henüz gelmeyen öğretmen seçilmedi.")
        self.next1.setEnabled(bool(absent))

    def _sections(self):
        """2. adımın tablolarını doldurur."""
        absent = self.absences()
        if not absent:
            return
        wd = self.date.date().dayOfWeek() - 1
        # Gelmeyenlerin dersleri: öğretmen başlığı + Saat | Sınıf | Ders
        self.gaps.clearSpans()
        self.gaps.clearContents()
        self.gaps.setRowCount(0)
        need = set()
        total = 0
        for t, reason in absent.items():
            r = self.gaps.rowCount()
            self.gaps.insertRow(r)
            head = _item(f"{t}  ·  {reason}")
            f = head.font()
            f.setBold(True)
            head.setFont(f)
            head.setBackground(BLUE)
            self.gaps.setItem(r, 0, head)
            self.gaps.setSpan(r, 0, 1, 3)
            for h in self._lessons_today(t):
                need.add(h)
                total += 1
                sinif, ders = split_info(self.schedule[t][(wd, h)])
                r = self.gaps.rowCount()
                self.gaps.insertRow(r)
                self.gaps.setItem(r, 0, _item(f"{h}. ders"))
                self.gaps.setItem(r, 1, _item(sinif or "—"))
                self.gaps.setItem(r, 2, _item(ders or "—"))
        # Nöbetçiler: yalnızca boş kalan derslerin saatlerinden hangilerinde boş oldukları
        names = sorted({t for t, _ in self.duty}, key=normalize)
        self.dutyt.clearContents()
        self.dutyt.setRowCount(len(names))
        for r, t in enumerate(names):
            if t in absent:
                txt, fit = "bugün gelmedi", []
            else:
                busy = set(self._lessons_today(t))
                fit = sorted(h for h in need if h not in busy)
                txt = ", ".join(f"{h}. ders" for h in fit) or "boş saati yok"
            self.dutyt.setItem(r, 0, _item(t))
            it = _item(txt)
            if fit:
                f = it.font()
                f.setBold(True)
                it.setFont(f)
                it.setBackground(GREEN)
            self.dutyt.setItem(r, 1, it)
        self.gaps_box.setTitle(f"Gelmeyen öğretmenlerin dersleri — {total} ders boş kalıyor")
        self.duty_box.setTitle(f"Bugünün nöbetçileri — {len(names)} kişi")

    def run(self, saved=None):
        date = self.date_iso()
        if not self.absences():
            _info(self, "Önce soldaki listeden gelmeyen öğretmenin durumunu seçin "
                        "(Raporlu, İzinli, Görevli…).")
            return
        counts = self.db.counts(date[:7], exclude_date=date)
        totals = self.db.total_counts(exclude_date=date)
        cap = int(self.db.get_setting("max_per_day", "0") or 0)
        self.plan = plan_day(date, self.schedule, self.duty, self.absences(), counts, totals, cap,
                             excluded=self.admins)
        if saved:
            by_key = {(h, t): (a, k, n) for h, t, _info_, a, k, n in saved}
            for a in self.plan.assignments:
                if (a.hour, a.absent) in by_key:
                    a.assigned, a.kind, a.note = by_key[(a.hour, a.absent)]
        self._sections()
        if saved:
            self.show_plan()
        else:
            self._store()  # Görevlendir'e basınca hemen istatistiğe işlenir
            self.saved_bar.show()
        self.steps.setCurrentIndex(2)
        self.stepbar.set(2)

    def show_plan(self):
        p = self.plan
        self.result.clearSpans()
        self.result.setRowCount(0)
        self.row_index = {}
        groups = {}
        for i, a in enumerate(p.assignments):
            groups.setdefault(a.absent, []).append(i)
        for absent, idxs in groups.items():
            r = self.result.rowCount()
            self.result.insertRow(r)
            head = _item(f"{absent}   ·   {p.absences.get(absent, '')}   ·   {len(idxs)} ders")
            f = head.font()
            f.setBold(True)
            head.setFont(f)
            head.setBackground(BLUE)
            self.result.setItem(r, 0, head)
            self.result.setSpan(r, 0, 1, 4)
            for i in idxs:
                a = p.assignments[i]
                r = self.result.rowCount()
                self.result.insertRow(r)
                self.row_index[r] = i
                sinif, ders = split_info(a.info)
                self.result.setItem(r, 0, _item(f"{a.hour}. ders"))
                self.result.setItem(r, 1, _item(sinif or "—"))
                self.result.setItem(r, 2, _item(ders or a.info))
                combo = QComboBox()
                combo.addItem("— atanmadı —", None)
                opts = options_for(p, self.schedule, i)
                for t, lab in opts:
                    combo.addItem(t if lab == "nöbetçi" else f"{t}  (nöbetçi değil)", (t, lab))
                if a.assigned and a.assigned not in [t for t, _ in opts]:
                    combo.addItem(a.assigned, (a.assigned, "kayıtlı"))
                idx = next((k for k in range(combo.count())
                            if combo.itemData(k) and combo.itemData(k)[0] == a.assigned), 0)
                combo.setCurrentIndex(idx)
                combo.setToolTip(a.note or "Nöbetçi öğretmen")
                combo.currentIndexChanged.connect(lambda _k, row=i, cb=combo: self._changed(row, cb))
                color = {"bos": YELLOW, "yok": RED}.get(a.kind)
                if color:
                    combo.setStyleSheet("font-weight:600")
                    for c in range(3):
                        self.result.item(r, c).setBackground(color)
                        self.result.item(r, c).setToolTip(a.note)
                self.result.setCellWidget(r, 3, combo)
        n = len(p.assignments)
        ok = sum(1 for a in p.assignments if a.kind == "nobetci")
        free = sum(1 for a in p.assignments if a.kind == "bos")
        none = sum(1 for a in p.assignments if not a.assigned)
        parts = [f"<b>{n}</b> ders", f"<b>{ok}</b> nöbetçiye verildi"]
        if free:
            parts.append(f"<b style='color:#d97706'>{free}</b> nöbetçi olmayana verildi "
                         "(o saatte boş nöbetçi yoktu — sarı satırlar)")
        if none:
            parts.append(f"<b style='color:#dc2626'>{none}</b> ders için boş öğretmen yok "
                         "(kırmızı satırlar)")
        saved = bool(self.db.assignments(self.date_iso()))
        parts.append("✅ kaydedildi" if saved else "henüz kaydedilmedi")
        self.summary.setText("  ·  ".join(parts))

    def _changed(self, row, combo):
        a = self.plan.assignments[row]
        data = combo.currentData()
        if not data:
            a.assigned, a.kind = None, "yok"
            a.note = "Elle boş bırakıldı."
        else:
            t, lab = data
            a.assigned = t
            if lab == "nöbetçi":
                a.kind, a.note = "nobetci", "Elle seçildi."
            else:
                a.kind = "bos"
                a.note = f"⚠ Elle seçildi; {t} nöbetçi değil ({lab})."
        self._store()  # elle yapılan değişiklik de hemen kaydedilir

    def save(self):
        if not self.plan:
            _info(self, "Kaydedilecek görevlendirme yok.")
            return
        self._store()
        self.refresh()

    def _store(self):
        """Günün görevlendirmesini istatistiğe kaydeder (aynı gün tekrar kaydedilirse yenilenir)."""
        self.db.save_day(self.date_iso(), self.plan.absences, self.plan.assignments)
        self.win.statusBar().showMessage(
            "✅ Görevlendirme istatistiğe kaydedildi. Sonraki görevlendirmeler bu kayda göre "
            "adil dağıtılır.", 6000)
        self.win.write_excel()
        if self.plan:
            self.show_plan()

    def delete(self):
        if _ask(self, "Bu günün devamsızlık ve görevlendirme kaydı silinsin mi?"):
            self.db.delete_day(self.date_iso())
            self.win.write_excel()
            self.refresh()

    def to_excel(self):
        if not self.plan:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel olarak kaydet", f"gorevlendirme_{self.date_iso()}.xlsx", "Excel (*.xlsx)")
        if path:
            self._store()
            export.save_day_xlsx(path, self.plan, self.win.school_header())
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def print_(self):
        if not self.plan:
            _info(self, "Önce gelmeyen öğretmenleri seçip 'Görevlendirmeyi Oluştur'a basın.")
            return
        from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
        self._store()
        doc = QTextDocument()
        has_logo = os.path.exists(logo_path())
        if has_logo:
            doc.addResource(QTextDocument.ImageResource, QUrl("logo"), QImage(logo_path()))
        doc.setHtml(export.day_html(self.plan, self.win.school_info(), has_logo))
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageOrientation(QPageLayout.Portrait)
        dlg = QPrintPreviewDialog(printer, self)
        dlg.setWindowTitle("Baskı önizleme — PDF için yazıcı olarak 'Microsoft Print to PDF' seçin")
        dlg.resize(1100, 800)
        dlg.paintRequested.connect(doc.print_)
        dlg.exec()


class ScheduleTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win, self.db = win, win.db
        self.version = None
        self.data = {}

        self.versions = QTableWidget(0, 4)
        self.versions.setHorizontalHeaderLabels(["Geçerlilik", "Dosya", "Öğretmen", "Yüklenme"])
        _stretch(self.versions, 1)
        self.versions.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.versions.setSelectionMode(QAbstractItemView.SingleSelection)
        self.versions.itemSelectionChanged.connect(self._select_version)
        load = variant(QPushButton("📄  Yeni ders programı yükle (PDF / Excel)"), "primary")
        load.clicked.connect(self.load_file)
        rem = variant(QPushButton("Seçili sürümü sil"), "danger")
        rem.clicked.connect(self.delete_version)

        self.teachers = QListWidget()
        self.teachers.setObjectName("list")
        self.teachers.currentTextChanged.connect(self._select_teacher)
        add_t = QPushButton("Öğretmen ekle")
        add_t.clicked.connect(self.add_teacher)
        ren_t = QPushButton("Yeniden adlandır")
        ren_t.clicked.connect(self.rename_teacher)
        del_t = QPushButton("Sil")
        del_t.clicked.connect(self.delete_teacher)

        self.grid = WeekGrid(8, editable=True)
        save = QPushButton("Bu öğretmenin programını kaydet")
        save.clicked.connect(self.save_teacher)

        # Kademe 1: yüklü programlar
        load.setMinimumHeight(46)
        load.setStyleSheet("font-size:11pt")
        view = QPushButton("👁  Programı görüntüle / düzenle")
        view.setMinimumHeight(46)
        view.clicked.connect(self.open_view)
        rem.setMinimumHeight(46)
        self.versions.setMinimumHeight(130)
        card1 = QGroupBox("Yüklü ders programları")
        c1 = QVBoxLayout(card1)
        hint = QLabel("Program değiştiğinde yeni dosyayı yükleyip <b>geçerlilik tarihini</b> girin. "
                      "Önceki günler eski programla, sonraki günler yeni programla hesaplanır.")
        hint.setWordWrap(True)
        c1.addWidget(hint)
        c1.addWidget(self.versions, 1)
        bh = QHBoxLayout()
        bh.addWidget(load, 1)
        bh.addWidget(view, 1)
        bh.addWidget(rem)
        c1.addLayout(bh)
        p1 = QWidget()
        v1 = QVBoxLayout(p1)
        v1.setContentsMargins(0, 0, 0, 0)
        v1.addWidget(card1, 1)

        # Kademe 2: öğretmenler ve haftalık program (tam sayfa)
        back = QPushButton("←  Geri")
        back.clicked.connect(lambda: self.steps.setCurrentIndex(0))
        self.view_title = QLabel()
        self.view_title.setStyleSheet("font-size:12pt; font-weight:700")
        th = QHBoxLayout()
        th.addWidget(back)
        th.addWidget(self.view_title, 1)
        self.teachers.setFixedWidth(260)
        tl = QVBoxLayout()
        tl.addWidget(QLabel("<b>Öğretmenler</b>"))
        tl.addWidget(self.teachers, 1)
        for b in (add_t, ren_t, del_t):
            tl.addWidget(b)
        gr = QVBoxLayout()
        gr.addWidget(QLabel("<b>Haftalık program</b> — hücreye çift tıklayıp düzenleyebilirsiniz"))
        gr.addWidget(self.grid, 1)
        gr.addWidget(save)
        body = QHBoxLayout()
        body.addLayout(tl)
        body.addLayout(gr, 1)
        p2 = QWidget()
        v2 = QVBoxLayout(p2)
        v2.setContentsMargins(0, 0, 0, 0)
        v2.addLayout(th)
        v2.addLayout(body, 1)

        self.steps = QStackedWidget()
        self.steps.addWidget(p1)
        self.steps.addWidget(p2)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(page_header("1  Ders Programı",
                                "Okulun ders programını PDF veya Excel olarak yükleyin; okunanları "
                                "kontrol edip gerekirse düzeltin."))
        v.addWidget(self.steps, 1)
        self.refresh()

    def open_view(self):
        if not self.version:
            self.refresh()
        if not self.version:
            _info(self, "Önce ders programını yükleyin.")
            return
        r = self.versions.currentRow()
        if r >= 0:
            self.view_title.setText(f"Ders programı — {self.versions.item(r, 0).text()} "
                                    f"tarihinden itibaren ({self.versions.item(r, 1).text()})")
        self.steps.setCurrentIndex(1)

    def refresh(self, select=None):
        rows = self.db.schedule_versions()
        self.versions.blockSignals(True)
        self.versions.setRowCount(len(rows))
        for r, (vid, vf, src, imp, n) in enumerate(rows):
            self.versions.setItem(r, 0, _item(_qdate(vf).toString("dd.MM.yyyy")))
            self.versions.item(r, 0).setData(Qt.UserRole, vid)
            self.versions.setItem(r, 1, _item(src))
            self.versions.setItem(r, 2, _item(n))
            self.versions.setItem(r, 3, _item((imp or "").replace("T", " ")))
        self.versions.blockSignals(False)
        if rows:
            idx = next((r for r, row in enumerate(rows) if row[0] == select), 0)
            self.versions.selectRow(idx)
            self._select_version()
        else:
            self.version, self.data = None, {}
            self.teachers.clear()
            self.grid.load({})

    def _select_version(self):
        r = self.versions.currentRow()
        if r < 0:
            return
        self.version = self.versions.item(r, 0).data(Qt.UserRole)
        self.data = self.db.schedule(self.version)
        cur = self.teachers.currentItem().text() if self.teachers.currentItem() else None
        self.teachers.clear()
        self.teachers.addItems(sorted(self.data, key=normalize))
        items = self.teachers.findItems(cur or "", Qt.MatchExactly) if cur else []
        self.teachers.setCurrentRow(self.teachers.row(items[0]) if items else 0)

    def _select_teacher(self, name):
        self.grid.load(self.data.get(name, {}))

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ders programı seç", "", FILE_FILTER)
        if not path:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            res = parse_schedule(read_document(path), self.db.all_teachers())
        except ReadError as e:
            QMessageBox.warning(self, "Okunamadı", str(e))
            return
        finally:
            QApplication.restoreOverrideCursor()
        if not res.teachers:
            QMessageBox.warning(self, "Program bulunamadı", "\n".join(res.warnings))
            return
        dlg = ScheduleReviewDialog(self, res, path, dt.date.today().isoformat())
        if dlg.exec() == QDialog.Accepted:
            vid = self.db.save_schedule(dlg.teachers(), dlg.valid_from(), os.path.basename(path))
            self.refresh(select=vid)
            self.win.changed()
            self.win.next_step("Ders programı kaydedildi.")

    def delete_version(self):
        if self.version and _ask(self, "Seçili program sürümü silinsin mi?"):
            self.db.delete_schedule_version(self.version)
            self.refresh()
            self.win.changed()

    def _store(self):
        self.db.replace_schedule_entries(self.version, self.data)
        self.win.changed()

    def save_teacher(self):
        it = self.teachers.currentItem()
        if not it or not self.version:
            return
        self.data[it.text()] = self.grid.slots()
        self._store()
        self.win.statusBar().showMessage(f"{it.text()} programı kaydedildi.", 3000)

    def _ask_name(self, title, text=""):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        edit = QLineEdit(text)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Ad Soyad:"))
        v.addWidget(edit)
        v.addWidget(bb)
        return clean_name(edit.text()) if dlg.exec() == QDialog.Accepted else None

    def add_teacher(self):
        if not self.version:
            self.version = self.db.save_schedule({}, dt.date.today().isoformat(), "elle")
        name = self._ask_name("Öğretmen ekle")
        if name and name not in self.data:
            self.data[name] = {}
            self._store()
            self.refresh(select=self.version)
            self.teachers.setCurrentItem(self.teachers.findItems(name, Qt.MatchExactly)[0])

    def rename_teacher(self):
        it = self.teachers.currentItem()
        if not it:
            return
        old = it.text()
        name = self._ask_name("Yeniden adlandır", old)
        if name and name != old:
            merged = self.data.pop(old)
            self.data.setdefault(name, {}).update(merged)
            self._store()
            self.refresh(select=self.version)

    def delete_teacher(self):
        it = self.teachers.currentItem()
        if it and _ask(self, f"{it.text()} bu program sürümünden silinsin mi?"):
            self.data.pop(it.text(), None)
            self._store()
            self.refresh(select=self.version)


class DutyTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win, self.db = win, win.db
        self.months = QTableWidget(0, 2)
        self.months.setHorizontalHeaderLabels(["Ay", "Öğretmen"])
        _stretch(self.months, 0)
        self.months.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.months.setSelectionMode(QAbstractItemView.SingleSelection)
        self.months.itemSelectionChanged.connect(self._show)
        load = variant(QPushButton("📄  Nöbet çizelgesi yükle (PDF / Excel)"), "primary")
        load.clicked.connect(self.load_file)
        manual = QPushButton("Elle oluştur / düzenle")
        manual.clicked.connect(self.edit)
        rem = variant(QPushButton("Seçili ayı sil"), "danger")
        rem.clicked.connect(self.delete)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Hafta"] + DAYS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setWordWrap(True)
        self.dated = QLabel()
        self.dated.setWordWrap(True)

        # Kademe 1: yüklü aylar
        view = QPushButton("👁  Çizelgeyi görüntüle")
        view.clicked.connect(self.open_view)
        for b in (load, view, manual, rem):
            b.setMinimumHeight(46)
        load.setStyleSheet("font-size:11pt")
        self.months.setMinimumHeight(130)
        card1 = QGroupBox("Yüklü nöbet çizelgeleri")
        c1 = QVBoxLayout(card1)
        hint = QLabel("Her ay o ayın çizelgesini yükleyin. Haftalara bölünmüş çizelgeler de okunur.")
        hint.setWordWrap(True)
        c1.addWidget(hint)
        c1.addWidget(self.months, 1)
        bh = QHBoxLayout()
        bh.addWidget(load, 1)
        bh.addWidget(view, 1)
        bh.addWidget(manual)
        bh.addWidget(rem)
        c1.addLayout(bh)
        p1 = QWidget()
        v1 = QVBoxLayout(p1)
        v1.setContentsMargins(0, 0, 0, 0)
        v1.addWidget(card1, 1)

        # Kademe 2: haftalık nöbetçiler (tam sayfa)
        back = QPushButton("←  Geri")
        back.clicked.connect(lambda: self.steps.setCurrentIndex(0))
        self.view_title = QLabel()
        self.view_title.setStyleSheet("font-size:12pt; font-weight:700")
        th = QHBoxLayout()
        th.addWidget(back)
        th.addWidget(self.view_title, 1)
        self.table.setMinimumHeight(220)
        p2 = QWidget()
        v2 = QVBoxLayout(p2)
        v2.setContentsMargins(0, 0, 0, 0)
        v2.addLayout(th)
        v2.addWidget(self.table, 1)
        v2.addWidget(self.dated)

        self.steps = QStackedWidget()
        self.steps.addWidget(p1)
        self.steps.addWidget(p2)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(page_header("2  Nöbet Çizelgesi",
                                "Her ay o ayın çizelgesini yükleyin. İsimler ders programındaki "
                                "öğretmenlerle otomatik eşleştirilir."))
        v.addWidget(self.steps, 1)
        self.refresh()

    def open_view(self):
        if not self.month():
            self.refresh()
        m = self.month()
        if not m:
            _info(self, "Önce nöbet çizelgesini yükleyin.")
            return
        self.view_title.setText(f"{export.month_tr(m)} nöbet çizelgesi")
        self._show()
        self.steps.setCurrentIndex(1)

    def month(self):
        r = self.months.currentRow()
        return self.months.item(r, 0).data(Qt.UserRole) if r >= 0 else None

    def refresh(self, select=None):
        rows = self.db.duty_months()
        self.months.blockSignals(True)
        self.months.setRowCount(len(rows))
        for r, (m, n) in enumerate(rows):
            self.months.setItem(r, 0, _item(export.month_tr(m)))
            self.months.item(r, 0).setData(Qt.UserRole, m)
            self.months.setItem(r, 1, _item(n))
        self.months.blockSignals(False)
        if rows:
            self.months.selectRow(next((r for r, row in enumerate(rows) if row[0] == select), 0))
        self._show()

    def _show(self):
        m = self.month()
        rows = self.db.duty_rows(m) if m else []
        weeks = {}
        for wd, date, t, p in sorted(rows, key=lambda r: (r[1] or "", r[3] or "", r[2])):
            if date:
                d = dt.date.fromisoformat(date)
                key = (d - dt.timedelta(days=d.weekday())).isoformat()
            else:
                key = ""
            weeks.setdefault(key, {i: [] for i in range(5)})[wd].append(
                t + (f"  ({p})" if p else ""))
        self.table.setRowCount(len(weeks))
        self.table.clearContents()
        for r, key in enumerate(sorted(weeks)):
            label = "Her hafta" if not key else _qdate(key).toString("dd.MM") + " haftası"
            self.table.setItem(r, 0, _item(label))
            for d, items in weeks[key].items():
                self.table.setItem(r, d + 1, _item("\n".join(items)))
        self.table.resizeRowsToContents()
        self.dated.setText("İdareciler (N.İDARECİ) hiçbir zaman derse görevlendirilmez."
                           if any(is_admin_place(r[3]) for r in rows) else "")

    def _teachers(self):
        return self.db.all_teachers()

    def load_file(self):
        teachers = self._teachers()
        if not teachers:
            _info(self, "Önce ders programını yükleyin. Nöbet çizelgesindeki isimler "
                        "ders programındaki öğretmenlerle eşleştirilir.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Nöbet çizelgesi seç", "", FILE_FILTER)
        if not path:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            res = parse_duty(read_document(path), teachers)
        except ReadError as e:
            QMessageBox.warning(self, "Okunamadı", str(e))
            return
        finally:
            QApplication.restoreOverrideCursor()
        month = _guess_month(res.entries)
        dlg = DutyEditDialog(self, res.entries, teachers, month, res.unmatched, res.warnings)
        if dlg.exec() == QDialog.Accepted:
            self._save(dlg)

    def edit(self):
        m = self.month() or dt.date.today().strftime("%Y-%m")
        entries = [DutyEntry(wd, t, p, d) for wd, d, t, p in self.db.duty_rows(m)]
        dlg = DutyEditDialog(self, entries, self._teachers(), m)
        if dlg.exec() == QDialog.Accepted:
            self._save(dlg)

    def _save(self, dlg):
        m = dlg.month_key()
        if m in [r[0] for r in self.db.duty_months()] and m != self.month() and \
                not _ask(self, f"{export.month_tr(m)} için kayıtlı çizelge var. Üzerine yazılsın mı?"):
            return
        self.db.save_duty(m, dlg.entries())
        self.refresh(select=m)
        self.win.changed()
        self.win.next_step("Nöbet çizelgesi kaydedildi.")

    def delete(self):
        m = self.month()
        if m and _ask(self, f"{export.month_tr(m)} nöbet çizelgesi silinsin mi?"):
            self.db.delete_duty_month(m)
            self.refresh()
            self.win.changed()


class ReportTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win, self.db = win, win.db
        self.month = QDateEdit(QDate.currentDate())
        self.month.setDisplayFormat("MMMM yyyy")
        self.month.setCalendarPopup(True)
        self.month.dateChanged.connect(self.refresh)
        xlsx = QPushButton("Excel'e aktar")
        xlsx.clicked.connect(self.to_excel)
        top = QHBoxLayout()
        top.addWidget(QLabel("<b>Ay:</b>"))
        top.addWidget(self.month)
        top.addStretch()
        top.addWidget(xlsx)
        self.table = QTableWidget(0, len(export.REPORT_HEADERS))
        self.table.setHorizontalHeaderLabels(export.REPORT_HEADERS)
        _stretch(self.table, 0)
        self.table.setSortingEnabled(True)
        self.info = QLabel()
        self.info.setWordWrap(True)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(page_header("Aylık Rapor",
                                "Kaydedilen günlerdeki görevlendirmeler sayılır. Program, nöbetçiler "
                                "arasında bu ay en az derse girene öncelik vererek sayıları eşitler."))
        v.addLayout(top)
        v.addWidget(self.table, 1)
        v.addWidget(self.info)
        self.rows = []

    def key(self):
        return self.month.date().toString("yyyy-MM")

    def refresh(self):
        m = self.key()
        self.rows = export.report_rows(self.db.counts(m), self.db.duty_days_in_month(m))
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            for c, val in enumerate(row):
                it = QTableWidgetItem()
                it.setData(Qt.DisplayRole, val)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if c == 4 and val:
                    it.setBackground(YELLOW)
                self.table.setItem(r, c, it)
        self.table.setSortingEnabled(True)
        days = self.db.saved_dates(m)
        duty_counts = [row[3] for row in self.rows if row[1]]
        spread = (max(duty_counts) - min(duty_counts)) if duty_counts else 0
        self.info.setText(f"Kayıtlı gün sayısı: {len(days)}. Nöbetçiler arasındaki fark "
                          f"(en çok − en az): {spread}.")

    def to_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "Excel olarak kaydet",
                                              f"aylik_rapor_{self.key()}.xlsx", "Excel (*.xlsx)")
        if path:
            export.save_report_xlsx(path, self.key(), self.rows, self.win.school())
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))


class AdminsDialog(QDialog):
    """Hiç görevlendirilmeyecek idarecileri seçme."""

    def __init__(self, parent, teachers, selected):
        super().__init__(parent)
        self.setWindowTitle("İdareciler")
        self.resize(460, 560)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Öğretmen ara…")
        self.list = QListWidget()
        self.list.setObjectName("list")
        for t in sorted(set(teachers) | set(selected), key=normalize):
            it = QListWidgetItem(t)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if t in selected else Qt.Unchecked)
            self.list.addItem(it)
        self.search.textChanged.connect(self._filter)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Kaydet")
        variant(bb.button(QDialogButtonBox.Save), "primary")
        bb.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v = QVBoxLayout(self)
        v.addWidget(page_header("İdareciler", "İşaretlenen kişilere hiçbir zaman ders "
                                              "görevlendirmesi yapılmaz."))
        v.addWidget(self.search)
        v.addWidget(self.list, 1)
        v.addWidget(bb)

    def _filter(self, text):
        key = normalize(text)
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(key) and key not in normalize(it.text()))

    def selected(self):
        return {self.list.item(i).text() for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.Checked}


class SettingsTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win, self.db = win, win.db

        def card(title):
            g = QGroupBox(title)
            lay = QVBoxLayout(g)
            lay.setSpacing(8)
            return g, lay

        def row(*widgets, stretch_first=True):
            h = QHBoxLayout()
            for i, w in enumerate(widgets):
                h.addWidget(w, 1 if (i == 0 and stretch_first) else 0)
            if not stretch_first:
                h.addStretch()
            return h

        # Okul
        self.school_info = QLabel()
        self.school_info.setWordWrap(True)
        self.school_logo = QLabel()
        self.school_logo.setFixedSize(72, 72)
        self.school_logo.setAlignment(Qt.AlignCenter)
        edit_school = variant(QPushButton("✏  Okul bilgilerini düzenle"), "primary")
        edit_school.clicked.connect(win.edit_school)
        self.refresh_school()
        g0, l0 = card("Okul")
        h0 = QHBoxLayout()
        h0.addWidget(self.school_logo)
        h0.addWidget(self.school_info, 1)
        h0.addWidget(edit_school, 0, Qt.AlignTop)
        l0.addLayout(h0)

        # Görünüm
        self.accent = QComboBox()
        self.accent.addItems(list(theme.ACCENTS))
        self.accent.setCurrentText(self.db.get_setting("theme_accent", "Mor"))
        self.accent.setFixedWidth(180)
        self.dark = QCheckBox("Koyu görünüm")
        self.dark.setChecked(self.db.get_setting("theme_dark", "0") == "1")
        self.accent.currentTextChanged.connect(self._theme_changed)
        self.dark.toggled.connect(self._theme_changed)
        gt, lt = card("Görünüm")
        lt.addLayout(row(QLabel("Tema rengi:"), self.accent, self.dark, stretch_first=False))

        # Dağıtım
        self.cap = QSpinBox()
        self.cap.setRange(0, 8)
        self.cap.setSpecialValueText("Sınırsız")
        self.cap.setFixedWidth(120)
        self.cap.setValue(int(self.db.get_setting("max_per_day", "0") or 0))
        self.cap.valueChanged.connect(lambda v: self.db.set_setting("max_per_day", v))
        g1, l1 = card("Dağıtım kuralları")
        rules = QLabel("Önce o saatte dersi olmayan <b>nöbetçi öğretmenler</b>, bu ay en az derse "
                       "girene öncelik verilerek görevlendirilir. Boş nöbetçi yoksa o saatte dersi "
                       "olmayan <b>diğer öğretmenler</b> görevlendirilir. İdareciler görevlendirilmez.")
        rules.setWordWrap(True)
        l1.addWidget(rules)
        l1.addLayout(row(QLabel("Bir nöbetçiye günde en fazla:"), self.cap, stretch_first=False))

        # İdareciler
        self.admins_label = QLabel()
        self.admins_label.setWordWrap(True)
        edit_admins = QPushButton("İdarecileri düzenle…")
        edit_admins.clicked.connect(self.edit_admins)
        ga, la = card("İdareciler (görevlendirilmez)")
        ha = QHBoxLayout()
        ha.addWidget(self.admins_label, 1)
        ha.addWidget(edit_admins, 0, Qt.AlignTop)
        la.addLayout(ha)
        self.refresh_admins()

        # Excel
        g4, l4 = card("Excel kayıt dosyası")
        hint = QLabel("Her görevlendirmeden sonra tüm kayıtlar bu Excel dosyasına yazılır:")
        hint.setWordWrap(True)
        l4.addWidget(hint)
        self.excel = QLabel(win.excel_path())
        self.excel.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.excel.setWordWrap(True)
        self.excel.setStyleSheet("font-weight:600")
        l4.addWidget(self.excel)
        open_x = QPushButton("Excel dosyasını aç")
        open_x.clicked.connect(self.open_excel)
        move_x = QPushButton("Konumu değiştir…")
        move_x.clicked.connect(self.move_excel)
        l4.addLayout(row(open_x, move_x, stretch_first=False))

        # Güncelleme
        self.upd = QLabel(f"Yüklü sürüm: <b>{__version__}</b>")
        self.upd.setWordWrap(True)
        self.auto = QCheckBox("Program açılırken yeni sürüm var mı diye bak")
        self.auto.setChecked(self.db.get_setting("auto_update", "1") == "1")
        self.auto.toggled.connect(lambda v: self.db.set_setting("auto_update", "1" if v else "0"))
        check = variant(QPushButton("🔄  Güncellemeleri denetle"), "primary")
        check.clicked.connect(lambda: win.check_updates(silent=False))
        g2, l2 = card("Güncelleme")
        h2 = QHBoxLayout()
        info2 = QVBoxLayout()
        info2.addWidget(self.upd)
        info2.addWidget(self.auto)
        h2.addLayout(info2, 1)
        h2.addWidget(check, 0, Qt.AlignVCenter)
        l2.addLayout(h2)

        # Veriler
        folder = QPushButton("Veri klasörünü aç")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(data_dir())))
        backup = QPushButton("Yedek al…")
        backup.clicked.connect(self.backup)
        restore = QPushButton("Yedekten geri yükle…")
        restore.clicked.connect(self.restore)
        reset = variant(QPushButton("Tüm verileri sil, sıfırdan başla…"), "danger")
        reset.clicked.connect(self.reset)
        g3, l3 = card("Veriler")
        dpath = QLabel("Veriler yalnızca bu bilgisayarda tutulur ve güncellemede silinmez.")
        dpath.setWordWrap(True)
        l3.addWidget(dpath)
        l3.addLayout(row(folder, backup, restore, stretch_first=False))
        l3.addLayout(row(reset, stretch_first=False))

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        v.addWidget(page_header("Ayarlar"))
        for g in (g0, gt, g1, ga, g4, g2, g3):
            v.addWidget(g)
        v.addStretch()

    def refresh_admins(self):
        admins = sorted(self.db.admins(), key=normalize)
        self.admins_label.setText(", ".join(admins) if admins else
                                  "Henüz yok. Nöbet çizelgesinde idareci (N.İDARECİ, müdür "
                                  "yardımcısı) olarak geçenler otomatik eklenir.")

    def edit_admins(self):
        dlg = AdminsDialog(self, self.db.all_teachers(), self.db.admins())
        if dlg.exec() == QDialog.Accepted:
            self.db.set_admins(dlg.selected())
            self.refresh_admins()
            self.win.changed()

    def reset(self):
        if not _ask(self, "Ders programı, nöbet çizelgeleri ve TÜM görevlendirme kayıtları "
                          "silinecek. Okul bilgileri ve ayarlar kalacak.\n\nÖnce yedek almak "
                          "isteyebilirsiniz. Silmek istediğinize emin misiniz?", "Sıfırdan başla"):
            return
        self.db.reset_all()
        self.refresh_admins()
        self.win.sched.refresh()
        self.win.duty.refresh()
        self.win.changed()
        self.win.go_first_step()
        _info(self, "Tüm veriler silindi. 1. adımdan, ders programını yükleyerek başlayın.")

    def refresh_school(self):
        info = self.win.school_info()
        lines = [f"<b style='font-size:12pt'>{info['school'] or 'Okul adı girilmedi'}</b>"]
        if info["school_city"]:
            lines.append(info["school_city"])
        if info["principal"]:
            lines.append(f"Okul Müdürü: {info['principal']}")
        if info["vice_principal"]:
            lines.append(f"Müdür Yardımcısı: {info['vice_principal']}")
        self.school_info.setText("<br>".join(lines))
        pm = QPixmap(logo_path()) if os.path.exists(logo_path()) else theme.app_icon().pixmap(64, 64)
        self.school_logo.setPixmap(pm.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _theme_changed(self, *_):
        self.db.set_setting("theme_accent", self.accent.currentText())
        self.db.set_setting("theme_dark", "1" if self.dark.isChecked() else "0")
        QApplication.instance().setStyleSheet(
            theme.build_style(self.accent.currentText(), self.dark.isChecked()))
        self.win.daily.refresh()

    def open_excel(self):
        path = self.win.excel_path()
        if self.win.write_excel() or os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def move_excel(self):
        folder = QFileDialog.getExistingDirectory(self, "Excel kayıt dosyasının klasörü",
                                                  os.path.dirname(self.win.excel_path()))
        if folder:
            self.db.set_setting("excel_path", os.path.join(folder, export.RECORDS_FILE))
            self.excel.setText(self.win.excel_path())
            self.win.write_excel()

    def backup(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Yedek kaydet", f"nobet_yedek_{dt.date.today().isoformat()}.db", "Yedek (*.db)")
        if path:
            self.db.conn.commit()
            shutil.copyfile(self.db.path, path)
            _info(self, "Yedek alındı.")

    def restore(self):
        path, _ = QFileDialog.getOpenFileName(self, "Yedek seç", "", "Yedek (*.db)")
        if path and _ask(self, "Mevcut tüm veriler yedektekiyle değiştirilecek. Devam edilsin mi?"):
            self.db.conn.close()
            shutil.copyfile(path, self.db.path)
            self.win.reopen_db()
            _info(self, "Yedek geri yüklendi.")


# ---------------------------------------------------------------- ana pencere

class MainWindow(QMainWindow):
    def __init__(self, db=None):
        super().__init__()
        self.setWindowTitle(f"Nöbetçi Öğretmen Görevlendirme  v{__version__}")
        self.resize(1440, 860)
        self.db = db or Database()
        self._workers = []
        self._build()
        QTimer.singleShot(800, self.check_new_month)
        if self.db.get_setting("auto_update", "1") == "1" and updater.can_self_update():
            QTimer.singleShot(2500, lambda: self.check_updates(silent=True))

    def _build(self):
        self.tabs = theme.NavPages("Nöbet Görevlendirme", "Nöbetçi öğretmen görevlendirme")
        self.tabs.footer.setText(f"Sürüm {__version__}")
        self.daily = DailyTab(self)
        self.sched = ScheduleTab(self)
        self.duty = DutyTab(self)
        self.report = ReportTab(self)
        self.settings = SettingsTab(self)
        # Sıra: önce ders programı, sonra nöbet çizelgesi, sonra görevlendirme
        self.tabs.addTab(self.sched, "1   Ders Programı")
        self.tabs.addTab(self.duty, "2   Nöbet Çizelgesi")
        self.tabs.addTab(self.daily, "3   Görevlendirme")
        self.tabs.addTab(self.report, "📊   Aylık Rapor")
        self.tabs.addTab(self.settings, "⚙   Ayarlar")
        self.tabs.currentChanged.connect(self._tab_changed)
        self.setCentralWidget(self.tabs)
        self.update_brand()
        self.go_first_step()
        self.statusBar().showMessage("Hazır.")

    def go_first_step(self):
        """Eksik olan ilk adımı açar: ders programı → nöbet çizelgesi → görevlendirme."""
        if not self.db.schedule_versions():
            self.tabs.setCurrentWidget(self.sched)
        elif not self.db.duty_months():
            self.tabs.setCurrentWidget(self.duty)
        else:
            self.tabs.setCurrentWidget(self.daily)

    def next_step(self, done):
        """Bir adım bitince kullanıcıyı sıradaki adıma götürür."""
        if not self.db.duty_months():
            _info(self, f"✅ {done}\n\nSıradaki adım: 2 — Bu ayın nöbet çizelgesini yükleyin.",
                  "Sonraki adım")
            self.tabs.setCurrentWidget(self.duty)
        else:
            self.statusBar().showMessage(f"✅ {done} Artık görevlendirme yapabilirsiniz.", 8000)
            self.tabs.setCurrentWidget(self.daily)

    def check_new_month(self):
        """Ay değiştiyse yeni nöbet çizelgesini (ve değiştiyse ders programını) ister."""
        if not self.db.schedule_versions() or not self.db.duty_months():
            return  # ilk kurulum: zaten adım adım yönlendiriliyor
        month = dt.date.today().strftime("%Y-%m")
        if month in [m for m, _n in self.db.duty_months()]:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("Yeni ay")
        box.setText(f"<b>{export.month_tr(month)}</b> başladı.<br><br>Bu ayın <b>nöbet "
                    "çizelgesini</b> yükleyin. Ders programı değiştiyse yeni <b>ders "
                    "programını</b> da yükleyin.")
        duty_b = box.addButton("Nöbet çizelgesini yükle", QMessageBox.AcceptRole)
        sched_b = box.addButton("Ders programını yükle", QMessageBox.ActionRole)
        box.addButton("Sonra", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is duty_b:
            self.tabs.setCurrentWidget(self.duty)
            self.duty.load_file()
        elif box.clickedButton() is sched_b:
            self.tabs.setCurrentWidget(self.sched)
            self.sched.load_file()

    def reopen_db(self):
        self.db = Database(self.db.path)
        self._build()

    def school(self):
        return self.db.get_setting("school", "")

    def school_info(self):
        return {k: self.db.get_setting(k, "") for k, _l, _h in SCHOOL_KEYS}

    def school_header(self):
        info = self.school_info()
        return " — ".join(x for x in (info["school"], info["school_city"]) if x)

    def edit_school(self):
        if SchoolDialog(self, self.db).exec() == QDialog.Accepted:
            self.settings.refresh_school()
            self.update_brand()
            self.daily.refresh()
            self.write_excel()

    def update_brand(self):
        if not hasattr(self, "tabs"):
            return
        name = self.school() or "Nöbet Görevlendirme"
        pm = QPixmap(logo_path()) if os.path.exists(logo_path()) else theme.app_icon().pixmap(96, 96)
        self.tabs.set_brand(name, "Nöbetçi öğretmen görevlendirme", pm)

    def changed(self):
        self.daily.refresh()
        self.write_excel()

    def excel_path(self):
        saved = self.db.get_setting("excel_path")
        if saved:
            return saved
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or \
            os.path.expanduser("~")
        return os.path.join(docs, "Nöbet Görevlendirme", export.RECORDS_FILE)

    def write_excel(self):
        path = self.excel_path()
        try:
            export.write_records_xlsx(path, self.db, self.school_header())
        except PermissionError:
            self.statusBar().showMessage(
                f"⚠ Excel kayıt dosyası açık olduğu için güncellenemedi: {path} — dosyayı kapatıp "
                "tekrar kaydedin (kayıtlar programda güvende).", 15000)
            return False
        except Exception as e:  # noqa: BLE001
            self.statusBar().showMessage(f"⚠ Excel kayıt dosyası yazılamadı: {e}", 15000)
            return False
        if hasattr(self, "settings"):
            self.settings.excel.setText(path)
        return True

    def _tab_changed(self, i):
        w = self.tabs.widget(i)
        if w is self.report:
            self.report.refresh()
        elif w is self.daily:
            self.daily.refresh()
        elif w is self.duty:
            self.duty.steps.setCurrentIndex(0)
            self.duty.refresh(select=self.duty.month())
        elif w is self.sched:
            self.sched.steps.setCurrentIndex(0)
            self.sched.refresh(select=self.sched.version)
        elif w is self.settings:
            self.settings.refresh_school()
            self.settings.refresh_admins()

    # ---- güncelleme ----
    def _start(self, worker, done, failed=None):
        self._workers.append(worker)
        worker.done.connect(done)
        worker.failed.connect(failed or (lambda m: QMessageBox.warning(self, "Güncelleme", m)))
        worker.finished.connect(lambda: self._workers.remove(worker))
        worker.start()

    def check_updates(self, silent=False):
        def done(info):
            self.settings.upd.setText(f"Yüklü sürüm: <b>{__version__}</b> — GitHub'daki son sürüm: "
                                      f"<b>{info['version'] or '?'}</b>")
            if not updater.is_newer(info["version"]) or not info["url"]:
                if not silent:
                    _info(self, f"Program güncel (v{__version__}).", "Güncelleme")
                return
            if not updater.can_self_update():
                _info(self, f"Yeni sürüm var: v{info['version']}. Kaynak koddan çalıştırıyorsunuz; "
                            "'git pull' ile güncelleyin.", "Güncelleme")
                return
            notes = info["notes"].strip()[:1500]
            if _ask(self, f"Yeni sürüm mevcut: v{info['version']} (yüklü: v{__version__}).\n\n"
                          f"{notes}\n\nŞimdi indirilip kurulsun mu? Program yeniden başlayacak.",
                    "Güncelleme"):
                self._download(info)

        def failed(msg):
            if not silent:
                self._update_failed(msg)
        self._start(Worker(updater.check), done, failed)

    def _update_failed(self, msg):
        box = QMessageBox(QMessageBox.Warning, "Güncelleme",
                          f"{msg}\n\nYeni sürümü tarayıcıdan da indirebilirsiniz: indirdiğiniz "
                          "NobetGorevlendirme.exe dosyasını eskisinin yerine koyun. "
                          "Verileriniz silinmez.", parent=self)
        open_btn = box.addButton("İndirme sayfasını aç", QMessageBox.AcceptRole)
        box.addButton("Kapat", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl(updater.RELEASES_PAGE))

    def _download(self, info):
        dlg = QProgressDialog("Yeni sürüm indiriliyor…", None, 0, 100, self)
        dlg.setWindowTitle("Güncelleme")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.show()
        w = Worker(updater.download, info, with_progress=True)
        w.progress.connect(lambda d, t: dlg.setValue(int(d * 100 / t) if t else 0))

        def done(path):
            dlg.close()
            self.db.conn.commit()
            updater.apply_and_restart(path)
            QApplication.quit()

        def failed(msg):
            dlg.close()
            self._update_failed(msg)
        self._start(w, done, failed)


def _next_school_day(d):
    while d.weekday() > 4:
        d += dt.timedelta(days=1)
    return d


def _guess_month(entries):
    dates = sorted(e.date for e in entries if e.date)
    if dates:
        return dates[len(dates) // 2][:7]
    return dt.date.today().strftime("%Y-%m")


def run():
    import sys
    QLocale.setDefault(QLocale(QLocale.Turkish, QLocale.Turkey))
    app = QApplication(sys.argv)
    app.setApplicationName("Nöbetçi Öğretmen Görevlendirme")
    db = Database()
    theme.apply(app, db.get_setting("theme_accent", "Mor"), db.get_setting("theme_dark", "0") == "1")
    win = MainWindow(db)
    win.showMaximized()
    sys.exit(app.exec())
