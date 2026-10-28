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
