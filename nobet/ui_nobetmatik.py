"""Nöbetmatik ekranı: 5 adımda (İleri / Geri) aylık nöbet çizelgesi oluşturma."""
import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QImage, QPageLayout, QTextDocument
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog,
                               QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QRadioButton, QSpinBox, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import export, theme
from . import ui as U
from .names import DAYS, normalize
from .nobetmatik import ADMIN_PLACE, Config, distribute, lesson_count, rule_text
from .theme import page_header, variant

STEPS = ["Ay ve öğretmenler", "Nöbet yerleri", "Seçenekler", "Kurallar", "Dağıt ve kaydet"]
RULE_KINDS = {"fixed": "Sabitle", "together": "Beraber", "apart": "Ayrı", "allowed": "Gün kısıtı"}


class RuleDialog(QDialog):
    def __init__(self, parent, kind, teachers, places):
        super().__init__(parent)
        self.kind = kind
        self.setWindowTitle(f"Kural ekle — {RULE_KINDS[kind]}")
        self.resize(460, 260)
        form = QFormLayout()
        self.a = self._teacher_combo(teachers)
        explain = {
            "fixed": "Öğretmen her hafta seçilen gün (isterseniz seçilen yerde) nöbet tutar.",
            "together": "İki öğretmen aynı gün nöbet tutar.",
            "apart": "İki öğretmen aynı gün nöbet tutmaz.",
            "allowed": "Öğretmen yalnızca işaretlenen günlerde nöbet tutabilir.",
        }[kind]
        lab = QLabel(explain)
        lab.setWordWrap(True)
        form.addRow(lab)
        form.addRow("Öğretmen:", self.a)
        if kind == "fixed":
            self.day = QComboBox()
            self.day.addItems(DAYS)
            self.place = QComboBox()
            self.place.addItem("Fark etmez (yerler dönsün)", "")
            for p in places:
                self.place.addItem(p, p)
            form.addRow("Gün:", self.day)
            form.addRow("Nöbet yeri:", self.place)
        elif kind in ("together", "apart"):
            self.b = self._teacher_combo(teachers)
            form.addRow("İkinci öğretmen:", self.b)
        else:
            self.days = [QCheckBox(d) for d in DAYS]
            h = QHBoxLayout()
            for c in self.days:
                h.addWidget(c)
            form.addRow("Günler:", h)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Ekle")
        variant(bb.button(QDialogButtonBox.Ok), "primary")
        bb.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        v = QVBoxLayout(self)
        v.addLayout(form)
        v.addStretch()
        v.addWidget(bb)

    @staticmethod
    def _teacher_combo(teachers):
        c = QComboBox()
        c.setEditable(True)
        c.addItems(teachers)
        c.setInsertPolicy(QComboBox.NoInsert)
        comp = c.completer()
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        return c

    def _ok(self):
        if self.kind in ("together", "apart") and self.a.currentText() == self.b.currentText():
            U._info(self, "İki farklı öğretmen seçin.")
            return
        if self.kind == "allowed" and not any(c.isChecked() for c in self.days):
            U._info(self, "En az bir gün işaretleyin.")
            return
        self.accept()

    def rule(self):
        t = self.a.currentText()
        if self.kind == "fixed":
            return {"teacher": t, "day": self.day.currentIndex(), "place": self.place.currentData()}
        if self.kind in ("together", "apart"):
            return [t, self.b.currentText()]
        return [t, [i for i, c in enumerate(self.days) if c.isChecked()]]


class NobetmatikPage(QWidget):
    def __init__(self, win, on_done, on_cancel):
        super().__init__()
        self.win, self.db = win, win.db
        self.on_done, self.on_cancel = on_done, on_cancel
        self.cfg = Config()
        self.schedule = {}
        self.result = None
        self.rules = []          # [(tür, kural)]

        self.stepbar = theme.StepBar(STEPS)
        self.stack = QStackedWidget()
        for build in (self._page_teachers, self._page_places, self._page_options,
                      self._page_rules, self._page_result):
            self.stack.addWidget(build())

        self.back = QPushButton("←  Geri")
        self.back.setMinimumHeight(44)
        self.back.clicked.connect(lambda: self.go(self.stack.currentIndex() - 1))
        self.next = variant(QPushButton("İleri  →"), "primary")
        self.next.setMinimumHeight(44)
        self.next.setStyleSheet("font-size:12pt")
        self.next.clicked.connect(lambda: self.go(self.stack.currentIndex() + 1))
        cancel = QPushButton("Vazgeç")
        cancel.setMinimumHeight(44)
        cancel.clicked.connect(self.on_cancel)
        self.save_btn = variant(QPushButton("✅  Kaydet ve kullan"), "primary")
        self.save_btn.setMinimumHeight(44)
        self.save_btn.clicked.connect(self.save)
        foot = QHBoxLayout()
        foot.addWidget(cancel)
        foot.addStretch()
        foot.addWidget(self.back)
        foot.addWidget(self.next)
        foot.addWidget(self.save_btn)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.stepbar)
        v.addWidget(self.stack, 1)
        v.addLayout(foot)

    # ------------------------------------------------------------ sayfalar
    def _page_teachers(self):
        self.month = U.MonthPicker()
        self.month.changed.connect(self._month_changed)
        self.teach = QTableWidget(0, 5)
        self.teach.setHorizontalHeaderLabels(["Nöbet tutar", "Öğretmen", "Ders günleri", "Muaf",
                                              "Muafiyet mazereti"])
        U._stretch(self.teach, 1)
        self.teach.horizontalHeader().setSectionResizeMode(4, U.QHeaderView.Stretch)
        self.teach.verticalHeader().hide()
        self.teach.setSelectionMode(QAbstractItemView.NoSelection)
        self.teach.setMinimumHeight(180)
        all_b = QPushButton("Tümünü seç")
        all_b.clicked.connect(lambda: self._check_all(True))
        none_b = QPushButton("Hiçbirini seçme")
        none_b.clicked.connect(lambda: self._check_all(False))
        self.teach_info = QLabel()
        self.teach_info.setObjectName("subtitle")
        self.teach_info.setWordWrap(True)
        top = QHBoxLayout()
        top.addWidget(QLabel("<b>Hangi ayın çizelgesi?</b>"))
        top.addWidget(self.month)
        top.addStretch()
        top.addWidget(all_b)
        top.addWidget(none_b)
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        v.addLayout(top)
        v.addWidget(self.teach_info)
        v.addWidget(self.teach, 1)
        return p

    def _page_places(self):
        self.places = QTableWidget(0, 2)
        self.places.setHorizontalHeaderLabels(["Nöbet yeri", "Her gün kaç nöbetçi?"])
        U._stretch(self.places, 0)
        self.places.verticalHeader().hide()
        self.places.setMinimumHeight(180)
        add = QPushButton("＋  Yer ekle")
        add.clicked.connect(lambda: self._add_place("", 1))
        rem = variant(QPushButton("Seçili yeri sil"), "danger")
        rem.clicked.connect(self._remove_place)
        self.cap_info = QLabel()
        self.cap_info.setWordWrap(True)
        h = QHBoxLayout()
        h.addWidget(add)
        h.addWidget(rem)
        h.addStretch()
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        hint = QLabel("Okulunuzdaki nöbet yerlerini (Bahçe, Zemin Kat, 1. Kat, 2. Kat, Kantin…) ve "
                      "her yerde <b>her gün</b> kaç nöbetçi olacağını girin.")
        hint.setWordWrap(True)
        v.addWidget(hint)
        v.addWidget(self.places, 1)
        v.addLayout(h)
        v.addWidget(self.cap_info)
        return p

    def _page_options(self):
        self.pw1 = QRadioButton("Herkes haftada yalnızca 1 nöbet tutsun")
        self.pw2 = QRadioButton("Yer artarsa bazı öğretmenler haftada 2 nöbet tutabilsin")
        grp = QButtonGroup(self)
        grp.addButton(self.pw1)
        grp.addButton(self.pw2)
        self.skip_free = QCheckBox("Öğretmenin dersi olmayan günlere nöbet yazma")
        self.light = QCheckBox("Dersin tam dolu olduğu günler yerine daha rahat günleri tercih et "
                               "(ör. 7 saatlik günde 7 değil 5 dersinin olduğu gün)")
        self.light.setStyleSheet("")
        self.rotate = QCheckBox("Nöbet yerleri her hafta değişsin "
                                "(Bahçe → Zemin Kat → 1. Kat → 2. Kat …)")
        g1 = QGroupBox("Haftalık nöbet sayısı")
        l1 = QVBoxLayout(g1)
        l1.addWidget(self.pw1)
        l1.addWidget(self.pw2)
        g2 = QGroupBox("Dağıtım tercihleri")
        l2 = QVBoxLayout(g2)
        for c in (self.skip_free, self.light, self.rotate):
            l2.addWidget(c)
        self.admin_combos = []
        g3 = QGroupBox("Nöbetçi idareci (isteğe bağlı)")
        l3 = QFormLayout(g3)
        for d in DAYS:
            c = QComboBox()
            c.setMinimumWidth(260)
            self.admin_combos.append(c)
            l3.addRow(d + ":", c)
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        for g in (g1, g2, g3):
            v.addWidget(g)
        v.addStretch()
        return p

    def _page_rules(self):
        self.rules_t = QTableWidget(0, 2)
        self.rules_t.setHorizontalHeaderLabels(["Kural", "Açıklama"])
        U._stretch(self.rules_t, 1)
        self.rules_t.verticalHeader().hide()
        self.rules_t.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rules_t.setMinimumHeight(160)
        h = QHBoxLayout()
        for kind, label in RULE_KINDS.items():
            b = QPushButton("＋  " + label)
            b.clicked.connect(lambda _c=False, k=kind: self._add_rule(k))
            h.addWidget(b)
        rem = variant(QPushButton("Seçili kuralı sil"), "danger")
        rem.clicked.connect(self._remove_rule)
        h.addStretch()
        h.addWidget(rem)
        hint = QLabel("İsterseniz kural ekleyin; kural yoksa doğrudan <b>İleri</b>'ye basın.<br>"
                      "<b>Sabitle</b>: öğretmen hep aynı gün (ve yer) · <b>Beraber</b>: iki öğretmen "
                      "aynı gün · <b>Ayrı</b>: aynı gün olmasın · <b>Gün kısıtı</b>: yalnızca "
                      "seçilen günler")
        hint.setWordWrap(True)
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(hint)
        v.addLayout(h)
        v.addWidget(self.rules_t, 1)
        return p

    def _page_result(self):
        self.week = QComboBox()
        self.week.setMinimumWidth(240)
        self.week.currentIndexChanged.connect(self._show_week)
        again = QPushButton("🔄  Yeniden dağıt")
        again.clicked.connect(self.run)
        prt = QPushButton("🖨  Baskı önizleme")
        prt.clicked.connect(self.print_)
        top = QHBoxLayout()
        top.addWidget(QLabel("<b>Hafta:</b>"))
        top.addWidget(self.week)
        top.addStretch()
        top.addWidget(again)
        top.addWidget(prt)
        self.grid = QTableWidget(0, 0)
        self.grid.verticalHeader().hide()
        self.grid.setSelectionMode(QAbstractItemView.NoSelection)
        self.grid.setWordWrap(True)
        self.grid.setMinimumHeight(180)
        self.res_info = QLabel()
        self.res_info.setWordWrap(True)
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        v.addLayout(top)
        v.addWidget(self.grid, 1)
        v.addWidget(self.res_info)
        return p

    # ------------------------------------------------------------ akış
    def start(self, month=None):
        saved = Config.from_dict(self.db.nobetmatik_config())
        self.cfg = saved
        self.month.set(month or U.dt.date.today().strftime("%Y-%m"))
        self.rules = ([("fixed", r) for r in saved.fixed] +
                      [("together", r) for r in saved.together] +
                      [("apart", r) for r in saved.apart] +
                      [("allowed", [t, d]) for t, d in saved.allowed_days.items()])
        # Önce seçenek kutuları: yer eklerken yapılan kapasite hesabı ayarları okur.
        (self.pw2 if saved.per_week >= 2 else self.pw1).setChecked(True)
        self.skip_free.setChecked(saved.skip_free_days)
        self.light.setChecked(saved.prefer_light_days)
        self.rotate.setChecked(saved.rotate)
        places = [list(p) for p in saved.places]
        self._month_changed()
        self.places.setRowCount(0)
        for p, n in places:
            self._add_place(p, n)
        self._fill_rules()
        self.go(0)

    def _month_changed(self):
        month = self.month.key()
        vid = self.db.schedule_version_for(month + "-01")
        self.schedule = self.db.schedule(vid) if vid else {}
        admins = self.db.admins()
        teachers = sorted((t for t in self.schedule if t not in admins), key=normalize)
        known = set(self.cfg.teachers)
        self.teach.setRowCount(len(teachers))
        for r, t in enumerate(teachers):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if (t in known or not known) else Qt.Unchecked)
            self.teach.setItem(r, 0, chk)
            self.teach.setItem(r, 1, U._item(t))
            days = [DAYS[d][:3] + f" {lesson_count(self.schedule, t, d)}"
                    for d in range(5) if lesson_count(self.schedule, t, d)]
            self.teach.setItem(r, 2, U._item("  ".join(days)))
            ex = QTableWidgetItem()
            ex.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            ex.setCheckState(Qt.Checked if t in self.cfg.exempt else Qt.Unchecked)
            self.teach.setItem(r, 3, ex)
            reason = QLineEdit(self.cfg.exempt.get(t, ""))
            reason.setPlaceholderText("Muafsa mazereti yazın (ör. hamilelik, sağlık raporu)")
            reason.textChanged.connect(lambda txt, row=r: self._reason_typed(row, txt))
            self.teach.setCellWidget(r, 4, reason)
        self.teach_info.setText(
            f"Ders programından {len(teachers)} öğretmen alındı (idareciler hariç). Nöbet "
            "tutmayacakların işaretini kaldırın; <b>muaf</b> olanları işaretleyip mazeretini yazın.")
        names = ["—"] + sorted(admins, key=normalize)
        for d, c in enumerate(self.admin_combos):
            c.clear()
            c.addItems(names)
            c.setCurrentText(self.cfg.admins_by_day.get(str(d), "—"))

    def _reason_typed(self, row, text):
        if text.strip():
            self.teach.item(row, 3).setCheckState(Qt.Checked)

    def _check_all(self, on):
        for r in range(self.teach.rowCount()):
            self.teach.item(r, 0).setCheckState(Qt.Checked if on else Qt.Unchecked)

    def _add_place(self, name, count):
        r = self.places.rowCount()
        self.places.insertRow(r)
        self.places.setItem(r, 0, QTableWidgetItem(name))
        sp = QSpinBox()
        sp.setRange(1, 20)
        sp.setValue(int(count) or 1)
        sp.valueChanged.connect(self._update_capacity)
        self.places.setCellWidget(r, 1, sp)
        self._update_capacity()
        if not name:
            self.places.editItem(self.places.item(r, 0))

    def _remove_place(self):
        r = self.places.currentRow()
        if r >= 0:
            self.places.removeRow(r)
            self._update_capacity()

    def _collect(self):
        c = self.cfg
        c.month = self.month.key()
        c.teachers, c.exempt = [], {}
        for r in range(self.teach.rowCount()):
            t = self.teach.item(r, 1).text()
            if self.teach.item(r, 0).checkState() == Qt.Checked:
                c.teachers.append(t)
            if self.teach.item(r, 3).checkState() == Qt.Checked:
                c.exempt[t] = self.teach.cellWidget(r, 4).text().strip()
        c.places = []
        for r in range(self.places.rowCount()):
            name = (self.places.item(r, 0).text() if self.places.item(r, 0) else "").strip()
            if name:
                c.places.append([name, self.places.cellWidget(r, 1).value()])
        c.per_week = 2 if self.pw2.isChecked() else 1
        c.skip_free_days = self.skip_free.isChecked()
        c.prefer_light_days = self.light.isChecked()
        c.rotate = self.rotate.isChecked()
        c.admins_by_day = {str(d): cb.currentText() for d, cb in enumerate(self.admin_combos)
                           if cb.currentText() and cb.currentText() != "—"}
        c.fixed = [r for k, r in self.rules if k == "fixed"]
        c.together = [r for k, r in self.rules if k == "together"]
        c.apart = [r for k, r in self.rules if k == "apart"]
        c.allowed_days = {r[0]: r[1] for k, r in self.rules if k == "allowed"}
        return c

    def _update_capacity(self):
        c = self._collect()
        per_day = c.capacity()
        n = len([t for t in c.teachers if t not in c.exempt])
        need = "yeterli" if per_day * 5 >= n else "yetersiz — bazı öğretmenlere bu ay nöbet düşmez"
        self.cap_info.setText(f"Günde <b>{per_day}</b>, haftada <b>{per_day * 5}</b> nöbet yeri var; "
                              f"nöbet tutacak <b>{n}</b> öğretmen var ({need}).")

    def _fill_rules(self):
        self.rules_t.setRowCount(len(self.rules))
        for r, (k, rule) in enumerate(self.rules):
            self.rules_t.setItem(r, 0, U._item(RULE_KINDS[k]))
            self.rules_t.setItem(r, 1, U._item(rule_text(k, rule)))

    def _add_rule(self, kind):
        c = self._collect()
        teachers = [t for t in c.teachers if t not in c.exempt]
        if not teachers:
            U._info(self, "Önce 1. adımda nöbet tutacak öğretmenleri seçin.")
            return
        dlg = RuleDialog(self, kind, teachers, [p for p, _n in c.places])
        if dlg.exec() == QDialog.Accepted:
            rule = dlg.rule()
            if kind == "allowed":
                self.rules = [(k, r) for k, r in self.rules
                              if not (k == "allowed" and r[0] == rule[0])]
            if kind == "fixed":
                self.rules = [(k, r) for k, r in self.rules
                              if not (k == "fixed" and r["teacher"] == rule["teacher"])]
            self.rules.append((kind, rule))
            self._fill_rules()

    def _remove_rule(self):
        r = self.rules_t.currentRow()
        if r >= 0:
            del self.rules[r]
            self._fill_rules()

    def go(self, index):
        cur = self.stack.currentIndex()
        if index > cur:
            c = self._collect()
            if cur == 0 and not [t for t in c.teachers if t not in c.exempt]:
                U._info(self, "Nöbet tutacak en az bir öğretmen seçin.")
                return
            if cur == 1 and not c.places:
                U._info(self, "En az bir nöbet yeri girin.")
                return
        if index < 0:
            return
        index = min(index, self.stack.count() - 1)
        self.stack.setCurrentIndex(index)
        self.stepbar.set(index)
        last = index == self.stack.count() - 1
        self.back.setEnabled(index > 0)
        self.next.setVisible(not last)
        self.save_btn.setVisible(last)
        if index == 1:
            self._update_capacity()
        if last:
            self.run()

    def run(self):
        c = self._collect()
        history = self.db.duty_history(c.month)
        self.result = distribute(c, self.schedule, history)
        self.week.blockSignals(True)
        self.week.clear()
        for monday, dates in self.result.weeks:
            self.week.addItem(f"{dates[0].strftime('%d.%m')} – {dates[-1].strftime('%d.%m.%Y')}")
        self.week.blockSignals(False)
        self._show_week(0)
        counts = {}
        for d, ts in self.result.by_day.items():
            for t in ts:
                counts[t] = counts.get(t, 0) + 1
        lines = [f"✅ <b>{len(counts)}</b> öğretmene haftada nöbet verildi "
                 f"({sum(counts.values())} nöbet/hafta)."]
        if any(v > 1 for v in counts.values()):
            lines.append(f"{sum(1 for v in counts.values() if v > 1)} öğretmen haftada 2 nöbet tutuyor.")
        lines += [f"<span style='color:#d97706'>⚠ {w}</span>" for w in self.result.warnings]
        if self.result.unassigned:
            lines.append("Bu ay nöbet verilmeyenler: " + ", ".join(self.result.unassigned))
        lines.append("Beğenmezseniz kuralları değiştirip <b>Yeniden dağıt</b>'a basın; "
                     "uygunsa <b>Kaydet ve kullan</b>.")
        self.res_info.setText("<br>".join(lines))

    def _show_week(self, w):
        if not self.result or w < 0 or w >= len(self.result.weeks):
            return
        places = [p for p, _n in self.cfg.places]
        has_admin = any(e.place == ADMIN_PLACE for e in self.result.entries)
        cols = ["Gün"] + places + (["Nöbetçi idareci"] if has_admin else [])
        self.grid.clear()
        self.grid.setColumnCount(len(cols))
        self.grid.setHorizontalHeaderLabels(cols)
        U._stretch(self.grid, *range(1, len(cols)))
        dates = self.result.weeks[w][1]
        self.grid.setRowCount(len(dates))
        for r, date in enumerate(dates):
            iso = date.isoformat()
            self.grid.setItem(r, 0, U._item(f"{DAYS[date.weekday()]}\n{date.strftime('%d.%m')}"))
            for c, p in enumerate(places + ([ADMIN_PLACE] if has_admin else []), start=1):
                names = [e.teacher for e in self.result.entries if e.date == iso and e.place == p]
                self.grid.setItem(r, c, U._item("\n".join(names)))
        self.grid.resizeRowsToContents()

    def print_(self):
        if not self.result:
            return
        print_duty(self, self.win, self.cfg.month, self.result.entries, self.cfg.exempt,
                   [p for p, _n in self.cfg.places])

    def save(self):
        if not self.result:
            return
        month = self.cfg.month
        if month in [m for m, _n in self.db.duty_months()] and not U._ask(
                self, f"{export.month_tr(month)} için kayıtlı bir nöbet çizelgesi var. "
                      "Yenisiyle değiştirilsin mi?"):
            return
        self.db.save_duty(month, self.result.entries)
        self.db.save_nobetmatik_config(self.cfg.to_dict())
        self.on_done(month)


def print_duty(parent, win, month, entries, exempt=None, places=None):
    from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
    doc = QTextDocument()
    has_logo = os.path.exists(U.logo_path())
    if has_logo:
        doc.addResource(QTextDocument.ImageResource, QUrl("logo"), QImage(U.logo_path()))
    doc.setHtml(export.duty_html(month, entries, win.school_info(), has_logo, exempt, places))
    printer = QPrinter(QPrinter.HighResolution)
    printer.setPageOrientation(QPageLayout.Portrait)
    dlg = QPrintPreviewDialog(printer, parent)
    dlg.setWindowTitle("Baskı önizleme — PDF için yazıcı olarak 'Microsoft Print to PDF' seçin")
    dlg.resize(1100, 800)
    dlg.paintRequested.connect(doc.print_)
    dlg.exec()
