"""Ders programı ayrıştırıcı.

Desteklenen yerleşimler (otomatik algılanır):
  1. Öğretmen bazlı sayfalar: her sayfada bir öğretmen, tabloda gün x saat, hücrede sınıf/ders.
  2. Sınıf bazlı sayfalar: her sayfada bir şube, hücrede ders + öğretmen adı.
  3. Çarşaf program: tek tabloda satırlar öğretmen (veya şube), sütunlar gün + saat.
  Tablolar devrik (günler satırda, saatler sütunda) da olabilir.
"""
import re
from dataclasses import dataclass, field

from .names import (NameMatcher, clean_name, looks_like_class, looks_like_person,
                    normalize, parse_day)

_EMPTY = {"", "bos", "x", "ogle", "ogle arasi", "ogle yemegi", "teneffus", "nobet"}
_HOUR_WORDS = {"ders", "saat", "inci", "nci", "ci", "ncu", "uncu", "nc", "s", "d"}
_SCHOOL_WORDS = ("lisesi", "okulu", "mudurlugu", "programi", "haftalik", "egitim ogretim",
                 "donemi", "tarih", "imza", "mudur", "kurum")


@dataclass
class ScheduleResult:
    # öğretmen -> {(gün 0-4, saat 1..): "9-A Matematik"}
    teachers: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    layouts: list = field(default_factory=list)
    totals: dict = field(default_factory=dict)     # öğretmen -> belgede yazılı haftalık saat

    def add(self, teacher, day, hour, info):
        teacher = clean_name(teacher)
        if not teacher or day is None or not hour:
            return
        slots = self.teachers.setdefault(teacher, {})
        info = re.sub(r"\s*\n\s*", " ", info or "").strip()
        old = slots.get((day, hour))
        if old and info and info not in old:
            slots[(day, hour)] = f"{old} + {info}"
        else:
            slots[(day, hour)] = info or old or "Ders"

    @property
    def max_hour(self):
        hours = [h for s in self.teachers.values() for (_, h) in s]
        return max(hours) if hours else 8


def parse_hour(text):
    """'1', '1.', '1. Ders', 'Ders 1' -> 1. Saat aralığı ise ('time', dakika). Değilse None."""
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    t = re.match(r"^\s*(\d{1,2})[:.](\d{2})", raw)
    if t:
        return ("time", int(t.group(1)) * 60 + int(t.group(2)))
    n = normalize(raw.split("\n")[0])
    tokens = n.split()
    if not tokens or len(tokens) > 3:
        return None
    nums = [tok for tok in tokens if tok.isdigit()]
    rest = [tok for tok in tokens if not tok.isdigit()]
    if len(nums) == 1 and all(r in _HOUR_WORDS for r in rest):
        v = int(nums[0])
        if 1 <= v <= 15:
            return v
    return None


def _pad(table):
    width = max(len(r) for r in table)
    return [list(r) + [None] * (width - len(r)) for r in table]


def _txt(v):
    return "" if v is None else str(v).strip()


def _ffill_days(row):
    """Gün başlık satırını birleştirilmiş hücreleri hesaba katarak sağa doldurur."""
    out, cur = [], None
    for c in row:
        d = parse_day(c)
        if d is not None:
            cur = d
        elif _txt(c):
            cur = None if parse_hour(c) is None else cur
        out.append(cur)
    return out


def _hours_from_labels(labels, groups):
    """Saat etiketlerini (numara veya saat aralığı) sıra numarasına çevirir.

    groups: aynı güne ait etiketleri gruplamak için anahtarlar (sıra her grupta 1'den başlar).
    """
    result = [None] * len(labels)
    counters = {}
    for i, (lab, g) in enumerate(zip(labels, groups)):
        if g is None:
            continue
        counters[g] = counters.get(g, 0) + 1
        if isinstance(lab, int):
            result[i] = lab
        else:
            result[i] = counters[g]
    return result


def _is_empty_cell(v):
    return normalize(v) in _EMPTY


def page_owner(text):
    """Sayfa başlığından öğretmen veya şube adını bulur: (ad, 'teacher'|'class'|None)."""
    lines = [l.strip() for l in (text or "").split("\n") if l.strip()]
    for line in lines[:15]:
        n = normalize(line)
        if ":" in line and ("ogretmen" in n or "adi soyadi" in n or "adi ve soyadi" in n):
            val = line.split(":", 1)[1]
            val = re.split(r"\s{2,}|\t| Branş| Bran[sş]ı|Sınıf|Şube", val)[0]
            val = clean_name(val)
            if looks_like_person(val):
                return val, "teacher"
        m = re.match(r"^(.*?)\s+(Öğretmen|ÖĞRETMEN|Ogretmen|OGRETMEN)", line)
        if m and looks_like_person(m.group(1)):
            return clean_name(m.group(1)), "teacher"
    for line in lines[:15]:
        n = normalize(line)
        if ":" in line and ("sinif" in n or "sube" in n):
            val = clean_name(line.split(":", 1)[1])
            val = re.split(r"\s{2,}", val)[0]
            if val:
                return val, "class"
        m = re.match(r"^(.*?)\s*(Sınıfı|SINIFI|Şubesi|ŞUBESİ)\b", line)
        if m and looks_like_class(m.group(1)):
            return clean_name(m.group(1)), "class"
    for line in lines[:8]:
        n = normalize(line)
        if any(w in n for w in _SCHOOL_WORDS):
            continue
        if looks_like_class(line):
            return clean_name(line), "class"
        if looks_like_person(line):
            return clean_name(line), "teacher"
    return None, None


def split_class_cell(cell, matcher=None):
    """Sınıf programı hücresinden (ders, [öğretmenler]) çıkarır."""
    text = _txt(cell)
    if matcher and matcher.names:
        found = matcher.find_all(text)
        if found:
            lesson = text
            for f in found:
                lesson = re.sub(re.escape(f), "", lesson, flags=re.I)
            return clean_name(re.sub(r"\s+", " ", lesson)), found
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    teachers, lesson = [], []
    for line in lines:
        if looks_like_person(line) and not _looks_like_lesson(line):
            teachers.append(clean_name(line))
        else:
            lesson.append(line)
    if not teachers and lines:
        # Tek satır: "MATEMATİK Ahmet YILMAZ" -> son iki kelime öğretmen
        words = lines[-1].split()
        if len(words) >= 3 and looks_like_person(" ".join(words[-2:])):
            teachers.append(" ".join(words[-2:]))
            lesson = [" ".join(words[:-2])] + lesson[:-1]
    return clean_name(" ".join(lesson)), teachers


_LESSON_HINTS = ("matematik", "turkce", "edebiyat", "fizik", "kimya", "biyoloji", "tarih",
                 "cografya", "ingilizce", "almanca", "din kultur", "beden", "muzik", "gorsel",
                 "felsefe", "rehberlik", "bilisim", "teknoloji", "fen bilim", "sosyal bilg",
                 "secmeli", "proje", "egitimi", "dili ve", "atolye", "meslek", "rehberlik",
                 "kuran", "peygamber", "temel dini", "saglik", "trafik", "psikoloji", "sosyoloji",
                 "mantik", "inkilap", "uygulama", "laboratuvar")


def _looks_like_lesson(line):
    n = normalize(line)
    return any(h in n for h in _LESSON_HINTS)


def parse_schedule(pages, known_teachers=()):
    """Belge sayfalarından ders programını çıkarır."""
    res = ScheduleResult()
    matcher = NameMatcher(known_teachers) if known_teachers else None
    unknown = 0
    for p_idx, page in enumerate(pages, start=1):
        owner, kind = page_owner(page.get("text", ""))
        res.warnings.extend(n for n in page.get("notes", []) if n not in res.warnings)
        for table in page.get("tables", []):
            if not table:
                continue
            grid = _pad(table)
            if _parse_days_in_cols(grid, owner, kind, res, matcher, p_idx):
                continue
            if _parse_days_in_rows(grid, owner, kind, res, matcher, p_idx):
                continue
        if not page.get("tables") and page.get("text", "").strip():
            unknown += 1
    _reconcile_geometry(res, pages)
    _join_split_blocks(res)
    for name, total in res.totals.items():
        read = len(res.teachers.get(name, {}))
        if read != total:
            res.warnings.append(f"⚠ {name}: belgede haftalık {total} saat yazıyor, {read} saat "
                                "okunabildi — programı kontrol edin.")
    if unknown:
        res.warnings.append(f"{unknown} sayfada tablo bulunamadı (atlandı).")
    if not res.teachers:
        res.warnings.append("Belgede gün/saat tablosu bulunamadı. Tabloda 'Pazartesi, Salı…' "
                            "başlıkları ve ders saatleri olduğundan emin olun.")
    return res


def _reconcile_geometry(res, pages):
    """Tablo okumasını, başlık sütunlarına bakan ikinci okumayla karşılaştırır.

    Tek dikdörtgene yazılmış blok derslerde (2-3 saat) tablo okuması bir saati kaçırabilir ya da
    sınıfı yanlış hücreye koyabilir. İkinci okuma o kutuyu kapladığı bütün saatlere yaydığı için
    eksik saati ekler, sınıfı olmayan/farklı derslerde kutunun yazısını kullanır."""
    from .names import split_info
    by_norm = {normalize(t): t for t in res.teachers}
    fixed = 0
    for page in pages:
        for name, cells in (page.get("geo") or {}).items():
            t = by_norm.get(normalize(clean_name(name)))
            if t is None:
                continue
            slots = res.teachers[t]
            for key, text in cells.items():
                if not text or normalize(text) in _EMPTY:
                    continue
                cur = slots.get(key)
                if cur is None:
                    slots[key] = text
                    fixed += 1
                    continue
                c_cur, c_new = split_info(cur)[0], split_info(text)[0]
                if c_new and c_cur != c_new:
                    slots[key] = text
                    fixed += 1
                elif not c_new and c_cur and normalize(split_info(cur)[1]) != normalize(
                        split_info(text)[1]) and len(text) > len(cur):
                    pass       # emin olunamayan fark: tablo okuması korunur
    if fixed:
        res.warnings.append(f"ℹ {fixed} ders hücresi ikinci okumayla (kutu/başlık karşılaştırması) "
                            "düzeltildi veya tamamlandı.")


def _owner_or_unknown(owner, res, p_idx):
    if owner:
        return owner
    name = f"Bilinmeyen (sayfa {p_idx})"
    msg = f"Sayfa {p_idx}: öğretmen/şube adı bulunamadı, '{name}' olarak eklendi — lütfen düzeltin."
    if msg not in res.warnings:
        res.warnings.append(msg)
    return name


def _emit(res, owner, kind, day, hour, cell, matcher):
    if _is_empty_cell(cell):
        return
    text = _txt(cell)
    if kind == "class":
        lesson, teachers = split_class_cell(text, matcher)
        info = f"{owner} {lesson}".strip()
        if not teachers:
            res.warnings.append(f"{owner} {day + 1}. gün {hour}. saat: hücrede öğretmen adı "
                                f"bulunamadı ('{text[:40]}')")
            return
        for t in teachers:
            res.add(t, day, hour, info)
    else:
        res.add(owner, day, hour, text)


def _parse_days_in_cols(grid, owner, kind, res, matcher, p_idx):
    for r in range(min(6, len(grid))):
        col_day = _ffill_days(grid[r])
        distinct = {d for d in col_day if d is not None}
        if len(distinct) < 2:
            continue
        # Doldurmayla güne bağlanan ama tamamen boş sütunları (tablo kenarı) at.
        for c, d in enumerate(col_day):
            if d is not None and parse_day(grid[r][c]) is None and \
                    not any(_txt(grid[i][c]) for i in range(r + 1, len(grid))):
                col_day[c] = None
        day_cols = [c for c, d in enumerate(col_day) if d is not None]
        per_day = {}
        for c in day_cols:
            per_day.setdefault(col_day[c], []).append(c)
        multi = max(len(v) for v in per_day.values()) > 1
        if multi:
            # Çarşaf: alt satırda saat numaraları olabilir.
            hour_row = r + 1 if r + 1 < len(grid) else None
            labels = [parse_hour(grid[hour_row][c]) if hour_row is not None else None
                      for c in range(len(col_day))]
            has_hours = sum(1 for c in day_cols if labels[c] is not None) >= len(day_cols) * 0.6
            if has_hours:
                # "Öğle Arası" gibi saat olmayan sütunlar hiçbir saate sayılmaz.
                hours = _hours_from_labels(
                    labels, [d if labels[c] is not None else None for c, d in enumerate(col_day)])
            else:
                hour_row = r
                hours = _hours_from_labels([None] * len(col_day), col_day)
            _parse_carsaf_rows(grid, hour_row + 1, col_day, hours, res, matcher, p_idx)
            res.layouts.append("çarşaf (satırlar öğretmen/şube)")
            return True
        # Izgara: satırlar saat, sütunlar gün; sahibi sayfa başlığından.
        label_col = next((c for c in range(len(col_day)) if col_day[c] is None), None)
        labels = []
        body = range(r + 1, len(grid))
        for i in body:
            labels.append(parse_hour(grid[i][label_col]) if label_col is not None else None)
        if label_col is not None and not any(labels):
            # Etiket sütunu saat değil, öğretmen/şube adı: devrik olmayan basit çarşaf.
            names = [_txt(grid[i][label_col]) for i in body]
            if sum(1 for n in names if n) >= 2:
                hours = [1 if d is not None else None for d in col_day]
                _parse_carsaf_rows(grid, r + 1, col_day, hours, res, matcher, p_idx)
                res.layouts.append("çarşaf (günlük tek sütun)")
                return True
        row_hours = _hours_from_labels(labels, [0 if (lab is not None or label_col is None)
                                                 else None for lab in labels])
        if not any(row_hours):
            row_hours = list(range(1, len(labels) + 1))
        who = _owner_or_unknown(owner, res, p_idx)
        k = kind or ("class" if looks_like_class(who) else "teacher")
        above = {}
        for i, h in zip(body, row_hours):
            for c in day_cols:
                # Birleştirilmiş hücre (blok ders): üstteki hücrenin dersi devam eder.
                v = grid[i][c] if grid[i][c] is not None else above.get(c)
                above[c] = v
                if h:
                    _emit(res, who, k, col_day[c], h, v, matcher)
        res.layouts.append("sayfa başına " + ("şube" if k == "class" else "öğretmen"))
        return True
    return False


def _parse_carsaf_rows(grid, start, col_day, hours, res, matcher, p_idx):
    label_cols = [c for c, d in enumerate(col_day) if d is None]
    rows = []
    for i in range(start, len(grid)):
        label = ""
        for c in label_cols:
            v = _txt(grid[i][c])
            if v and not v.isdigit():
                label = v.split("\n")[0]
                break
        if label:
            rows.append((label, grid[i]))
    class_rows = sum(1 for lab, _ in rows if looks_like_class(lab))
    kind = "class" if rows and class_rows > len(rows) / 2 else "teacher"
    for label, row in rows:
        if kind == "teacher" and not (looks_like_person(label) or
                                      (matcher and matcher.match(label))):
            if len(normalize(label).split()) < 2:
                continue
        prev = None
        total = None                      # satır sonunda yazılı haftalık ders saati
        for c in reversed(label_cols):
            t = _txt(row[c])
            if t.isdigit() and 0 < int(t) <= 60:
                total = int(t)
                break
            if t:
                break
        for c, d in enumerate(col_day):
            v = row[c]
            # Birleştirilmiş hücre (blok ders): soldaki hücrenin dersi aynı gün içinde devam eder.
            if v is None and c > 0 and d is not None and col_day[c - 1] == d:
                v = prev
            prev = v
            if d is None or not hours[c]:
                continue
            _emit(res, clean_name(label), kind, d, hours[c], v, matcher)
        if kind == "teacher" and total is not None:
            res.totals[clean_name(label)] = total


def _parse_days_in_rows(grid, owner, kind, res, matcher, p_idx):
    width = len(grid[0])
    for c in range(min(4, width)):
        col = [row[c] for row in grid]
        days = [parse_day(v) for v in col]
        if len({d for d in days if d is not None}) < 2:
            continue
        # Günleri aşağı doğru doldur
        row_day, cur = [], None
        for v, d in zip(col, days):
            if d is not None:
                cur = d
            elif _txt(v):
                cur = cur if parse_hour(v) is not None else None
            row_day.append(cur)
        first_day_row = next(i for i, d in enumerate(row_day) if d is not None)
        # Devrik çarşaf: yanındaki sütunda saatler, başlık satırında sahipler
        if c + 1 < width:
            hcol = [parse_hour(grid[i][c + 1]) for i in range(len(grid))]
            day_rows = [i for i, d in enumerate(row_day) if d is not None]
            if sum(1 for i in day_rows if hcol[i] is not None) >= len(day_rows) * 0.6 and \
                    len(day_rows) > len({row_day[i] for i in day_rows}):
                hours = _hours_from_labels(hcol, row_day)
                header = grid[first_day_row - 1] if first_day_row > 0 else None
                if header:
                    owners = [(j, _txt(header[j]).split("\n")[0]) for j in range(c + 2, width)
                              if _txt(header[j])]
                    k = "class" if owners and sum(looks_like_class(o) for _, o in owners) > \
                        len(owners) / 2 else "teacher"
                    for i in day_rows:
                        if not hours[i]:
                            continue
                        for j, o in owners:
                            _emit(res, clean_name(o), k, row_day[i], hours[i], grid[i][j], matcher)
                    res.layouts.append("devrik çarşaf")
                    return True
        # Izgara devrik: başlık satırında saatler
        header_idx = first_day_row - 1 if first_day_row > 0 else None
        if header_idx is None:
            continue
        labels = [parse_hour(v) for v in grid[header_idx]]
        groups = [0 if (j != c and labels[j] is not None) else None for j in range(width)]
        if not any(g is not None for g in groups):
            groups = [0 if j > c else None for j in range(width)]
        hours = _hours_from_labels(labels, groups)
        who = _owner_or_unknown(owner, res, p_idx)
        k = kind or ("class" if looks_like_class(who) else "teacher")
        for i, d in enumerate(row_day):
            if d is None or i <= header_idx:
                continue
            for j in range(c + 1, width):
                if hours[j]:
                    _emit(res, who, k, d, hours[j], grid[i][j], matcher)
        res.layouts.append("sayfa başına (devrik)")
        return True
    return False


def _join_split_blocks(res):
    """Blok dersin yazısı iki hücreye bölünmüş olabilir: biri yalnızca sınıf, öteki yalnızca
    ders adı ("BİLG." + "6/E"). Ardışık saatlerde (öğle arası saat sayılmaz) ikisini de
    "sınıf ders" yapar. Ayrıca sınıfı olmayan bir derse, yanındaki saatte aynı ders adı sınıfla
    birlikte yazılıysa o sınıf eklenir (3 saatlik bloklar dahil)."""
    from .names import split_info
    for slots in res.teachers.values():
        for _ in range(3):                        # 3 saatlik bloklar için birkaç tur
            changed = False
            for (d, h) in sorted(slots):
                nxt = (d, h + 1)
                if nxt not in slots:
                    continue
                c1, l1 = split_info(slots[(d, h)])
                c2, l2 = split_info(slots[nxt])
                if c1 and not l1 and l2 and not c2:
                    slots[(d, h)] = slots[nxt] = f"{c1} {l2}"
                    changed = True
                elif l1 and not c1 and c2 and not l2:
                    slots[(d, h)] = slots[nxt] = f"{c2} {l1}"
                    changed = True
                elif l1 and l2 and normalize(l1) == normalize(l2) and bool(c1) != bool(c2) \
                        and "destek" not in normalize(l1):
                    # Aynı ders ardışık iki saatte, birinde sınıf var biri yok: blok dersin parçası
                    cls = c1 or c2
                    slots[(d, h)] = slots[nxt] = f"{cls} {l1}"
                    changed = True
            if not changed:
                break
