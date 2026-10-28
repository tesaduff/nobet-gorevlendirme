"""Nöbet çizelgesi ayrıştırıcı.

Çizelgedeki isimler ders programındaki öğretmen listesiyle eşleştirilir. Desteklenenler:
  - Satırlarda gün (veya tarih), sütunlarda nöbet yeri, hücrelerde öğretmen adları
  - Sütunlarda gün, satırlarda nöbet yeri
  - Satırlarda öğretmen, sütunlarda gün, hücrelerde nöbet yeri
  - Tablosuz metin: "Pazartesi: Ahmet YILMAZ, Ayşe KAYA" gibi satırlar
"""
import datetime as dt
import re
from dataclasses import dataclass, field

from .names import NameMatcher, clean_name, looks_like_person, parse_day

_DATE_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")


@dataclass
class DutyEntry:
    weekday: int
    teacher: str
    place: str = ""
    date: str = None  # ISO tarih; yalnızca çizelge tarih bazlıysa


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


def _key(text):
    """Hücreden (gün, tarih) çıkarır."""
    if text is None:
        return None
    s = str(text)
    m = _DATE_RE.search(s)
    if m:
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


def _txt(v):
    return "" if v is None else str(v).strip()


def parse_duty(pages, known_teachers):
    res = DutyResult()
    matcher = NameMatcher(known_teachers)
    if not matcher.names:
        res.warnings.append("Önce ders programını yükleyin; nöbet çizelgesindeki isimler "
                            "ders programındaki öğretmenlerle eşleştirilir.")
    any_table = False
    for page in pages:
        for table in page.get("tables", []):
            if table and _parse_table(table, matcher, res):
                any_table = True
    if not any_table:
        for page in pages:
            _parse_text(page.get("text", ""), matcher, res)
    if not res.entries:
        res.warnings.append("Çizelgede gün/tarih ile eşleşen öğretmen bulunamadı.")
    return res


def _names_in(cell, matcher, res):
    names = matcher.find_all(cell)
    if not names:
        for part in re.split(r"[\n,;/]", _txt(cell)):
            if looks_like_person(part):
                if matcher.names:
                    res.note_unmatched(part)
                else:
                    names.append(clean_name(part))
    return names


def _parse_table(table, matcher, res):
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
        for r in range(min(3, len(grid))):
            k = _key(grid[r][c])
            if k:
                break
        col_keys.append(k)
    n_rows = sum(1 for k in row_keys if k)
    n_cols = sum(1 for k in col_keys if k)
    if max(n_rows, n_cols) == 0:
        return False
    before = len(res.entries)
    if n_rows >= n_cols:
        # Birleştirilmiş gün hücreleri: alt satırlar aynı güne aittir.
        cur = None
        for i, row in enumerate(grid):
            if row_keys[i]:
                cur = row_keys[i]
            elif _txt(row[0]) and not matcher.find_all(row[0]):
                # Gün olmayan yeni bir satır başlığı (ör. "Nöbetçi Müdür Yrd.")
                cur = None
            if not cur:
                continue
            header_row = next((r for r in range(i) if not row_keys[r]), None)
            for j in range(width):
                if j < 2 and (_key(row[j]) or not _txt(row[j])):
                    continue
                place = _txt(grid[header_row][j]) if header_row is not None else ""
                if _key(place):
                    place = ""
                for name in _names_in(row[j], matcher, res):
                    res.add(cur[0], name, place, cur[1])
    else:
        key_row = max(range(min(3, len(grid))),
                      key=lambda r: sum(1 for c in range(width) if _key(grid[r][c])))
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
                names = matcher.find_all(row[j])
                if names:
                    for name in names:
                        res.add(k[0], name, label if not label_teacher else "", k[1])
                elif label_teacher:
                    res.add(k[0], label_teacher, _txt(row[j]), k[1])
                else:
                    _names_in(row[j], matcher, res)
            if label and not label_teacher and looks_like_person(label) and matcher.names \
                    and any(cur_keys[j] and _txt(row[j]) for j in range(width)):
                if not any(matcher.find_all(row[j]) for j in range(width)):
                    res.note_unmatched(label)
    return len(res.entries) > before


def _parse_text(text, matcher, res):
    cur = None
    for line in (text or "").split("\n"):
        k = _key(line)
        rest = line
        if k:
            cur = k
            rest = re.sub(_DATE_RE, "", line)
            rest = re.sub(r"^\s*\S+\s*[:\-–]?", "", rest) if parse_day(rest) is not None else rest
        if not cur:
            continue
        for name in _names_in(rest, matcher, res):
            res.add(cur[0], name, "", cur[1])

