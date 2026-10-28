"""Nöbet çizelgesi ayrıştırıcı.

Çizelgedeki isimler ders programındaki öğretmen listesiyle eşleştirilir. Desteklenenler:
  - Satırlarda gün (veya tarih), sütunlarda nöbet yeri, hücrelerde öğretmen adları
  - Sütunlarda gün, satırlarda nöbet yeri
  - Satırlarda öğretmen, sütunlarda gün, hücrelerde nöbet yeri
  - Haftalara bölünmüş çizelgeler ("05-09 EKİM", "05.10.2026 - 09.10.2026" başlıkları)
  - Tablosuz metin: "Pazartesi: Ahmet YILMAZ, Ayşe KAYA" gibi satırlar
Ders programında bulunmayan isimler de eklenir ama `unmatched` listesinde bildirilir.
"""
import datetime as dt
import re
from dataclasses import dataclass, field

from .names import NameMatcher, clean_name, looks_like_person, normalize, parse_day, tr_lower

_DATE_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
_MONTHS = ["ocak", "subat", "mart", "nisan", "mayis", "haziran", "temmuz", "agustos", "eylul",
           "ekim", "kasim", "aralik"]
_MONTH_RE = "(" + "|".join(_MONTHS) + r")[a-z]*"
# "05-09 EKİM", "28 EKİM - 01 KASIM", "5 - 9 Ekim 2026"
_WEEK_RE = re.compile(r"\b(\d{1,2})\s*(?:" + _MONTH_RE + r")?\s*[-–]\s*(\d{1,2})\s*" + _MONTH_RE)
# İsim gibi görünen ama isim olmayan ifadeler (tatil, yer adları, başlıklar)
_NOT_NAME = {"bayram", "bayrami", "tatil", "tatili", "resmi", "gunu", "haftasi", "hafta", "nobet",
             "nobetci", "nobeti", "idareci", "bahce", "kat", "kati", "kantin", "koridor", "toren",
             "ogle", "arasi", "okul", "okulu", "mudur", "muduru", "yardimcisi", "sinav", "izin",
             "seminer", "gunler", "yeri", "ortaokulu", "lisesi", "cizelgesi", "zemin", "giris",
             "cikis", "bina", "blok", "salon", "yemekhane", "kapi", "merdiven", "bayramlari"}


@dataclass
class DutyEntry:
    weekday: int
    teacher: str
    place: str = ""
    date: str = None  # ISO tarih; yalnızca çizelge tarih/hafta bazlıysa


@dataclass
class DutyResult:
    entries: list = field(default_factory=list)
    unmatched: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def add(self, weekday, teacher, place="", date=None):
        e = DutyEntry(weekday, teacher, clean_name(place), date)
        if not any(x.weekday == e.weekday and x.teacher == e.teacher and x.date == e.date
                   for x in self.entries):
            self.entries.append(e)

    def note_unmatched(self, text):
        t = clean_name(text)
        if t and t not in self.unmatched:
            self.unmatched.append(t)


def is_admin_place(place):
    """Nöbetçi idareci / müdür yardımcısı sütunu mu?"""
    n = normalize(place)
    return "idareci" in n or "mudur" in n or n in ("n i", "ni")


def _key(text):
    """Hücreden (gün, tarih) çıkarır."""
    if text is None:
        return None
    s = str(text)
    m = _DATE_RE.search(s)
    if m and len(_DATE_RE.findall(s)) == 1:
        d, mo, y = (int(x) for x in m.groups())
        if y < 100:
            y += 2000
        try:
            date = dt.date(y, mo, d)
        except ValueError:
            date = None
        if date and date.weekday() < 5:
            return (date.weekday(), date.isoformat())
    day = parse_day(s.split("\n")[0])
    if day is None:
        # "03.11.2026\nPazartesi" gibi ikinci satırda gün olabilir
        for line in s.split("\n")[1:]:
            day = parse_day(line)
            if day is not None:
                break
    if day is not None:
        return (day, None)
    return None


def week_monday(text, year):
    """Hafta başlığından o haftanın Pazartesi tarihini çıkarır; başlık değilse None."""
    if not text:
        return None
    s = str(text)
    dates = _DATE_RE.findall(s)
    if len(dates) >= 2:
        d, mo, y = (int(x) for x in dates[0])
        y = y + 2000 if y < 100 else y
    else:
        n = tr_lower(s).translate(str.maketrans("çğıöşü", "cgiosu"))
        m = _WEEK_RE.search(n)
        if not m:
            return None
        d1, mon1, d2, mon2 = m.groups()
        mo = _MONTHS.index(mon1 or mon2) + 1
        if not mon1 and int(d1) > int(d2):  # "28-01 KASIM": hafta önceki ayda başlıyor
            mo = mo - 1 or 12
        d, y = int(d1), year
        ym = re.search(r"\b(20\d{2})\b", s)
        if ym:
            y = int(ym.group(1))
    try:
        start = dt.date(y, mo, d)
    except ValueError:
        return None
    return start - dt.timedelta(days=start.weekday())


def _txt(v):
    return "" if v is None else str(v).strip()


def _year_of(pages):
    for p in pages:
        m = re.search(r"\b(20\d{2})\b", p.get("text", "") or "")
        if m:
            return int(m.group(1))
    return dt.date.today().year


def parse_duty(pages, known_teachers):
    res = DutyResult()
    matcher = NameMatcher(known_teachers)
    if not matcher.names:
        res.warnings.append("Önce ders programını yükleyin; nöbet çizelgesindeki isimler "
                            "ders programındaki öğretmenlerle eşleştirilir.")
    ctx = {"year": _year_of(pages), "week": None, "header": None}
    any_table = False
    for page in pages:
        for table in page.get("tables", []):
            if table and _parse_table(table, matcher, res, ctx):
                any_table = True
    if not any_table:
        ctx["week"] = None
        for page in pages:
            _parse_text(page.get("text", ""), matcher, res, ctx)
    if not res.entries:
        res.warnings.append("Çizelgede gün/tarih ile eşleşen öğretmen bulunamadı.")
    if any(e.date for e in res.entries):
        weeks = sorted({_monday(e.date) for e in res.entries if e.date})
        res.warnings.insert(0, f"Haftalık çizelge algılandı: {len(weeks)} hafta "
                               f"({weeks[0].strftime('%d.%m')} – "
                               f"{(weeks[-1] + dt.timedelta(days=4)).strftime('%d.%m.%Y')}).")
    return res


def _monday(iso):
    d = dt.date.fromisoformat(iso)
    return d - dt.timedelta(days=d.weekday())


def _person(part):
    if not looks_like_person(part):
        return False
    return not (set(normalize(part).split()) & _NOT_NAME)


def _names_in(cell, matcher, res):
    """Hücredeki öğretmenler. Programda olmayan ama isim gibi görünenler de döner."""
    names = matcher.find_all(cell)
    if names:
        return names
    out = []
    for part in re.split(r"[\n,;/]|\s+-\s+", _txt(cell)):
        part = re.sub(r"^\s*\d+\s*[-.)]?\s*", "", part)  # "1 EMRAH GÜR" -> "EMRAH GÜR"
        if _person(part):
            name = clean_name(part)
            if matcher.names:
                res.note_unmatched(name)
            out.append(name)
    return out


def _date_for(key, ctx):
    if key[1]:
        return key[1]
    if ctx["week"]:
        return (ctx["week"] + dt.timedelta(days=key[0])).isoformat()
    return None


def _week_in_row(row, ctx):
    filled = [_txt(c) for c in row if _txt(c)]
    if not filled or len(filled) > 2:
        return None
    for v in filled:
        w = week_monday(v, ctx["year"])
        if w:
            return w
    return None


def _ffill(row):
    out, cur = [], ""
    for c in row:
        if c is not None:
            cur = _txt(c)
        out.append(cur)
    return out


def _parse_table(table, matcher, res, ctx):
    width = max(len(r) for r in table)
    grid = [list(r) + [None] * (width - len(r)) for r in table]
    row_keys = []
    for row in grid:
        k = None
        for c in range(min(2, width)):
            k = _key(row[c])
            if k:
                break
        row_keys.append(k)
    col_keys = []
    for c in range(width):
        k = None
        for r in range(min(4, len(grid))):
            k = _key(grid[r][c])
            if k:
                break
        col_keys.append(k)
    n_rows = sum(1 for k in row_keys if k)
    n_cols = sum(1 for k in col_keys if k)
    if max(n_rows, n_cols) == 0:
        for row in grid:
            w = _week_in_row(row, ctx)
            if w:
                ctx["week"] = w
        return False
    before = len(res.entries)
    if n_rows >= n_cols:
        cur = None
        for i, row in enumerate(grid):
            w = _week_in_row(row, ctx)
            if w and not row_keys[i]:
                ctx["week"], cur = w, None
                continue
            if row_keys[i]:
                cur = row_keys[i]
            elif _txt(row[0]) and not matcher.find_all(row[0]):
                # Gün olmayan yeni bir satır başlığı (ör. başlık satırı veya açıklama)
                cur = None
                if sum(1 for c in row if _txt(c)) >= 2:
                    ctx["header"] = _ffill(row)
                continue
            if not cur:
                continue
            header = ctx["header"] or [""] * width
            date = _date_for(cur, ctx)
            for j in range(width):
                if j < 2 and (_key(row[j]) or not _txt(row[j])):
                    continue
                place = header[j] if j < len(header) else ""
                if _key(place):
                    place = ""
                for name in _names_in(row[j], matcher, res):
                    res.add(cur[0], name, place, date)
    else:
        key_row = max(range(min(4, len(grid))),
                      key=lambda r: sum(1 for c in range(width) if _key(grid[r][c])))
        for r in range(key_row):
            w = _week_in_row(grid[r], ctx)
            if w:
                ctx["week"] = w
        cur_keys, cur = [], None
        for c in range(width):
            k = _key(grid[key_row][c])
            if k:
                cur = k
            elif _txt(grid[key_row][c]):
                cur = None
            cur_keys.append(cur)
        for i in range(key_row + 1, len(grid)):
            row = grid[i]
            label = _txt(row[0])
            label_teacher = matcher.match(label) if label else None
            for j in range(width):
                k = cur_keys[j]
                if not k or not _txt(row[j]):
                    continue
                date = _date_for(k, ctx)
                names = matcher.find_all(row[j])
                if names:
                    for name in names:
                        res.add(k[0], name, label if not label_teacher else "", date)
                elif label_teacher:
                    res.add(k[0], label_teacher, _txt(row[j]), date)
                elif label and _person(label) and j > 0:
                    # Satırda öğretmen adı, hücrede nöbet yeri; isim programda yok.
                    if matcher.names:
                        res.note_unmatched(label)
                    res.add(k[0], clean_name(label), _txt(row[j]), date)
                else:
                    for name in _names_in(row[j], matcher, res):
                        res.add(k[0], name, label, date)
    return len(res.entries) > before


def _parse_text(text, matcher, res, ctx):
    cur = None
    for line in (text or "").split("\n"):
        w = week_monday(line, ctx["year"]) if not _key(line) else None
        if w:
            ctx["week"], cur = w, None
            continue
        k = _key(line)
        rest = line
        if k:
            cur = k
            rest = re.sub(_DATE_RE, "", line)
            rest = re.sub(r"^\s*\S+\s*[:\-–]?", "", rest) if parse_day(rest) is not None else rest
        if not cur:
            continue
        date = _date_for(cur, ctx)
        for name in _names_in(rest, matcher, res):
            res.add(cur[0], name, "", date)
