import datetime as dt
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nobet.db import Database
from nobet.names import NameMatcher, parse_day
from nobet.parse_duty import parse_duty
from nobet.parse_schedule import parse_hour, parse_schedule
from nobet.reader import read_document
from nobet.scheduler import plan_day

DAYS = ["PAZARTESİ", "SALI", "ÇARŞAMBA", "PERŞEMBE", "CUMA"]


def test_days_and_hours():
    assert parse_day("PAZARTESİ") == 0
    assert parse_day("Çarş.") == 2
    assert parse_day("CUMARTESİ") is None
    assert parse_hour("1. Ders") == 1
    assert parse_hour("3") == 3
    assert parse_hour("08:30-09:10") == ("time", 510)
    assert parse_hour("Matematik") is None


def test_matcher():
    m = NameMatcher(["Ahmet YILMAZ", "Ayşe KAYA", "Mehmet Ali ÖZTÜRK"])
    assert m.match("AHMET YILMAZ") == "Ahmet YILMAZ"
    assert m.match("ayse kaya") == "Ayşe KAYA"
    assert m.match("A. YILMAZ") == "Ahmet YILMAZ"
    assert m.match("Mehmet ÖZTÜRK") == "Mehmet Ali ÖZTÜRK"
    assert m.find_all("Ahmet Yılmaz\nAyşe Kaya") == ["Ahmet YILMAZ", "Ayşe KAYA"]
    assert m.match("Zeynep DEMİR") is None


def _teacher_page(name, lessons):
    rows = [["Saat"] + DAYS]
    for h in range(1, 7):
        rows.append([f"{h}. Ders"] + [lessons.get((d, h), "") for d in range(5)])
    return {"text": f"ATATÜRK LİSESİ\nÖğretmen Adı Soyadı : {name}\nHaftalık Ders Programı",
            "tables": [rows]}


def test_teacher_pages():
    pages = [_teacher_page("Ahmet YILMAZ", {(0, 1): "9-A\nMAT", (0, 2): "9-B MAT"}),
             _teacher_page("Ayşe KAYA", {(1, 3): "10-A TDE"})]
    res = parse_schedule(pages)
    assert res.teachers["Ahmet YILMAZ"] == {(0, 1): "9-A MAT", (0, 2): "9-B MAT"}
    assert res.teachers["Ayşe KAYA"] == {(1, 3): "10-A TDE"}


def test_class_pages():
    rows = [["", *DAYS]]
    rows.append(["1", "MATEMATİK\nAhmet YILMAZ", "", "", "", ""])
    rows.append(["2", "TÜRK DİLİ VE EDEBİYATI\nAyşe KAYA", "", "", "", ""])
    pages = [{"text": "Sınıf : 9-A\n", "tables": [rows]}]
    res = parse_schedule(pages)
    assert res.teachers["Ahmet YILMAZ"][(0, 1)].startswith("9-A")
    assert (0, 2) in res.teachers["Ayşe KAYA"]


def test_carsaf():
    header1 = ["Öğretmen", "PAZARTESİ", None, None, "SALI", None, None]
    header2 = ["", "1", "2", "3", "1", "2", "3"]
    rows = [header1, header2,
            ["Ahmet YILMAZ", "9A", "", "9B", "", "", ""],
            ["Ayşe KAYA", "", "10A", "", "10B", "", ""]]
    res = parse_schedule([{"text": "", "tables": [rows]}])
    assert res.teachers["Ahmet YILMAZ"] == {(0, 1): "9A", (0, 3): "9B"}
    assert res.teachers["Ayşe KAYA"] == {(0, 2): "10A", (1, 1): "10B"}


def test_transposed_grid():
    rows = [["Gün", "1", "2", "3"],
            ["Pazartesi", "9A", "", "9C"],
            ["Salı", "", "10B", ""]]
    res = parse_schedule([{"text": "Ahmet YILMAZ\n", "tables": [rows]}])
    assert res.teachers["Ahmet YILMAZ"] == {(0, 1): "9A", (0, 3): "9C", (1, 2): "10B"}


def test_duty_rows_by_day():
    known = ["Ahmet YILMAZ", "Ayşe KAYA", "Can DEMİR"]
    rows = [["GÜN", "BAHÇE", "KORİDOR"],
            ["PAZARTESİ", "Ahmet YILMAZ", "Ayşe KAYA"],
            ["SALI", "Can DEMİR", "Zeynep ŞEN"]]
    res = parse_duty([{"text": "", "tables": [rows]}], known)
    got = {(e.weekday, e.teacher, e.place) for e in res.entries}
    # Programda olmayan isim de eklenir ama ayrıca bildirilir
    assert got == {(0, "Ahmet YILMAZ", "BAHÇE"), (0, "Ayşe KAYA", "KORİDOR"),
                   (1, "Can DEMİR", "BAHÇE"), (1, "Zeynep ŞEN", "KORİDOR")}
    assert res.unmatched == ["Zeynep ŞEN"]


def test_duty_cols_by_day():
    known = ["Ahmet YILMAZ", "Ayşe KAYA", "Can DEMİR"]
    rows = [["Nöbet Yeri", "Pazartesi", "Salı"],
            ["Bahçe", "Ahmet YILMAZ", "Ayşe KAYA\nCan DEMİR"]]
    res = parse_duty([{"text": "", "tables": [rows]}], known)
    got = {(e.weekday, e.teacher, e.place) for e in res.entries}
    assert got == {(0, "Ahmet YILMAZ", "Bahçe"), (1, "Ayşe KAYA", "Bahçe"),
                   (1, "Can DEMİR", "Bahçe")}


def test_duty_teacher_rows():
    known = ["Ahmet YILMAZ", "Ayşe KAYA"]
    rows = [["Öğretmen", "Pazartesi", "Salı", "Çarşamba"],
            ["Ahmet YILMAZ", "Bahçe", "", ""],
            ["Ayşe KAYA", "", "", "Kantin"]]
    res = parse_duty([{"text": "", "tables": [rows]}], known)
    got = {(e.weekday, e.teacher, e.place) for e in res.entries}
    assert got == {(0, "Ahmet YILMAZ", "Bahçe"), (2, "Ayşe KAYA", "Kantin")}


def test_duty_text_only():
    known = ["Ahmet YILMAZ", "Ayşe KAYA"]
    text = "NÖBET ÇİZELGESİ\nPazartesi: Ahmet YILMAZ, Ayşe KAYA\n"
    res = parse_duty([{"text": text, "tables": []}], known)
    assert {e.teacher for e in res.entries if e.weekday == 0} == {"Ahmet YILMAZ", "Ayşe KAYA"}


def test_duty_dates():
    known = ["Ahmet YILMAZ"]
    rows = [["Tarih", "Nöbetçi"], ["03.11.2026", "Ahmet YILMAZ"]]
    res = parse_duty([{"text": "", "tables": [rows]}], known)
    assert res.entries[0].date == "2026-11-03" and res.entries[0].weekday == 1


def _schedule():
    # Pazartesi; A gelmeyecek, dersleri 2. ve 4. saat
    return {
        "A": {(0, 2): "9-A MAT", (0, 4): "9-B MAT"},
        "N1": {(0, 1): "x", (0, 2): "x"},          # nöbetçi, 2. saatte dolu
        "N2": {(0, 3): "x"},                       # nöbetçi
        "N3": {(0, 5): "x"},                       # nöbetçi
        "B": {(0, 1): "x", (0, 3): "x"},           # nöbetçi değil
    }


def test_plan_prefers_duty_and_fairness():
    date = "2026-11-02"  # Pazartesi
    sched = _schedule()
    duty = [("N1", "Bahçe"), ("N2", "Koridor"), ("N3", "Kantin")]
    plan = plan_day(date, sched, duty, {"A": "Raporlu"}, {"N2": (3, 3, 0)}, {})
    by_hour = {a.hour: a for a in plan.assignments}
    # 2. saat: N1 dolu, N2 bu ay 3 kez girmiş -> N3
    assert by_hour[2].assigned == "N3" and by_hour[2].kind == "nobetci"
    # 4. saat: N1 (0) ile N3 (bugün 1) -> N1
    assert by_hour[4].assigned == "N1"


def test_plan_falls_back_to_free_teacher_with_note():
    date = "2026-11-02"
    sched = _schedule()
    sched["N2"] = {(0, 2): "x", (0, 4): "x"}
    duty = [("N1", ""), ("N2", "")]
    sched["N1"][(0, 4)] = "x"
    plan = plan_day(date, sched, duty, {"A": "İzinli"}, {}, {})
    by_hour = {a.hour: a for a in plan.assignments}
    assert by_hour[2].assigned == "B" and by_hour[2].kind == "bos"
    assert "nöbetçi değil" in by_hour[2].note
    assert "iki dersi arasında" in by_hour[2].note
    # 4. saat: B ve N3 boş, ikisi de pencere değil; bugün daha az giren N3 seçilir
    assert by_hour[4].assigned == "N3" and by_hour[4].kind == "bos"


def test_plan_unassigned():
    plan = plan_day("2026-11-02", {"A": {(0, 1): "9A"}}, [], {"A": "Görevli"}, {}, {})
    assert plan.assignments[0].assigned is None and plan.assignments[0].kind == "yok"


def test_db_roundtrip(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.save_schedule({"A": {(0, 1): "9A"}}, "2026-09-01")
    db.save_schedule({"A": {(0, 2): "9A"}}, "2026-11-15")
    v = db.schedule_version_for("2026-11-02")
    assert db.schedule(v) == {"A": {(0, 1): "9A"}}
    v = db.schedule_version_for("2026-11-20")
    assert db.schedule(v) == {"A": {(0, 2): "9A"}}
    from nobet.parse_duty import DutyEntry
    db.save_duty("2026-10", [DutyEntry(0, "N1", "Bahçe")])
    rows, month = db.duty_for("2026-11-02")
    assert rows == [("N1", "Bahçe")] and month == "2026-10"
    plan = plan_day("2026-11-02", {"A": {(0, 1): "9A"}, "N1": {}}, rows, {"A": "R"}, {}, {})
    db.save_day("2026-11-02", plan.absences, plan.assignments)
    assert db.counts("2026-11") == {"N1": (1, 1, 0)}
    assert db.counts("2026-11", exclude_date="2026-11-02") == {}


# ---- gerçek PDF dosyalarıyla uçtan uca ----

def _make_pdf(path, pages):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle

    font = "Helvetica"
    for cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(cand):
            pdfmetrics.registerFont(TTFont("TR", cand))
            font = "TR"
            break
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = font
    story = []
    for title, rows, spans in pages:
        for line in title.split("\n"):
            story.append(Paragraph(line, styles["Normal"]))
        t = Table(rows)
        st = [("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("FONTNAME", (0, 0), (-1, -1), font)]
        st += [("SPAN", a, b) for a, b in spans]
        t.setStyle(TableStyle(st))
        story += [t, PageBreak()]
    SimpleDocTemplate(path, pagesize=landscape(A4)).build(story)


@pytest.fixture
def has_font():
    if not any(os.path.exists(p) for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",)):
        pytest.skip("Türkçe font yok")


def test_pdf_teacher_pages(tmp_path, has_font):
    p = str(tmp_path / "program.pdf")
    pages = []
    for name, cells in [("Ahmet YILMAZ", {(1, 1): "9-A MAT"}), ("Ayşe KAYA", {(2, 3): "10-B TDE"})]:
        rows = [["Saat"] + DAYS]
        for h in range(1, 7):
            rows.append([f"{h}. Ders"] + [cells.get((h, d), "") for d in range(5)])
        pages.append((f"ATATÜRK ANADOLU LİSESİ\nÖğretmen Adı Soyadı : {name}", rows, []))
    _make_pdf(p, pages)
    res = parse_schedule(read_document(p))
    assert res.teachers["Ahmet YILMAZ"] == {(1, 1): "9-A MAT"}
    assert res.teachers["Ayşe KAYA"] == {(3, 2): "10-B TDE"}


def test_pdf_carsaf_and_duty(tmp_path, has_font):
    p = str(tmp_path / "carsaf.pdf")
    h1 = ["Öğretmen"] + sum([[d, "", ""] for d in DAYS], [])
    h2 = [""] + ["1", "2", "3"] * 5
    rows = [h1, h2,
            ["Ahmet YILMAZ"] + ["9A", "", ""] + [""] * 12,
            ["Ayşe KAYA"] + ["", "", ""] + ["", "10B", ""] + [""] * 9,
            ["Can DEMİR"] + ["", "", "11C"] + [""] * 12]
    spans = [((1 + 3 * i, 0), (3 + 3 * i, 0)) for i in range(5)]
    _make_pdf(p, [("ÇARŞAF PROGRAM", rows, spans)])
    res = parse_schedule(read_document(p))
    assert res.teachers["Ahmet YILMAZ"] == {(0, 1): "9A"}
    assert res.teachers["Ayşe KAYA"] == {(1, 2): "10B"}
    assert res.teachers["Can DEMİR"] == {(0, 3): "11C"}

    d = str(tmp_path / "nobet.pdf")
    rows = [["GÜN", "BAHÇE", "1. KAT"],
            ["PAZARTESİ", "Ahmet Yılmaz", "Ayşe Kaya"],
            ["SALI", "Can Demir", ""]]
    _make_pdf(d, [("KASIM AYI NÖBET ÇİZELGESİ", rows, [])])
    duty = parse_duty(read_document(d), list(res.teachers))
    got = {(e.weekday, e.teacher) for e in duty.entries}
    assert got == {(0, "Ahmet YILMAZ"), (0, "Ayşe KAYA"), (1, "Can DEMİR")}


def test_daily_cap_moves_to_free_teacher():
    sched = {"A": {(0, 1): "9A", (0, 2): "9A", (0, 3): "9A"},
             "N": {}, "B": {(0, 4): "x"}}
    plan = plan_day("2026-11-02", sched, [("N", "")], {"A": "R"}, {}, {}, max_per_day=2)
    got = [(a.assigned, a.kind) for a in plan.assignments]
    assert got == [("N", "nobetci"), ("N", "nobetci"), ("B", "bos")]
    assert "sınırına ulaştığı" in plan.assignments[2].note
    # B de olmasa sınır aşılır ama ders boş kalmaz
    plan = plan_day("2026-11-02", {k: v for k, v in sched.items() if k != "B"}, [("N", "")],
                    {"A": "R"}, {}, {}, max_per_day=2)
    assert [a.assigned for a in plan.assignments] == ["N", "N", "N"]


# ---- e-Okul "Toplu Çarşaf Liste" benzeri: öğle arası, toplam sütunu, kutu çizilmiş blok dersler

def _font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("TR", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    return "TR"


def _carsaf_boxes_pdf(path, teachers):
    """teachers: [(ad, [(gün, ilk_saat, saat_sayısı, metin)], toplam)]"""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    font = _font()
    c = canvas.Canvas(path, pagesize=landscape(A4))
    W, H = landscape(A4)
    x0, cw, rh = 20, 18, 14
    cols = []  # (gün, saat or None)
    for d in range(5):
        for h in (1, 2, 3, 4, None, 5, 6, 7):
            cols.append((d, h))
    name_w = 80
    xs = [x0 + name_w + i * cw for i in range(len(cols) + 1)]
    top = H - 60
    c.setFont(font, 6)
    c.drawString(x0, H - 30, "Toplu Çarşaf Liste : Öğretmenler")
    rows = 2 + len(teachers)
    ys = [top - i * rh for i in range(rows + 1)]
    for y in ys:
        c.line(x0, y, xs[-1] + 20, y)
    for i, x in enumerate([x0] + xs + [xs[-1] + 20]):
        # Başlıkta gün adları birleşik hücre: yalnızca gün sınırlarında çizgi
        day_edge = i == 0 or (i - 1) % 8 == 0 or i >= len(xs)
        c.line(x, ys[0] if day_edge else ys[1], x, ys[-1])
    for d in range(5):
        c.drawString(xs[d * 8] + 2, ys[0] - 9, DAYS[d])
    for i, (d, h) in enumerate(cols):
        c.drawString(xs[i] + 2, ys[1] - 9, str(h) if h else "Öğle")
    c.drawString(xs[-1] + 2, ys[0] - 9, "Toplam")
    for r, (name, lessons, total) in enumerate(teachers):
        y = ys[2 + r]
        c.drawString(x0 + 2, y - 9, name)
        c.drawString(xs[-1] + 2, y - 9, str(total))
        for d, first, n, text in lessons:
            i = cols.index((d, first))
            j = i + n  # blok ders öğle arasına taşmaz
            c.setFillColorRGB(1, 1, 1)
            c.rect(xs[i], y - rh, xs[j] - xs[i], rh, fill=1, stroke=1)
            c.setFillColorRGB(0, 0, 0)
            mid = (xs[i] + xs[j]) / 2
            c.drawCentredString(mid, y - 9, text)
    c.save()


@pytest.mark.usefixtures("has_font")
def test_carsaf_block_lessons_drawn_as_boxes(tmp_path):
    p = str(tmp_path / "carsaf.pdf")
    _carsaf_boxes_pdf(p, [
        ("Ali VELİ", [(0, 2, 3, "7/C"), (0, 5, 1, "8/A"), (2, 6, 2, "5B")], 6),
        ("Ece SU", [(1, 1, 2, "6/D"), (4, 7, 1, "9A")], 3),
    ])
    res = parse_schedule(read_document(p))
    assert sorted(res.teachers["Ali VELİ"]) == [(0, 2), (0, 3), (0, 4), (0, 5), (2, 6), (2, 7)]
    assert sorted(res.teachers["Ece SU"]) == [(1, 1), (1, 2), (4, 7)]
    assert res.teachers["Ali VELİ"][(0, 3)] == "7/C"


def test_carsaf_merged_cells_and_lunch_column():
    # Birleştirilmiş hücre (None) soldaki dersi sürdürür; "Öğle Arası" sütunu saat değildir.
    h1 = ["", "Pazartesi", None, None, None, None, "Salı", None, None, None, None, "Toplam"]
    h2 = [None, "1", "2", "Öğle Arası", "3", "4", "1", "2", "Öğle Arası", "3", "4", None]
    rows = [h1, h2,
            ["Ali VELİ", "9A", None, None, None, "", "", "", None, "10B", "", "4"],
            [None] * 12,
            ["Ece SU", "", "", None, "", "", "8C", "", None, "", "", "1"]]
    res = parse_schedule([{"text": "", "tables": [rows]}])
    assert sorted(res.teachers["Ali VELİ"]) == [(0, 1), (0, 2), (0, 3), (1, 3)]
    assert res.teachers["Ece SU"] == {(1, 1): "8C"}


def test_grid_vertical_merged_block():
    rows = [["Saat"] + DAYS,
            ["1", "9A MAT", "", "", "", ""],
            ["2", None, "", "", "", ""],
            ["3", "", "", "", "", ""]]
    res = parse_schedule([{"text": "Öğretmen Adı Soyadı : Ali VELİ", "tables": [rows]}])
    assert res.teachers["Ali VELİ"] == {(0, 1): "9A MAT", (0, 2): "9A MAT"}


def test_weekly_duty_chart_with_numbers_admin_and_holiday():
    known = ["Ali VELİ", "Ece SU", "Can ER", "Ümmü GÜLSÜM KAYA", "Naz AK"]
    hdr = ["GÜNLER", "BAHÇE", None, "ZEMİN KAT", None, "N.İDARECİ"]
    t1 = [["X ORTAOKULU 2026 YILI EKİM AYI NÖBET ÇİZELGESİ", None, None, None, None, None],
          ["05-09 EKİM", None, None, None, None, None], hdr,
          ["PAZARTESİ", "1", "ALİ VELİ", "1", "ECE SU", "NAZ AK"],
          [None, "2", "ÜMMÜGÜLSÜM KAYA", "", "", None],
          ["SALI", "1", "CAN ER", "1", "ZEYNEP YOK", "NAZ AK"]]
    t2 = [["26-30 EKİM", None, None, None, None, None], hdr,
          ["PAZARTESİ", "1", "ECE SU", "1", "ALİ VELİ", "NAZ AK"],
          ["PERŞEMBE", "29 EKİM CUMHURİYET BAYRAMI", None, None, None, "NAZ AK"]]
    res = parse_duty([{"text": "X ORTAOKULU 2026 YILI", "tables": [t1, t2]}], known)
    got = {(e.date, e.teacher, e.place) for e in res.entries}
    assert ("2026-10-05", "Ali VELİ", "BAHÇE") in got
    assert ("2026-10-05", "Ümmü GÜLSÜM KAYA", "BAHÇE") in got
    assert ("2026-10-05", "Naz AK", "N.İDARECİ") in got
    assert ("2026-10-06", "ZEYNEP YOK", "ZEMİN KAT") in got
    assert ("2026-10-26", "Ali VELİ", "ZEMİN KAT") in got
    assert {e.teacher for e in res.entries if e.date == "2026-10-29"} == {"Naz AK"}
    assert res.unmatched == ["ZEYNEP YOK"]
    from nobet.parse_duty import is_admin_place, week_monday
    assert is_admin_place("N.İDARECİ") and not is_admin_place("BAHÇE")
    assert week_monday("28 EKİM - 01 KASIM", 2026).isoformat() == "2026-10-26"
    assert week_monday("28-01 KASIM", 2026).isoformat() == "2026-10-26"
    assert week_monday("05.10.2026 - 09.10.2026", 2026).isoformat() == "2026-10-05"


def test_duty_nearest_week_fallback(tmp_path):
    from nobet.parse_duty import DutyEntry
    db = Database(str(tmp_path / "t.db"))
    db.save_duty("2026-10", [DutyEntry(0, "A", "Bahçe", "2026-10-05"),
                             DutyEntry(0, "B", "Bahçe", "2026-10-26")])
    assert db.duty_for("2026-10-26")[0] == [("B", "Bahçe")]
    assert db.duty_for("2026-10-12")[0] == [("A", "Bahçe")]   # çizelgede olmayan hafta
    assert db.duty_for("2026-11-02")[0] == [("B", "Bahçe")]   # yeni ay yüklenmedi


def test_admins_never_assigned_and_split_blocks(tmp_path):
    sched = {"A": {(0, 1): "9A"}, "IDARECI": {(0, 2): "x"}, "B": {(0, 3): "x"}}
    plan = plan_day("2026-11-02", sched, [("IDARECI", "N.İDARECİ")], {"A": "R"}, {}, {},
                    excluded={"IDARECI"})
    assert plan.assignments[0].assigned == "B" and plan.assignments[0].kind == "bos"
    only_admin = plan_day("2026-11-02", {"A": {(0, 1): "9A"}, "IDARECI": {(0, 2): "x"}}, [],
                          {"A": "R"}, {}, {}, excluded={"IDARECI"})
    assert only_admin.assignments[0].assigned is None
    # İdareci otomatik seçilmez ama elle seçim listesinde "idareci" etiketiyle yer alır
    assert ("IDARECI", "idareci") in plan.assignments[0].options
    from nobet.parse_duty import DutyEntry
    db = Database(str(tmp_path / "t.db"))
    db.save_duty("2026-10", [DutyEntry(0, "IDARECI", "N.İDARECİ"), DutyEntry(0, "N", "Bahçe")])
    assert db.admins() == {"IDARECI"}
    db.set_admins({"IDARECI", "X"})
    assert db.admins() == {"IDARECI", "X"}
    db.set_admins({"X"})
    assert db.admins() == {"X"}
    db.reset_all()
    assert db.duty_months() == [] and db.schedule_versions() == []
    from nobet.parse_schedule import ScheduleResult, _join_split_blocks
    r = ScheduleResult()
    r.teachers = {"T": {(0, 1): "TÜRKÇE", (0, 2): "5A", (0, 4): "7/D Yazarlık"}}
    _join_split_blocks(r)
    assert r.teachers["T"][(0, 1)] == r.teachers["T"][(0, 2)] == "5A TÜRKÇE"


# ---- Nöbetmatik

def _sched(n=12):
    """n öğretmen; her biri her gün 4 ders, ama T0 Pazartesi 7 ders (tam dolu), T1 Salı dersi yok."""
    s = {}
    for i in range(n):
        t = f"T{i}"
        s[t] = {(d, h): "x" for d in range(5) for h in range(1, 5)}
    s["T0"].update({(0, h): "x" for h in range(1, 8)})
    for h in range(1, 5):
        del s["T1"][(1, h)]
    return s


def test_nobetmatik_basic_capacity_and_rotation():
    from nobet.nobetmatik import Config, distribute
    sched = _sched(8)
    cfg = Config(month="2026-11", teachers=sorted(sched), places=[["Bahçe", 1], ["Zemin", 1]])
    res = distribute(cfg, sched)
    # 8 öğretmen, günde 2 yer -> her gün en fazla 2 kişi, herkes tam 1 gün
    assert all(len(v) <= 2 for v in res.by_day.values())
    assert sorted(t for v in res.by_day.values() for t in v) == sorted(sched)
    assert "T1" not in res.by_day[1]          # dersi olmayan güne nöbet yok
    # Yerler haftalık değişir
    t = res.by_day[[d for d in range(5) if res.by_day[d]][0]][0]
    places = [e.place for e in sorted(res.entries, key=lambda e: e.date) if e.teacher == t]
    assert len(set(places)) == 2 and places[0] != places[1]
    # Kasım 2026: 5 hafta (2-6, 9-13, 16-20, 23-27, 30)
    assert len(res.weeks) == 5


def test_nobetmatik_rules():
    from nobet.nobetmatik import Config, distribute
    sched = _sched(10)
    cfg = Config(month="2026-11", teachers=sorted(sched), places=[["Bahçe", 2], ["Zemin", 1]],
                 exempt={"T9": "Sağlık raporu"},
                 fixed=[{"teacher": "T2", "day": 3, "place": "Zemin"}],
                 together=[["T3", "T4"]], apart=[["T5", "T6"]],
                 allowed_days={"T7": [4]}, admins_by_day={"0": "IDARECI"})
    res = distribute(cfg, sched)
    day = {t: d for d, ts in res.by_day.items() for t in ts}
    assert "T9" not in day                                   # muaf
    assert day["T2"] == 3                                    # sabit gün
    assert all(e.place == "Zemin" for e in res.entries if e.teacher == "T2")   # sabit yer
    assert day["T3"] == day["T4"]                            # beraber
    assert day["T5"] != day["T6"]                            # ayrı
    assert day["T7"] == 4                                    # gün kısıtı
    assert day.get("T0") != 0                                # tam dolu gün tercih edilmez
    assert {e.place for e in res.entries if e.teacher == "IDARECI"} == {"N.İDARECİ"}
    assert all(e.weekday == 0 for e in res.entries if e.teacher == "IDARECI")


def test_nobetmatik_shortage_gives_everyone_duty():
    """Yer yetmese de kimse dışarıda kalmaz; fazladan kişiler yerlere eklenir."""
    from nobet.nobetmatik import Config, distribute
    sched = _sched(7)
    cfg = Config(month="2026-11", teachers=sorted(sched), places=[["Bahçe", 1]])
    res = distribute(cfg, sched, {"T5": 9, "T6": 8})
    assigned = {t for v in res.by_day.values() for t in v}
    assert assigned == set(sched) and not res.unassigned
    assert all(e.place == "Bahçe" for e in res.entries)


def test_nobetmatik_fixed_place_any_day_and_admins():
    from nobet.nobetmatik import ADMIN_PLACE, Config, distribute, distribute_admins
    sched = _sched(10)
    cfg = Config(month="2026-11", teachers=sorted(sched), places=[["Bahçe", 1], ["Kantin", 1]],
                 fixed=[{"teacher": "T3", "day": None, "place": "Kantin"}],
                 admins=["A1", "A2"])
    res = distribute(cfg, sched)
    t3 = [e for e in res.entries if e.teacher == "T3"]
    assert t3 and all(e.place == "Kantin" for e in t3)
    by_admin = {}
    for a in cfg.admins_by_day.values():
        by_admin[a] = by_admin.get(a, 0) + 1
    assert sorted(by_admin.values()) == [2, 3]
    assert any(e.place == ADMIN_PLACE for e in res.entries)
    assert distribute_admins([], sched) == {}

def test_nobetmatik_two_per_week_fills_slots():
    from nobet.nobetmatik import Config, distribute
    sched = _sched(4)
    cfg = Config(month="2026-11", teachers=sorted(sched), places=[["Bahçe", 1]], per_week=2)
    res = distribute(cfg, sched)
    counts = {}
    for d, ts in res.by_day.items():
        for t in ts:
            counts[t] = counts.get(t, 0) + 1
    assert sum(counts.values()) == 5 and max(counts.values()) == 2


def test_yearly_fairness_carries_over_months(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    sched = {"A": {(0, 1): "9A", (0, 2): "9A"}, "N1": {}, "N2": {}}
    # Ekim: N1 iki derse girmiş
    oct_plan = plan_day("2026-10-05", sched, [("N1", ""), ("N2", "")], {"A": "R"}, {}, {})
    for a in oct_plan.assignments:
        a.assigned, a.kind = "N1", "nobetci"
    db.save_day("2026-10-05", oct_plan.absences, oct_plan.assignments)
    year = db.year_counts("2026-11-02", exclude_date="2026-11-02")
    assert year["N1"][0] == 2 and db.counts("2026-11") == {}
    nov = plan_day("2026-11-02", sched, [("N1", ""), ("N2", "")], {"A": "R"}, {}, {},
                   year_counts=year)
    # Kasım'da aylık sayılar sıfır olsa da N2 önce gelir (yıllık adalet)
    assert nov.assignments[0].assigned == "N2"
    assert Database.school_year_start("2027-03-10") == "2026-09-01"
    assert Database.school_year_start("2026-09-01") == "2026-09-01"


def test_nobetmatik_config_roundtrip_keeps_options():
    from nobet.nobetmatik import Config
    c = Config.from_dict({"rotate": True, "skip_free_days": False, "places": [["Bahçe", 3]]})
    d = Config.from_dict(c.to_dict())
    assert d.rotate is True and d.skip_free_days is False and d.places == [["Bahçe", 3]]


def test_nobetmatik_manual_move():
    from nobet.nobetmatik import Config, distribute, move_teacher
    sched = _sched(6)
    cfg = Config(month="2026-11", teachers=sorted(sched), places=[["Bahçe", 1], ["Zemin", 1]])
    res = distribute(cfg, sched)
    note = move_teacher(cfg, res, sched, "T1", 1)          # T1'in Salı dersi yok
    assert "dersi olmadığı" in note and "T1" in res.by_day[1]
    assert {e.weekday for e in res.entries if e.teacher == "T1"} == {1}
    move_teacher(cfg, res, sched, "T1", None)
    assert "T1" in res.unassigned and not any(e.teacher == "T1" for e in res.entries)


def test_fairness_stats_and_verdict(tmp_path):
    from nobet.parse_duty import DutyEntry
    from nobet import export
    db = Database(str(tmp_path / "t.db"))
    # N1 boş, N2'nin 1. saatte dersi var
    db.save_schedule({"A": {(0, 1): "9A", (0, 2): "9A"}, "N1": {(0, 5): "x"},
                      "N2": {(0, 1): "x", (0, 5): "x"}}, "2026-09-01")
    db.save_duty("2026-11", [DutyEntry(0, "N1", "Bahçe"), DutyEntry(0, "N2", "Zemin")])
    sched = db.schedule(db.schedule_version_for("2026-11-02"))
    plan = plan_day("2026-11-02", sched, [("N1", ""), ("N2", "")], {"A": "R"}, {}, {})
    db.save_day("2026-11-02", plan.absences, plan.assignments)
    st = db.fairness_stats("2026-11-02", "2026-11-02")
    assert st["N1"]["chances"] == 2 and st["N2"]["chances"] == 1      # N2 1. saatte derste
    assert st["N1"]["assigned"] + st["N2"]["assigned"] == 2
    assert st["N1"]["days"] == st["N2"]["days"] == 1
    verdict, _c, _l = export.fairness_summary(st)
    assert verdict.startswith("✅") and st["__meta__"]["exceptions"] == []
    # Elle kural dışı seçim yapılırsa rapor bunu açıkça söyler
    a = plan.assignments
    a[0].assigned = a[1].assigned = "N1"
    db.save_day("2026-11-02", plan.absences, a)
    st = db.fairness_stats("2026-11-02", "2026-11-02")
    verdict, _c, _l = export.fairness_summary(st)
    assert verdict.startswith("⚠") and len(st["__meta__"]["exceptions"]) == 1


def test_same_day_running_count_spreads_lessons():
    # A base 0, B base 1; 3 boş ders, ikisi de hep boş: güncel toplamla A,B,A gibi dağılmalı
    sched = {"X": {(0, 1): "9A", (0, 2): "9A", (0, 3): "9A"}, "A": {}, "B": {}}
    plan = plan_day("2026-11-02", sched, [("A", ""), ("B", "")], {"X": "R"}, {}, {},
                    year_counts={"B": (1, 1, 0)})
    got = [a.assigned for a in sorted(plan.assignments, key=lambda a: a.hour)]
    assert got.count("A") == 2 and got.count("B") == 1


def test_nobetmatik_moves_heavy_coverers_to_quiet_days():
    from nobet.nobetmatik import Config, distribute
    sched = _sched(10)
    cfg = Config(month="2026-11", teachers=sorted(sched), places=[["Bahçe", 2]],
                 prefer_light_days=False)
    demand = {0: 5.0, 1: 0.5, 2: 0.5, 3: 0.5, 4: 0.5}         # Pazartesi çok yoğun
    res = distribute(cfg, sched, covered={"T5": 9, "T6": 9}, demand=demand)
    day = {t: d for d, ts in res.by_day.items() for t in ts}
    assert day["T5"] != 0 and day["T6"] != 0


def test_nobetmatik_rules_override_free_days():
    from nobet.nobetmatik import Config, distribute
    sched = _sched(6)          # T1'in Salı dersi yok
    cfg = Config(month="2026-11", teachers=sorted(sched), places=[["Bahçe", 2]],
                 fixed=[{"teacher": "T1", "day": 1, "place": ""}])
    res = distribute(cfg, sched)
    assert "T1" in res.by_day[1]                    # kural, "dersi olmayan gün" seçeneğinden önce
    cfg = Config(month="2026-11", teachers=sorted(sched), places=[["Bahçe", 1]])
    res = distribute(cfg, sched)
    assert all(res.reasons.get(t) for t in res.unassigned)


def test_jokers_used_before_other_teachers():
    from nobet.scheduler import plan_day
    # A gelmedi (1. saat dersi var); nöbetçi N o saatte dolu; J joker; O başka boş öğretmen
    sched = {"A": {(0, 1): "6/A MAT"}, "N": {(0, 1): "7/B FEN"}, "O": {(0, 2): "5/C TÜR"}}
    plan = plan_day("2026-11-02", sched, [("N", "Bahçe")], {"A": "Raporlu"}, {}, {},
                    jokers=["J"])
    a = plan.assignments[0]
    assert a.assigned == "J" and a.kind == "joker"
    assert [t for t, lab in a.options if lab == "joker"] == ["J"]


def test_delete_single_absent_teacher(tmp_path):
    from nobet.db import Database
    from nobet.scheduler import Assignment
    db = Database(str(tmp_path / "v.db"))
    db.save_day("2026-11-02", {"A": "Raporlu", "B": "İzinli"},
                [Assignment(1, "A", "6/A", "X", "nobetci"), Assignment(2, "B", "7/A", "Y", "nobetci")])
    db.delete_absent("2026-11-02", "A")
    assert db.absences("2026-11-02") == {"B": "İzinli"}
    assert [r[1] for r in db.assignments("2026-11-02")] == ["B"]
    db.set_jokers("2026-11-02", ["J", "K"])
    assert db.jokers("2026-11-02") == ["J", "K"]


def test_joker_daily_limit_then_others():
    from nobet.scheduler import JOKER_MAX, plan_day
    # A'nın 8 dersi var, nöbetçi yok; joker J en fazla JOKER_MAX ders alır, kalan O'ya gider
    sched = {"A": {(0, h): f"6/A D{h}" for h in range(1, 9)}, "O": {(0, 9): "5/A X"}}
    plan = plan_day("2026-11-02", sched, [], {"A": "Raporlu"}, {}, {}, jokers=["J"])
    kinds = [a.kind for a in sorted(plan.assignments, key=lambda a: a.hour)]
    assert kinds.count("joker") == JOKER_MAX
    assert kinds[-1] == "bos" and plan.assignments[-1].assigned == "O"


def test_teacher_programs_show_own_and_tasks():
    from nobet.export import programs_html, teacher_programs
    from nobet.scheduler import plan_day
    sched = {"A": {(0, 1): "6/A MAT", (0, 2): "6/B MAT"}, "N": {(0, 3): "7/C FEN"}}
    plan = plan_day("2026-11-02", sched, [("N", "Bahçe")], {"A": "Raporlu"}, {}, {})
    n, rows = teacher_programs(plan, sched)
    assert n >= 7 and rows[0][0] == "N"
    cells = rows[0][1]
    assert cells[1][0] == "task" and cells[2][0] == "task" and cells[3] == ("own", "7/C FEN")
    assert "A yerine" in cells[1][1]
    assert "GÜNLÜK PROGRAMI" in programs_html(plan, sched)
