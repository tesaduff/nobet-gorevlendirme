"""Ana pencere ve diyaloglar (PySide6)."""
import datetime as dt
import os
import shutil

from PySide6.QtCore import QDate, QLocale, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPageLayout, QTextDocument
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
                               QCompleter, QDateEdit, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit,
                               QProgressDialog, QPushButton, QSpinBox, QSplitter, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from . import export, updater
from .db import Database, data_dir
from .names import DAYS, NameMatcher, clean_name, normalize
from .parse_duty import DutyEntry, is_admin_place, parse_duty
from .parse_schedule import parse_schedule
from .reader import ReadError, read_document
from .scheduler import KIND_LABELS, options_for, plan_day, teachers_with_lessons
from .version import __version__

STATUSES = ["Okulda", "Raporlu", "İzinli", "Görevli", "Diğer"]
FILE_FILTER = "Belgeler (*.pdf *.xlsx *.xlsm *.csv);;PDF (*.pdf);;Excel (*.xlsx *.xlsm)"
YELLOW, RED, GREEN = QColor("#fff4cc"), QColor("#ffd6d6"), QColor("#e3f4e1")


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
    def __init__(self, win):
        super().__init__()
        self.win, self.db = win, win.db
        self.plan = None
        self.schedule = {}

        self.date = QDateEdit(_qdate(_next_school_day(dt.date.today()).isoformat()))
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd.MM.yyyy dddd")
        self.date.dateChanged.connect(self.refresh)
        prev_b, next_b = QPushButton("◀"), QPushButton("▶")
        prev_b.setFixedWidth(32)
        next_b.setFixedWidth(32)
        prev_b.clicked.connect(lambda: self._shift(-1))
        next_b.clicked.connect(lambda: self._shift(1))
        self.status = QLabel()
        self.status.setWordWrap(True)

        top = QHBoxLayout()
        top.addWidget(QLabel("<b>Tarih:</b>"))
        top.addWidget(prev_b)
        top.addWidget(self.date)
        top.addWidget(next_b)
        top.addWidget(self.status, 1)

        self.people = QTableWidget(0, 4)
        self.people.setHorizontalHeaderLabels(["Öğretmen", "Dersleri", "Nöbet", "Durum"])
        _stretch(self.people, 0)
        self.people.setSelectionMode(QAbstractItemView.NoSelection)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Öğretmen ara…")
        self.filter.textChanged.connect(self._filter)

        run = QPushButton("▶  Görevlendirmeyi Oluştur")
        run.setStyleSheet("font-weight:bold; padding:6px")
        run.clicked.connect(self.run)

        lbox = QGroupBox("Bugün okulda olması gerekenler — gelmeyenlerin durumunu seçin")
        lv = QVBoxLayout(lbox)
        lv.addWidget(self.filter)
        lv.addWidget(self.people)
        lv.addWidget(run)

        self.result = QTableWidget(0, 6)
        self.result.setHorizontalHeaderLabels(
            ["Saat", "Gelmeyen", "Sınıf / Ders", "Görevlendirilen", "Tür", "Not"])
        _stretch(self.result, 5)
        self.result.setWordWrap(True)
        self.summary = QLabel()

        save = QPushButton("💾 Kaydet")
        save.clicked.connect(self.save)
        xlsx = QPushButton("Excel'e aktar")
        xlsx.clicked.connect(self.to_excel)
        prt = QPushButton("Yazdır / PDF")
        prt.clicked.connect(self.print_)
        delete = QPushButton("Bu günün kaydını sil")
        delete.clicked.connect(self.delete)
        bh = QHBoxLayout()
        for b in (save, xlsx, prt):
            bh.addWidget(b)
        bh.addStretch()
        bh.addWidget(delete)

        rbox = QGroupBox("Görevlendirme (Görevlendirilen sütunundan elle değiştirebilirsiniz)")
        rv = QVBoxLayout(rbox)
        rv.addWidget(self.result, 1)
        rv.addWidget(self.summary)
        rv.addLayout(bh)

        split = QSplitter()
        split.addWidget(lbox)
        split.addWidget(rbox)
        split.setSizes([430, 870])
        v = QVBoxLayout(self)
        v.addLayout(top)
        v.addWidget(split, 1)
        self.refresh()

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
        self.result.setRowCount(0)
        self.summary.setText("")
        self.people.setRowCount(0)
        if wd > 4:
            self.status.setText("Hafta sonu — ders yok.")
            return
        vid = self.db.schedule_version_for(date)
        self.schedule = self.db.schedule(vid) if vid else {}
        duty, month = self.db.duty_for(date)
        admins_teach = self.db.get_setting("admins_teach", "0") == "1"
        self.duty = [(t, p) for t, p in duty if admins_teach or not is_admin_place(p)]
        pool = {t for t, _ in self.duty}
        msgs = []
        if not self.schedule:
            msgs.append("<span style='color:#b00'>Ders programı yüklenmedi (Ders Programı sekmesi).</span>")
        if not month:
            msgs.append("<span style='color:#b00'>Nöbet çizelgesi yüklenmedi (Nöbet Çizelgesi sekmesi).</span>")
        elif month != date[:7]:
            msgs.append(f"<span style='color:#a05a00'>Bu ayın nöbet çizelgesi yüklenmedi; "
                        f"{export.month_tr(month)} çizelgesi kullanılıyor.</span>")
        saved = self.db.assignments(date)
        saved_abs = self.db.absences(date)
        if saved or saved_abs:
            msgs.append("<b style='color:#060'>Bu gün için kayıt var.</b>")
        self.status.setText(" ".join(msgs) or f"{len(pool)} nöbetçi öğretmen.")

        teaching = teachers_with_lessons(self.schedule, wd)
        duty_place = {}
        for t, p in duty:
            duty_place[t] = (duty_place.get(t, "") + (", " if t in duty_place else "") + (p or "✓"))
        names = sorted(set(teaching) | set(duty_place) | set(saved_abs),
                       key=lambda n: (n not in pool, n not in duty_place, normalize(n)))
        self.people.setRowCount(len(names))
        for r, n in enumerate(names):
            hours = sorted(h for (d, h) in self.schedule.get(n, {}) if d == wd)
            self.people.setItem(r, 0, _item(n))
            self.people.setItem(r, 1, _item(", ".join(map(str, hours)) or "—"))
            self.people.setItem(r, 2, _item(duty_place.get(n, "")))
            if n in pool:
                for c in range(3):
                    self.people.item(r, c).setBackground(GREEN)
            elif n in duty_place:
                self.people.item(r, 2).setToolTip("Nöbetçi idareci: derse görevlendirilmez "
                                                  "(Ayarlar'dan değiştirilebilir).")
            combo = QComboBox()
            combo.addItems(STATUSES)
            if n in saved_abs:
                reason = saved_abs[n]
                combo.setCurrentText(reason if reason in STATUSES else "Diğer")
            combo.currentTextChanged.connect(lambda _t, row=r: self._mark(row))
            self.people.setCellWidget(r, 3, combo)
            self._mark(r)
        self._filter(self.filter.text())
        if saved_abs:
            self.run(saved=saved)

    def _mark(self, row):
        combo = self.people.cellWidget(row, 3)
        absent = combo.currentText() != "Okulda"
        combo.setStyleSheet("background:#ffd6d6" if absent else "")

    def _filter(self, text):
        key = text.strip().lower()
        for r in range(self.people.rowCount()):
            self.people.setRowHidden(r, bool(key) and key not in self.people.item(r, 0).text().lower())

    def absences(self):
        out = {}
        for r in range(self.people.rowCount()):
            s = self.people.cellWidget(r, 3).currentText()
            if s != "Okulda":
                out[self.people.item(r, 0).text()] = s
        return out

    def run(self, saved=None):
        date = self.date_iso()
        absences = self.absences()
        if not saved and not absences:
            _info(self, "Önce sol listeden gelmeyen öğretmenlerin durumunu seçin "
                        "(Raporlu, İzinli, Görevli…).")
            return
        counts = self.db.counts(date[:7], exclude_date=date)
        totals = self.db.total_counts(exclude_date=date)
        cap = int(self.db.get_setting("max_per_day", "0") or 0)
        self.plan = plan_day(date, self.schedule, self.duty, absences, counts, totals, cap)
        if saved:
            by_key = {(h, t): (info, a, k, n) for h, t, info, a, k, n in saved}
            for a in self.plan.assignments:
                if (a.hour, a.absent) in by_key:
                    _info_, a.assigned, a.kind, a.note = by_key[(a.hour, a.absent)]
        self.show_plan()

    def show_plan(self):
        p = self.plan
        self.result.setRowCount(len(p.assignments))
        for r, a in enumerate(p.assignments):
            self.result.setItem(r, 0, _item(a.hour))
            self.result.setItem(r, 1, _item(f"{a.absent} ({p.absences.get(a.absent, '')})"))
            self.result.setItem(r, 2, _item(a.info))
            combo = QComboBox()
            combo.addItem("— atanmadı —", None)
            opts = options_for(p, self.schedule, r)
            for t, lab in opts:
                combo.addItem(f"{t}  [{lab}]", (t, lab))
            if a.assigned and a.assigned not in [t for t, _ in opts]:
                combo.addItem(f"{a.assigned}  [kayıtlı]", (a.assigned, "kayıtlı"))
            idx = next((i for i in range(combo.count())
                        if combo.itemData(i) and combo.itemData(i)[0] == a.assigned), 0)
            combo.setCurrentIndex(idx)
            combo.currentIndexChanged.connect(lambda _i, row=r, cb=combo: self._changed(row, cb))
            self.result.setCellWidget(r, 3, combo)
            self.result.setItem(r, 4, _item(KIND_LABELS.get(a.kind, a.kind)))
            self.result.setItem(r, 5, _item(a.note))
            color = {"bos": YELLOW, "yok": RED}.get(a.kind)
            if a.kind == "elle" or "Elle" in (a.note or ""):
                color = color or QColor("#e6ecff")
            if color:
                for c in (0, 1, 2, 4, 5):
                    self.result.item(r, c).setBackground(color)
        self.result.resizeRowsToContents()
        n = len(p.assignments)
        ok = sum(1 for a in p.assignments if a.kind == "nobetci")
        free = sum(1 for a in p.assignments if a.kind == "bos")
        none = sum(1 for a in p.assignments if not a.assigned)
        self.summary.setText(f"<b>{n}</b> boş ders: <b>{ok}</b> nöbetçiye, "
                             f"<b style='color:#a05a00'>{free}</b> nöbetçi olmayan öğretmene verildi"
                             + (f", <b style='color:#b00'>{none}</b> ders atanamadı." if none else "."))

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
        self.show_plan()

    def save(self):
        if not self.plan:
            _info(self, "Kaydedilecek görevlendirme yok.")
            return
        self.db.save_day(self.date_iso(), self.plan.absences, self.plan.assignments)
        self.win.statusBar().showMessage("Kaydedildi. Aylık rapor güncellendi.", 4000)
        self.refresh()

    def delete(self):
        if _ask(self, "Bu günün devamsızlık ve görevlendirme kaydı silinsin mi?"):
            self.db.delete_day(self.date_iso())
            self.refresh()

    def to_excel(self):
        if not self.plan:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel olarak kaydet", f"gorevlendirme_{self.date_iso()}.xlsx", "Excel (*.xlsx)")
        if path:
            export.save_day_xlsx(path, self.plan, self.win.school())
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def print_(self):
        if not self.plan:
            return
        from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
        doc = QTextDocument()
        doc.setHtml(export.day_html(self.plan, self.win.school()))
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageOrientation(QPageLayout.Landscape)
        dlg = QPrintPreviewDialog(printer, self)
        dlg.setWindowTitle("Yazdır (PDF için yazıcı olarak 'Microsoft Print to PDF' seçin)")
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
        load = QPushButton("📄 Yeni ders programı yükle (PDF / Excel)")
        load.setStyleSheet("font-weight:bold; padding:6px")
        load.clicked.connect(self.load_file)
        rem = QPushButton("Seçili sürümü sil")
        rem.clicked.connect(self.delete_version)

        self.teachers = QListWidget()
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

        left = QGroupBox("Program sürümleri")
        lv = QVBoxLayout(left)
        lv.addWidget(QLabel("Program değiştiğinde yeni dosyayı yükleyip geçerlilik tarihini girin. "
                            "Eski tarihli günler eski programla hesaplanır."))
        lv.addWidget(self.versions)
        lv.addWidget(load)
        lv.addWidget(rem)
        mid = QGroupBox("Öğretmenler")
        mv = QVBoxLayout(mid)
        mv.addWidget(self.teachers)
        mh = QHBoxLayout()
        for b in (add_t, ren_t, del_t):
            mh.addWidget(b)
        mv.addLayout(mh)
        right = QGroupBox("Haftalık program (hücreye çift tıklayıp düzenleyebilirsiniz)")
        rv = QVBoxLayout(right)
        rv.addWidget(self.grid)
        rv.addWidget(save)
        split = QSplitter()
        for w in (left, mid, right):
            split.addWidget(w)
        split.setSizes([380, 260, 660])
        QVBoxLayout(self).addWidget(split)
        self.refresh()

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
        load = QPushButton("📄 Nöbet çizelgesi yükle (PDF / Excel)")
        load.setStyleSheet("font-weight:bold; padding:6px")
        load.clicked.connect(self.load_file)
        manual = QPushButton("Elle oluştur / düzenle")
        manual.clicked.connect(self.edit)
        rem = QPushButton("Seçili ayı sil")
        rem.clicked.connect(self.delete)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Hafta"] + DAYS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setWordWrap(True)
        self.dated = QLabel()
        self.dated.setWordWrap(True)

        left = QGroupBox("Aylık çizelgeler")
        lv = QVBoxLayout(left)
        lv.addWidget(QLabel("Her ay yeni çizelgeyi yükleyin. Yüklenmeyen aylarda son çizelge kullanılır."))
        lv.addWidget(self.months)
        for b in (load, manual, rem):
            lv.addWidget(b)
        right = QGroupBox("Haftalık nöbetçiler")
        rv = QVBoxLayout(right)
        rv.addWidget(self.table, 1)
        rv.addWidget(self.dated)
        split = QSplitter()
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([340, 960])
        QVBoxLayout(self).addWidget(split)
        self.refresh()

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
                t + (f" — {p}" if p else ""))
        self.table.setRowCount(len(weeks))
        self.table.clearContents()
        for r, key in enumerate(sorted(weeks)):
            label = "Her hafta" if not key else _qdate(key).toString("dd.MM") + " haftası"
            self.table.setItem(r, 0, _item(label))
            for d, items in weeks[key].items():
                self.table.setItem(r, d + 1, _item("\n".join(items)))
        self.table.resizeRowsToContents()
        self.dated.setText("Nöbet yeri 'idareci' olanlar varsayılan olarak derse görevlendirilmez."
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
        v.addLayout(top)
        v.addWidget(QLabel("Kaydedilen günlerdeki görevlendirmeler sayılır. Program, nöbetçiler "
                           "arasında bu ay en az derse girene öncelik vererek sayıları eşitler."))
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


class SettingsTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win, self.db = win, win.db
        self.school = QLineEdit(self.db.get_setting("school", ""))
        self.school.setPlaceholderText("Ör. Atatürk Anadolu Lisesi Müdürlüğü")
        self.school.editingFinished.connect(
            lambda: self.db.set_setting("school", self.school.text().strip()))

        self.auto = QCheckBox("Program açılırken güncellemeleri denetle")
        self.auto.setChecked(self.db.get_setting("auto_update", "1") == "1")
        self.auto.toggled.connect(lambda v: self.db.set_setting("auto_update", "1" if v else "0"))
        check = QPushButton("🔄 Güncellemeleri denetle")
        check.clicked.connect(lambda: win.check_updates(silent=False))
        self.upd = QLabel(f"Yüklü sürüm: <b>{__version__}</b>")

        folder = QPushButton("Veri klasörünü aç")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(data_dir())))
        backup = QPushButton("Yedek al…")
        backup.clicked.connect(self.backup)
        restore = QPushButton("Yedekten geri yükle…")
        restore.clicked.connect(self.restore)

        self.cap = QSpinBox()
        self.cap.setRange(0, 8)
        self.cap.setSpecialValueText("Sınırsız")
        self.cap.setValue(int(self.db.get_setting("max_per_day", "0") or 0))
        self.cap.valueChanged.connect(lambda v: self.db.set_setting("max_per_day", v))

        g1 = QGroupBox("Okul ve dağıtım")
        f1 = QFormLayout(g1)
        f1.addRow("Çıktılarda görünecek okul adı:", self.school)
        f1.addRow("Bir nöbetçiye günde en fazla ders:", self.cap)
        f1.addRow("", QLabel("Sınıra ulaşan nöbetçinin yerine o saatte boş olan başka bir "
                             "öğretmen (notla) atanır; kimse yoksa yine nöbetçiye verilir."))
        self.admins = QCheckBox("Nöbetçi idareciler (müdür yardımcıları) de boş derslere görevlendirilsin")
        self.admins.setChecked(self.db.get_setting("admins_teach", "0") == "1")
        self.admins.toggled.connect(lambda v: (self.db.set_setting("admins_teach", "1" if v else "0"),
                                               win.changed()))
        f1.addRow("", self.admins)
        g2 = QGroupBox("Güncelleme")
        v2 = QVBoxLayout(g2)
        v2.addWidget(self.upd)
        v2.addWidget(QLabel(f"Güncellemeler GitHub'dan alınır: github.com/{updater.REPO}"))
        v2.addWidget(self.auto)
        v2.addWidget(check)
        g3 = QGroupBox("Veriler")
        v3 = QVBoxLayout(g3)
        v3.addWidget(QLabel(f"Tüm veriler bu bilgisayarda tutulur:\n{self.db.path}\n"
                            "Güncelleme verileri silmez."))
        h3 = QHBoxLayout()
        for b in (folder, backup, restore):
            h3.addWidget(b)
        h3.addStretch()
        v3.addLayout(h3)
        v = QVBoxLayout(self)
        for g in (g1, g2, g3):
            v.addWidget(g)
        v.addStretch()

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
        self.resize(1320, 800)
        self.db = db or Database()
        self._workers = []
        self._build()
        if self.db.get_setting("auto_update", "1") == "1" and updater.can_self_update():
            QTimer.singleShot(2500, lambda: self.check_updates(silent=True))

    def _build(self):
        self.tabs = QTabWidget()
        self.daily = DailyTab(self)
        self.sched = ScheduleTab(self)
        self.duty = DutyTab(self)
        self.report = ReportTab(self)
        self.settings = SettingsTab(self)
        self.tabs.addTab(self.daily, "📅 Günlük Görevlendirme")
        self.tabs.addTab(self.sched, "📚 Ders Programı")
        self.tabs.addTab(self.duty, "🛡 Nöbet Çizelgesi")
        self.tabs.addTab(self.report, "📊 Aylık Rapor")
        self.tabs.addTab(self.settings, "⚙ Ayarlar")
        self.tabs.currentChanged.connect(self._tab_changed)
        self.setCentralWidget(self.tabs)
        self.statusBar().showMessage(f"Veriler: {self.db.path}")

    def reopen_db(self):
        self.db = Database(self.db.path)
        self._build()

    def school(self):
        return self.db.get_setting("school", "")

    def changed(self):
        self.daily.refresh()

    def _tab_changed(self, i):
        w = self.tabs.widget(i)
        if w is self.report:
            self.report.refresh()
        elif w is self.daily:
            self.daily.refresh()

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
                QMessageBox.warning(self, "Güncelleme", msg)
        self._start(Worker(updater.check), done, failed)

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
            QMessageBox.warning(self, "Güncelleme", msg)
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
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
