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
    assert got == {(0, "Ahmet YILMAZ", "BAHÇE"), (0, "Ayşe KAYA", "KORİDOR"),
                   (1, "Can DEMİR", "BAHÇE")}
    assert "Zeynep ŞEN" in res.unmatched


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
