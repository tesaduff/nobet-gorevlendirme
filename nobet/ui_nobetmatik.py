"""Nöbetmatik ekranı: 5 adımda (İleri / Geri) aylık nöbet çizelgesi oluşturma."""
import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QImage, QPageLayout, QTextDocument
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog,
                               QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPushButton, QRadioButton, QSpinBox, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import export, theme
from . import ui as U
from .names import DAYS, normalize
from .nobetmatik import ADMIN_PLACE, Config, distribute, lesson_count, move_teacher, rule_text
from .theme import page_header, variant

STEPS = ["Ay ve öğretmenler", "Nöbet yerleri", "Seçenekler", "Kurallar", "Dağıt",
         "Düzenle ve kaydet"]
RULE_KINDS = {"fixed": "Sabitle", "exempt": "Muaf", "together": "Beraber", "apart": "Ayrı",
              "allowed": "Gün kısıtı"}


def teacher_combo(teachers=()):
    """Yazarak aranabilen öğretmen seçimi."""
    c = QComboBox()
    c.setEditable(True)
    c.setInsertPolicy(QComboBox.NoInsert)
    c.addItems(list(teachers))
    c.setMinimumHeight(36)
    comp = c.completer()
    comp.setCaseSensitivity(Qt.CaseInsensitive)
    comp.setFilterMode(Qt.MatchContains)
    return c


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
                      self._page_rules, self._page_result, self._page_edit):
            self.stack.addWidget(build())

        self.back = QPushButton("←  Geri")
        self.back.setMinimumHeight(40)
        self.back.clicked.connect(lambda: self.go(self.stack.currentIndex() - 1))
        self.next = variant(QPushButton("İleri  →"), "primary")
        self.next.setMinimumHeight(40)
        self.next.setStyleSheet("font-size:12pt")
        self.next.clicked.connect(lambda: self.go(self.stack.currentIndex() + 1))
        cancel = QPushButton("Vazgeç")
        cancel.setMinimumHeight(40)
        cancel.clicked.connect(self.on_cancel)
        self.save_btn = variant(QPushButton("✅  Kaydet ve kullan"), "primary")
        self.save_btn.setMinimumHeight(40)
        self.save_btn.clicked.connect(self.save)
        foot = QHBoxLayout()
        foot.addWidget(cancel)
        foot.addStretch()
        foot.addWidget(self.back)
        foot.addWidget(self.next)
        foot.addWidget(self.save_btn)

        # Gezinme düğmeleri üstte: küçük ekranlarda da her zaman görünür
        self.stack.setMinimumHeight(220)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.stepbar)
        v.addLayout(foot)
        v.addWidget(self.stack, 1)

    # ------------------------------------------------------------ sayfalar
    def _page_teachers(self):
        self.month = U.MonthPicker()
        self.month.changed.connect(self._month_changed)
        # Sütunlar: nöbet tutar (ortalı onay kutusu) | öğretmen | her gün için ders sayısı
        self.teach = QTableWidget(0, 7)
        self.teach.setHorizontalHeaderLabels(["Nöbet tutar", "Öğretmen"] +
                                             ["Pzt", "Sal", "Çar", "Per", "Cum"])
        U._stretch(self.teach, 1)
        hh = self.teach.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        self.teach.setColumnWidth(0, 110)
        for c in range(2, 7):
            hh.setSectionResizeMode(c, QHeaderView.Fixed)
            self.teach.setColumnWidth(c, 70)
            self.teach.horizontalHeaderItem(c).setToolTip(f"{DAYS[c - 2]} günkü ders sayısı")
        hh.setDefaultAlignment(Qt.AlignCenter)
        self.teach.setMaximumWidth(860)
        self.teach_checks = []
        self.teach.verticalHeader().hide()
        self.teach.setSelectionMode(QAbstractItemView.NoSelection)
        self.teach.setMinimumHeight(140)
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
        tc = QHBoxLayout()
        tc.addStretch(1)
        tc.addWidget(self.teach, 20)
        tc.addStretch(1)
        v.addLayout(tc, 1)
        return p

    def _page_places(self):
        self.places = QTableWidget(0, 2)
        self.places.setHorizontalHeaderLabels(["Nöbet yeri", "Her gün kaç nöbetçi?"])
        U._stretch(self.places, 0)
        self.places.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.places.setColumnWidth(1, 190)
        self.places.verticalHeader().hide()
        self.places.setMinimumHeight(120)
        self.places.setFixedWidth(560)
        add = QPushButton("＋  Yer ekle")
        add.clicked.connect(lambda: self._add_place("", 1))
        rem = variant(QPushButton("Seçili yeri sil"), "danger")
        rem.clicked.connect(self._remove_place)
        self.cap_info = QLabel()
        self.cap_info.setWordWrap(True)
        self.fit = variant(QPushButton("Herkese haftada 1 nöbet yetecek kadar yer ayarla"), "primary")
        self.fit.clicked.connect(self._fit_capacity)
        h = QHBoxLayout()
        h.addWidget(add)
        h.addStretch()
        h.addWidget(rem)
        self.cap_info.setFixedWidth(560)
        hint = QLabel("Okulunuzdaki nöbet yerlerini (Bahçe, Zemin Kat, 1. Kat, 2. Kat, Kantin…) ve "
                      "her yerde <b>her gün</b> kaç nöbetçi olacağını girin.")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        col = QVBoxLayout()
        col.addWidget(self.places, 1)
        col.addLayout(h)
        col.addWidget(self.cap_info)
        col.addWidget(self.fit)
        center = QHBoxLayout()
        center.addStretch()
        center.addLayout(col)
        center.addStretch()
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(hint)
        v.addLayout(center, 1)
        return p

    def _page_options(self):
        self.pw1 = QRadioButton("Herkes haftada yalnızca 1 nöbet tutsun")
        self.pw1.toggled.connect(lambda _v: self._update_capacity() if self.places.rowCount() else None)
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
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 0, 4, 0)
        for g in (g1, g2, g3):
            v.addWidget(g)
        v.addStretch()
        from PySide6.QtWidgets import QFrame, QScrollArea
        p = QScrollArea()
        p.setWidgetResizable(True)
        p.setFrameShape(QFrame.NoFrame)
        p.setWidget(inner)
        return p

    def _page_rules(self):
        """Önce öğretmen, sonra kural türü; türe göre ilgili alan açılır."""
        self.r_teacher = teacher_combo()
        self.r_teacher.lineEdit().setPlaceholderText("Öğretmen adını yazın veya seçin…")
        self.r_kind = QComboBox()
        self.r_kind.setMinimumHeight(36)
        for k, label in RULE_KINDS.items():
            self.r_kind.addItem(label, k)
        self.r_fields = QStackedWidget()
        # Sabitle: gün + yer
        f_fixed = QWidget()
        ff = QHBoxLayout(f_fixed)
        ff.setContentsMargins(0, 0, 0, 0)
        self.r_day = QComboBox()
        self.r_day.addItems(DAYS)
        self.r_place = QComboBox()
        self.r_place.setMinimumWidth(200)
        ff.addWidget(QLabel("Hangi gün:"))
        ff.addWidget(self.r_day)
        ff.addSpacing(12)
        ff.addWidget(QLabel("Hangi yer:"))
        ff.addWidget(self.r_place)
        ff.addStretch()
        # Muaf: mazeret
        f_ex = QWidget()
        fe = QHBoxLayout(f_ex)
        fe.setContentsMargins(0, 0, 0, 0)
        self.r_reason = QLineEdit()
        self.r_reason.setPlaceholderText("Mazereti yazın (ör. sağlık raporu, hamilelik, görevlendirme)")
        self.r_reason.setMinimumHeight(36)
        fe.addWidget(QLabel("Mazeret:"))
        fe.addWidget(self.r_reason, 1)
        # Beraber / Ayrı: kiminle
        f_with = QWidget()
        fw = QHBoxLayout(f_with)
        fw.setContentsMargins(0, 0, 0, 0)
        self.r_other = teacher_combo()
        self.r_with_label = QLabel("Kiminle:")
        fw.addWidget(self.r_with_label)
        fw.addWidget(self.r_other, 1)
        # Gün kısıtı: günler
        f_days = QWidget()
        fd = QHBoxLayout(f_days)
        fd.setContentsMargins(0, 0, 0, 0)
        fd.addWidget(QLabel("Yalnızca şu günler:"))
        self.r_days = [QCheckBox(d) for d in DAYS]
        for c in self.r_days:
            fd.addWidget(c)
        fd.addStretch()
        self._field_of = {"fixed": 0, "exempt": 1, "together": 2, "apart": 2, "allowed": 3}
        for w in (f_fixed, f_ex, f_with, f_days):
            self.r_fields.addWidget(w)
        self.r_kind.currentIndexChanged.connect(self._kind_changed)
        add = variant(QPushButton("＋  Kuralı ekle"), "primary")
        add.setMinimumHeight(40)
        add.clicked.connect(self._add_rule)

        builder = QGroupBox("Yeni kural")
        bl = QFormLayout(builder)
        bl.addRow("1. Öğretmen:", self.r_teacher)
        bl.addRow("2. Kural:", self.r_kind)
        bl.addRow("3. Ayrıntı:", self.r_fields)
        bl.addRow("", add)

        self.rules_t = QTableWidget(0, 2)
        self.rules_t.setHorizontalHeaderLabels(["Kural", "Açıklama"])
        U._stretch(self.rules_t, 1)
        self.rules_t.verticalHeader().hide()
        self.rules_t.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rules_t.setMinimumHeight(80)
        rem = variant(QPushButton("Seçili kuralı sil"), "danger")
        rem.clicked.connect(self._remove_rule)
        lst = QGroupBox("Eklenen kurallar")
        ll = QVBoxLayout(lst)
        ll.addWidget(self.rules_t, 1)
        ll.addWidget(rem, 0, Qt.AlignRight)
        hint = QLabel("Kural şart değil; kural yoksa doğrudan <b>İleri</b>'ye basın.")
        hint.setObjectName("subtitle")
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(hint)
        v.addWidget(builder)
        v.addWidget(lst, 1)
        self._kind_changed()
        return p

    def _kind_changed(self):
        kind = self.r_kind.currentData()
        self.r_fields.setCurrentIndex(self._field_of[kind])
        self.r_with_label.setText("Kiminle aynı gün:" if kind == "together"
                                  else "Kiminle aynı gün olmasın:")

    def _rule_teachers(self):
        c = self._collect()
        return sorted(c.teachers, key=normalize), [p for p, _n in c.places]

    def _prepare_rules_page(self):
        teachers, places = self._rule_teachers()
        for combo in (self.r_teacher, self.r_other):
            cur = combo.currentText()
            combo.clear()
            combo.addItems(teachers)
            combo.setCurrentText(cur if cur in teachers else "")
        self.r_place.clear()
        self.r_place.addItem("Fark etmez (yerler dönsün)", "")
        for p in places:
            self.r_place.addItem(p, p)

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
        self.grid.setMinimumHeight(140)
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
        self.rules = ([("exempt", [t, why]) for t, why in saved.exempt.items()] +
                      [("fixed", r) for r in saved.fixed] +
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
        self.teach_checks = []
        for r, t in enumerate(teachers):
            box = QCheckBox()
            box.setChecked(t in known or not known)
            box.setCursor(Qt.PointingHandCursor)
            cell = QWidget()
            ch = QHBoxLayout(cell)
            ch.setContentsMargins(0, 0, 0, 0)
            ch.addWidget(box, 0, Qt.AlignCenter)
            self.teach.setCellWidget(r, 0, cell)
            self.teach_checks.append(box)
            self.teach.setItem(r, 1, U._item(t))
            for d in range(5):
                n = lesson_count(self.schedule, t, d)
                it = U._item(n if n else "–")
                it.setTextAlignment(Qt.AlignCenter)
                if not n:
                    it.setForeground(QColor(theme.MUTED))
                self.teach.setItem(r, 2 + d, it)
        self.teach_info.setText(
            f"Ders programından {len(teachers)} öğretmen alındı (idareciler hariç). Nöbet "
            "tutmayacakların işaretini kaldırın. Muafiyetleri 4. adımda (Kurallar) mazeretiyle "
            "ekleyebilirsiniz.")
        names = ["—"] + sorted(admins, key=normalize)
        for d, c in enumerate(self.admin_combos):
            c.clear()
            c.addItems(names)
            c.setCurrentText(self.cfg.admins_by_day.get(str(d), "—"))

    def _check_all(self, on):
        for box in self.teach_checks:
            box.setChecked(on)

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
        c.teachers = []
        for r in range(self.teach.rowCount()):
            if self.teach_checks[r].isChecked():
                c.teachers.append(self.teach.item(r, 1).text())
        c.exempt = {r[0]: r[1] for k, r in self.rules if k == "exempt"}
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
        weekly = per_day * 5 * (2 if c.per_week >= 2 else 1)
        if per_day * 5 >= n:
            self.cap_info.setText(f"✅ Günde <b>{per_day}</b>, haftada <b>{per_day * 5}</b> nöbet yeri; "
                                  f"nöbet tutacak <b>{n}</b> öğretmen. Herkese haftada 1 nöbet düşer.")
            self.cap_info.setStyleSheet("")
            self.fit.setVisible(per_day * 5 - n >= 5)
            self.fit.setText("Yer sayısını öğretmen sayısına göre ayarla")
        else:
            self.cap_info.setText(f"⚠ Yer yetmiyor: haftada <b>{per_day * 5}</b> nöbet yeri var ama "
                                  f"<b>{n}</b> öğretmen nöbet tutacak. <b>{n - per_day * 5}</b> "
                                  "öğretmene bu ay nöbet düşmez. Kişi sayılarını artırın ya da "
                                  "aşağıdaki düğmeye basın.")
            self.cap_info.setStyleSheet("color:#dc2626; font-weight:600")
            self.fit.setVisible(True)
            self.fit.setText("Herkese haftada 1 nöbet yetecek kadar yer ayarla")
        del weekly

    def _fit_capacity(self):
        """Kişi sayılarını, herkese haftada tam 1 nöbet düşecek şekilde yerlere paylaştırır."""
        import math
        c = self._collect()
        n = len([t for t in c.teachers if t not in c.exempt])
        rows = self.places.rowCount()
        if not rows:
            return
        per_day = max(rows, math.ceil(n / 5))
        base, extra = divmod(per_day, rows)
        for r in range(rows):
            self.places.cellWidget(r, 1).setValue(base + (1 if r < extra else 0))
        self._update_capacity()

    def _fill_rules(self):
        self.rules_t.setRowCount(len(self.rules))
        for r, (k, rule) in enumerate(self.rules):
            self.rules_t.setItem(r, 0, U._item(RULE_KINDS[k]))
            self.rules_t.setItem(r, 1, U._item(rule_text(k, rule)))

    def _add_rule(self):
        teachers, _places = self._rule_teachers()
        t = self.r_teacher.currentText().strip()
        if t not in teachers:
            U._info(self, "Listeden bir öğretmen seçin.")
            return
        kind = self.r_kind.currentData()
        if kind == "fixed":
            rule = {"teacher": t, "day": self.r_day.currentIndex(),
                    "place": self.r_place.currentData()}
        elif kind == "exempt":
            rule = [t, self.r_reason.text().strip()]
        elif kind in ("together", "apart"):
            o = self.r_other.currentText().strip()
            if o not in teachers or o == t:
                U._info(self, "İkinci öğretmeni listeden seçin (aynı kişi olamaz).")
                return
            rule = [t, o]
        else:
            days = [i for i, c in enumerate(self.r_days) if c.isChecked()]
            if not days:
                U._info(self, "En az bir gün işaretleyin.")
                return
            rule = [t, days]
        # Aynı öğretmen için tek "sabitle", tek "muaf", tek "gün kısıtı" olur
        if kind in ("fixed", "exempt", "allowed"):
            def same(k, r):
                who = r["teacher"] if k == "fixed" else r[0]
                return k == kind and who == t
            self.rules = [(k, r) for k, r in self.rules if not same(k, r)]
        self.rules.append((kind, rule))
        self._fill_rules()
        self.r_teacher.setCurrentText("")
        self.r_reason.clear()
        for c in self.r_days:
            c.setChecked(False)

    def _remove_rule(self):
        r = self.rules_t.currentRow()
        if r >= 0:
            del self.rules[r]
            self._fill_rules()

    # ------------------------------------------------------------ elle düzenleme
    def _page_edit(self):
        self.edit_t = QTableWidget(0, 4)
        self.edit_t.setHorizontalHeaderLabels(["Öğretmen", "Nöbet günü", "O gün dersi",
                                               "Not"])
        U._stretch(self.edit_t, 0)
        self.edit_t.verticalHeader().hide()
        self.edit_t.setSelectionMode(QAbstractItemView.NoSelection)
        self.edit_t.setMinimumHeight(120)
        self.edit_info = QLabel()
        self.edit_info.setWordWrap(True)
        prt = QPushButton("🖨  Baskı önizleme")
        prt.clicked.connect(self.print_)
        h = QHBoxLayout()
        hint = QLabel("Dağıtımı beğenmediğiniz öğretmenin <b>nöbet gününü</b> buradan değiştirin; "
                      "yerler yeniden hesaplanır. Bitince <b>Kaydet ve kullan</b>'a basın.")
        hint.setWordWrap(True)
        h.addWidget(hint, 1)
        h.addWidget(prt)
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 0, 0, 0)
        v.addLayout(h)
        v.addWidget(self.edit_t, 1)
        v.addWidget(self.edit_info)
        return p

    def _fill_edit(self):
        if not self.result:
            return
        day_of = {t: d for d, ts in self.result.by_day.items() for t in ts}
        teachers = sorted(set(day_of) | set(self.result.unassigned),
                          key=lambda t: (day_of.get(t, 9), normalize(t)))
        self.edit_t.setRowCount(len(teachers))
        for r, t in enumerate(teachers):
            self.edit_t.setItem(r, 0, U._item(t))
            combo = QComboBox()
            combo.addItem("— nöbet yok —", None)
            for d, name in enumerate(DAYS):
                combo.addItem(name, d)
            combo.setCurrentIndex(day_of[t] + 1 if t in day_of else 0)
            combo.currentIndexChanged.connect(lambda _i, who=t, cb=combo: self._move(who, cb))
            self.edit_t.setCellWidget(r, 1, combo)
            d = day_of.get(t)
            self.edit_t.setItem(r, 2, U._item(f"{lesson_count(self.schedule, t, d)} ders"
                                              if d is not None else "—"))
            why = "" if d is not None else self.result.reasons.get(t, "Yer yetmedi")
            note = U._item(why)
            if why:
                note.setBackground(theme.YELLOW)
            self.edit_t.setItem(r, 3, note)

    def _move(self, teacher, combo):
        note = move_teacher(self.cfg, self.result, self.schedule, teacher, combo.currentData())
        self.edit_info.setText(f"<span style='color:#d97706'>⚠ {note}</span>" if note else
                               f"✅ {teacher} için nöbet günü güncellendi.")
        r = next(i for i in range(self.edit_t.rowCount()) if self.edit_t.item(i, 0).text() == teacher)
        d = combo.currentData()
        self.edit_t.setItem(r, 2, U._item(f"{lesson_count(self.schedule, teacher, d)} ders"
                                          if d is not None else "—"))
        self.edit_t.setItem(r, 3, U._item("Elle değiştirildi"))
        self._show_week(self.week.currentIndex())

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
        if index == 3:
            self._prepare_rules_page()
        if index == 4 and cur < 4:
            self.run()
        if index == 5:
            self._fill_edit()

    def run(self):
        c = self._collect()
        history = self.db.duty_history(c.month)
        # Gün yükü dengesi: bu yıl kim kaç boş derse girdi, hangi gün ne kadar yoğundu
        start = self.db.school_year_start(c.month + "-01")
        end = (U.dt.date.fromisoformat(c.month + "-01") - U.dt.timedelta(days=1)).isoformat()
        covered, demand = {}, {}
        if end >= start:
            stats = self.db.fairness_stats(start, end)
            covered = {t: v["assigned"] for t, v in stats.items() if t != "__meta__"}
            demand = {d: n / max(1, k) for d, (n, k) in
                      stats.get("__meta__", {}).get("weekday_load", {}).items()}
        self.result = distribute(c, self.schedule, history, covered, demand)
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
            groups = {}
            for t in self.result.unassigned:
                groups.setdefault(self.result.reasons.get(t, "Yer yetmedi"), []).append(t)
            for why, names in groups.items():
                lines.append(f"<b>Nöbet verilmeyenler — {why}:</b> " + ", ".join(names))
        lines.append("Beğenmezseniz <b>Yeniden dağıt</b>'a basın ya da <b>İleri</b> ile bir "
                     "sonraki adımda günleri elle değiştirin.")
        self.res_info.setText("<br>".join(lines))

    def _show_week(self, w):
        if not self.result or w < 0 or w >= len(self.result.weeks):
            return
        places = [p for p, _n in self.cfg.places]
        has_admin = any(e.place == ADMIN_PLACE for e in self.result.entries)
        cols = ["Gün"] + places + (["Nöbetçi idareci"] if has_admin else [])
        rows = []
        for date in self.result.weeks[w][1]:
            iso = date.isoformat()
            cells = [[e.teacher for e in self.result.entries if e.date == iso and e.place == p]
                     for p in places + ([ADMIN_PLACE] if has_admin else [])]
            rows.append((f"{DAYS[date.weekday()]}\n{date.strftime('%d.%m.%Y')}", cells))
        U.fill_duty_grid(self.grid, cols, rows)

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
