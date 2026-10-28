"""Excel ve yazdırma (HTML) çıktıları."""
import datetime as dt
import html

from .names import DAYS, normalize
from .scheduler import KIND_LABELS


def date_tr(date):
    d = dt.date.fromisoformat(date)
    months = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
              "Eylül", "Ekim", "Kasım", "Aralık"]
    day = DAYS[d.weekday()] if d.weekday() < 5 else ("Cumartesi", "Pazar")[d.weekday() - 5]
    return f"{d.day} {months[d.month - 1]} {d.year} {day}"


def month_tr(month):
    y, m = month.split("-")
    months = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
              "Eylül", "Ekim", "Kasım", "Aralık"]
    return f"{months[int(m) - 1]} {y}"


def day_html(plan, school=""):
    e = html.escape
    rows = []
    for a in plan.assignments:
        color = {"bos": "#fff4cc", "yok": "#ffd6d6"}.get(a.kind, "#ffffff")
        rows.append(
            f"<tr style='background:{color}'><td align=center>{a.hour}</td><td>{e(a.absent)}</td>"
            f"<td>{e(a.info)}</td><td><b>{e(a.assigned or '—')}</b></td>"
            f"<td>{e(KIND_LABELS.get(a.kind, a.kind))}</td><td>{e(a.note)}</td></tr>")
    absent = ", ".join(f"{e(t)} ({e(r)})" for t, r in sorted(plan.absences.items())) or "—"
    duty = ", ".join(f"{e(t)}" + (f" ({e(p)})" if p else "") for t, p in plan.duty) or "—"
    return f"""
<html><body style="font-family:Arial; font-size:10pt">
<h3 align=center>{e(school)}</h3>
<h3 align=center>DERS GÖREVLENDİRME ÇİZELGESİ — {e(date_tr(plan.date))}</h3>
<p><b>Gelmeyen öğretmenler:</b> {absent}<br><b>Nöbetçi öğretmenler:</b> {duty}</p>
<table border=1 cellspacing=0 cellpadding=4 width=100%>
<tr style='background:#dde4ee'><th>Saat</th><th>Gelmeyen Öğretmen</th><th>Sınıf / Ders</th>
<th>Görevlendirilen</th><th>Tür</th><th>Not</th></tr>
{''.join(rows) or '<tr><td colspan=6 align=center>Görevlendirme yok</td></tr>'}
</table>
<br><br><table width=100%><tr><td></td><td align=center width=30%>Müdür Yardımcısı</td>
<td align=center width=30%>Okul Müdürü</td></tr></table>
</body></html>"""


def save_day_xlsx(path, plan, school=""):
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Görevlendirme"
    ws.append([school])
    ws.append([f"Ders Görevlendirme Çizelgesi — {date_tr(plan.date)}"])
    ws.append([])
    ws.append(["Saat", "Gelmeyen Öğretmen", "Sınıf / Ders", "Görevlendirilen", "Tür", "Not"])
    for c in ws[4]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDE4EE")
    fills = {"bos": PatternFill("solid", fgColor="FFF4CC"), "yok": PatternFill("solid", fgColor="FFD6D6")}
    for a in plan.assignments:
        ws.append([a.hour, a.absent, a.info, a.assigned or "—", KIND_LABELS.get(a.kind, a.kind),
                   a.note])
        if a.kind in fills:
            for c in ws[ws.max_row]:
                c.fill = fills[a.kind]
    ws.append([])
    ws.append(["Gelmeyenler", ", ".join(f"{t} ({r})" for t, r in sorted(plan.absences.items()))])
    ws.append(["Nöbetçiler", ", ".join(t + (f" ({p})" if p else "") for t, p in plan.duty)])
    for col, w in zip("ABCDEF", (6, 24, 24, 24, 24, 60)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=5):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"].font = Font(bold=True)
    wb.save(path)


REPORT_HEADERS = ["Öğretmen", "Bu ay nöbet günü", "Toplam ders doldurma", "Nöbetçi olarak",
                  "Nöbetçi değilken", "Nöbet günü başına"]


def report_rows(counts, duty_days):
    teachers = sorted(set(counts) | set(duty_days))
    rows = []
    for t in teachers:
        tot, duty, free = counts.get(t, (0, 0, 0))
        days = duty_days.get(t, 0)
        rows.append([t, days, tot, duty, free, round(duty / days, 2) if days else ""])
    rows.sort(key=lambda r: (-r[1] if r[1] else 0, -r[2], normalize(r[0])))
    return rows


def save_report_xlsx(path, month, rows, school=""):
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Aylık Rapor"
    ws.append([school])
    ws.append([f"{month_tr(month)} Ders Doldurma Dağılımı"])
    ws.append([])
    ws.append(REPORT_HEADERS)
    for c in ws[4]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDE4EE")
    for r in rows:
        ws.append(r)
    for col, w in zip("ABCDEF", (28, 16, 20, 16, 18, 18)):
        ws.column_dimensions[col].width = w
    wb.save(path)


RECORDS_FILE = "Kayıtlar.xlsx"


def write_records_xlsx(path, db, school=""):
    """Tüm kayıtları tek bir Excel dosyasına yazar (her kayıttan sonra yenilenir).

    Dosya Excel'de açıkken yazılamaz; o durumda PermissionError yükselir ve veriler
    programın veritabanında güvende kalır, bir sonraki kayıtta yeniden denenir.
    """
    import os
    import tempfile

    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    head_fill = PatternFill("solid", fgColor="DDE4EE")
    fills = {"bos": PatternFill("solid", fgColor="FFF4CC"),
             "yok": PatternFill("solid", fgColor="FFD6D6")}

    def sheet(wb, title, headers, widths, first=False):
        ws = wb.active if first else wb.create_sheet()
        ws.title = title
        ws.append(headers)
        for c in ws[1]:
            c.font = Font(bold=True)
            c.fill = head_fill
        for i, w in enumerate(widths):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = w
        ws.freeze_panes = "A2"
        return ws

    wb = openpyxl.Workbook()
    ws = sheet(wb, "Görevlendirmeler",
               ["Tarih", "Gün", "Saat", "Gelmeyen Öğretmen", "Durumu", "Sınıf / Ders",
                "Görevlendirilen", "Tür", "Not"], [12, 11, 6, 26, 10, 22, 26, 24, 60], first=True)
    rows = db.conn.execute(
        "SELECT a.date, a.hour, a.absent_teacher, ab.reason, a.info, a.assigned, a.kind, a.note "
        "FROM assignments a LEFT JOIN absences ab ON ab.date = a.date "
        "AND ab.teacher = a.absent_teacher ORDER BY a.date, a.hour, a.absent_teacher").fetchall()
    for date, hour, absent, reason, info, assigned, kind, note in rows:
        d = dt.date.fromisoformat(date)
        ws.append([d, DAYS[d.weekday()] if d.weekday() < 5 else "", hour, absent, reason or "",
                   info or "", assigned or "—", KIND_LABELS.get(kind, kind or ""), note or ""])
        ws.cell(ws.max_row, 1).number_format = "DD.MM.YYYY"
        if kind in fills:
            for c in ws[ws.max_row]:
                c.fill = fills[kind]
    for row in ws.iter_rows(min_row=2):
        row[-1].alignment = Alignment(wrap_text=True, vertical="top")

    ws = sheet(wb, "Devamsızlık", ["Tarih", "Gün", "Öğretmen", "Durumu"], [12, 11, 28, 12])
    for date, teacher, reason in db.conn.execute(
            "SELECT date, teacher, reason FROM absences ORDER BY date, teacher"):
        d = dt.date.fromisoformat(date)
        ws.append([d, DAYS[d.weekday()] if d.weekday() < 5 else "", teacher, reason or ""])
        ws.cell(ws.max_row, 1).number_format = "DD.MM.YYYY"

    ws = sheet(wb, "Aylık Özet", ["Ay"] + REPORT_HEADERS, [14, 28, 16, 20, 16, 18, 18])
    months = [r[0] for r in db.conn.execute(
        "SELECT DISTINCT substr(date, 1, 7) FROM assignments ORDER BY 1 DESC")]
    for m in months:
        for r in report_rows(db.counts(m), db.duty_days_in_month(m)):
            ws.append([month_tr(m)] + r)

    ws = sheet(wb, "Ders Programı", ["Geçerlilik", "Öğretmen", "Gün", "Saat", "Sınıf / Ders"],
               [12, 28, 11, 6, 30])
    for vid, valid_from, *_ in db.schedule_versions():
        sched = db.schedule(vid)
        for t in sorted(sched, key=normalize):
            for (d, h), info in sorted(sched[t].items()):
                ws.append([dt.date.fromisoformat(valid_from), t, DAYS[d], h, info])
                ws.cell(ws.max_row, 1).number_format = "DD.MM.YYYY"

    ws = sheet(wb, "Nöbet Çizelgesi", ["Ay", "Tarih", "Gün", "Öğretmen", "Nöbet Yeri"],
               [14, 12, 11, 28, 18])
    for m, _n in db.duty_months():
        for wd, date, t, p in sorted(db.duty_rows(m), key=lambda r: (r[1] or "", r[0], r[3] or "")):
            ws.append([month_tr(m), dt.date.fromisoformat(date) if date else "Her hafta",
                       DAYS[wd], t, p or ""])
            if date:
                ws.cell(ws.max_row, 2).number_format = "DD.MM.YYYY"

    if school:
        wb.properties.title = f"{school} — Nöbetçi Öğretmen Görevlendirme Kayıtları"
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=folder)
    os.close(fd)
    try:
        wb.save(tmp)
        os.replace(tmp, path)  # Excel'de açıksa burada PermissionError
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
