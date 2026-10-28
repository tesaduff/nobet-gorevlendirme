"""Nöbetmatik: ders programından aylık nöbet çizelgesi üretir.

Kurallar:
  - Her öğretmen haftada 1 (isteğe bağlı 2) gün nöbet tutar; gün ay boyunca aynıdır.
  - Dersi olmayan günlere nöbet yazılmaz (ayarlanabilir).
  - Dersi tam dolu günler yerine daha rahat günler tercih edilir (ayarlanabilir).
  - Nöbet yerleri her hafta bir sonrakine kayar: Bahçe -> Zemin -> 1. Kat -> 2. Kat ...
  - Sabitle (öğretmen -> gün, isteğe bağlı yer), Beraber, Ayrı, Gün kısıtı kuralları.
  - Yer yetmezse kimse dışarıda kalmaz: yerlere fazladan nöbetçi yazılır.
  - Nöbetçi idareciler günlere adil ve otomatik dağıtılır.
"""
import math
import calendar
import datetime as dt
from dataclasses import asdict, dataclass, field

from .names import DAYS, normalize
from .parse_duty import DutyEntry

ADMIN_PLACE = "N.İDARECİ"


@dataclass
class Config:
    month: str = ""
    teachers: list = field(default_factory=list)       # nöbet tutabilecekler
    exempt: dict = field(default_factory=dict)         # öğretmen -> mazeret
    places: list = field(default_factory=lambda: [["Bahçe", 2], ["Zemin Kat", 2],
                                                  ["1. Kat", 2], ["2. Kat", 2]])
    per_week: int = 1                                  # 1 veya 2
    skip_free_days: bool = True
    prefer_light_days: bool = True
    rotate: bool = True
    admins_by_day: dict = field(default_factory=dict)  # "0".."4" -> idareci (otomatik)
    admins: list = field(default_factory=list)         # nöbetçi idareci olabilecekler
    fixed: list = field(default_factory=list)          # [{"teacher", "day", "place"}]
    together: list = field(default_factory=list)       # [[a, b]]
    apart: list = field(default_factory=list)          # [[a, b]]
    allowed_days: dict = field(default_factory=dict)   # öğretmen -> [gün, ...]

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        c = cls()
        for k, v in (d or {}).items():
            if hasattr(c, k):
                setattr(c, k, v)
        return c

    def capacity(self):
        return sum(int(n) for _p, n in self.places if str(_p).strip())


@dataclass
class Result:
    by_day: dict                       # gün -> [öğretmen] (ay boyunca)
    entries: list                      # tarihli DutyEntry listesi
    weeks: list                        # [(pazartesi, [tarih, ...])]
    warnings: list = field(default_factory=list)
    unassigned: list = field(default_factory=list)
    reasons: dict = field(default_factory=dict)   # öğretmen -> neden nöbet verilmedi


def month_weeks(month):
    """Ayın iş günlerini haftalara böler: [(pazartesi, [tarih, ...]), ...]."""
    y, m = (int(x) for x in month.split("-"))
    days = [dt.date(y, m, d) for d in range(1, calendar.monthrange(y, m)[1] + 1)]
    weeks = {}
    for d in days:
        if d.weekday() < 5:
            monday = d - dt.timedelta(days=d.weekday())
            weeks.setdefault(monday, []).append(d)
    return sorted(weeks.items())


def lesson_count(schedule, teacher, day):
    return sum(1 for (d, _h) in schedule.get(teacher, {}) if d == day)


def school_day_length(schedule, day):
    return max((h for slots in schedule.values() for (d, h) in slots if d == day), default=7)


def day_cost(lessons, day_len, prefer_light):
    """Küçük = daha uygun gün. Tam dolu gün en kötü; 1-2 dersle bütün gün kalmak da yorucu."""
    if not prefer_light:
        return 0
    if lessons >= day_len:
        return 10
    if lessons >= day_len - 1:
        return 4
    if lessons <= 2:
        return 2
    return 0


class _Groups:
    def __init__(self, items):
        self.parent = {i: i for i in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def distribute(cfg, schedule, history=None, covered=None, demand=None):
    """Aylık nöbet çizelgesini hesaplar.

    history: {öğretmen: bu yıl tutulan nöbet günü}
    covered: {öğretmen: bu yıl girdiği boş ders}  — çok girenler sakin günlere konur
    demand:  {gün: nöbetçi başına düşen boş ders ortalaması} — geçmiş gün yoğunluğu
    """
    history = history or {}
    covered = covered or {}
    demand = demand or {}
    top_cov = max(covered.values(), default=0) or 1
    top_dem = max(demand.values(), default=0) or 1
    warnings = []
    places = [(str(p).strip(), int(n)) for p, n in cfg.places if str(p).strip() and int(n) > 0]
    capacity = sum(n for _p, n in places)
    if not capacity:
        return Result({d: [] for d in range(5)}, [], month_weeks(cfg.month),
                      ["Nöbet yeri girilmedi."], list(cfg.teachers))
    pool = [t for t in cfg.teachers if t not in cfg.exempt]
    # Sabitlemede gün boş olabilir ("herhangi bir gün"): o zaman yalnızca yer sabitlenir.
    fixed_day = {f["teacher"]: int(f["day"]) for f in cfg.fixed
                 if f.get("teacher") in pool and f.get("day") not in (None, "", -1)}

    def allowed(t):
        # Kurallar her zaman önce gelir: sabitlenen gün / gün kısıtı, "dersi olmayan güne
        # yazma" seçeneğini geçersiz kılar.
        if t in fixed_day:
            return {fixed_day[t]}
        lesson_days = {d for d in range(5) if lesson_count(schedule, t, d) > 0}
        if cfg.allowed_days.get(t):
            days = {int(d) for d in cfg.allowed_days[t]}
            if cfg.skip_free_days and days & lesson_days:
                days &= lesson_days
            return days
        if cfg.skip_free_days and t in schedule and lesson_days:
            return lesson_days
        return set(range(5))

    # Yer yetmezse kimse dışarıda kalmaz: günlük nöbetçi sayısı artırılır, fazladan kişiler
    # yerlere sırayla eklenir.
    weekly = {t: len(schedule.get(t, {})) for t in pool}
    pool.sort(key=lambda t: (history.get(t, 0), weekly[t], normalize(t)))
    unassigned = []
    reasons = {}
    need = math.ceil(len(pool) / 5)
    expanded = need > capacity
    if expanded:
        warnings.append(f"Nöbet yerleri {len(pool)} öğretmene yetmediği için her gün {capacity} "
                        f"yerine {need} nöbetçi yazıldı; fazladan kişiler yerlere sırayla "
                        "eklendi. Herkes nöbet tutar.")
        capacity = need

    groups = _Groups(pool)
    for a, b in cfg.together:
        if a in groups.parent and b in groups.parent:
            groups.union(a, b)
    units = {}
    for t in pool:
        units.setdefault(groups.find(t), []).append(t)
    unit_of = {t: r for r, members in units.items() for t in members}
    apart = {(unit_of[a], unit_of[b]) for a, b in cfg.apart if a in unit_of and b in unit_of}
    apart |= {(b, a) for a, b in apart}

    day_len = {d: school_day_length(schedule, d) for d in range(5)}
    load = {d: 0 for d in range(5)}
    by_day = {d: [] for d in range(5)}
    unit_days = {r: [] for r in units}

    def unit_allowed(r):
        days = set(range(5))
        for t in units[r]:
            days &= allowed(t)
        return days

    def cost(r, d):
        c = sum(day_cost(lesson_count(schedule, t, d), day_len[d], cfg.prefer_light_days)
                for t in units[r])
        # Bu yıl çok boş derse girenleri, geçmişte boş dersi az olan günlere yönlendir
        c += 3 * sum(covered.get(t, 0) / top_cov for t in units[r]) * demand.get(d, 0) / top_dem
        return c + 3 * load[d] / capacity   # günleri dengeli doldur

    def place_unit(r, overflow=False):
        size = len(units[r])
        options = [d for d in unit_allowed(r) - set(unit_days[r])
                   if (overflow or load[d] + size <= capacity)
                   and not any((r, o) in apart and d in unit_days[o] for o in units)]
        if not options:
            return False
        d = min(options, key=lambda d: (cost(r, d), d))
        unit_days[r].append(d)
        load[d] += size
        by_day[d].extend(units[r])
        return True

    order = sorted(units, key=lambda r: (len(unit_allowed(r)), -len(units[r]),
                                          history.get(units[r][0], 0), normalize(units[r][0])))
    for r in order:
        # Uygun günlerde yer kalmadıysa yine dışarıda bırakılmaz, en az dolu uygun güne eklenir.
        if not place_unit(r) and not place_unit(r, overflow=True):
            names = ", ".join(units[r])
            why = ("uygun gün yok (kurallar veya ders günleri)" if not unit_allowed(r)
                   else "uygun günlerde yer kalmadı")
            warnings.append(f"{names}: {why}.")
            unassigned.extend(units[r])
            for t in units[r]:
                reasons[t] = ("Kurallar çakışıyor" if not unit_allowed(r)
                              else "Uygun günlerde yer kalmadı")
    if cfg.per_week >= 2:
        for r in sorted(units, key=lambda r: (history.get(units[r][0], 0), normalize(units[r][0]))):
            if unit_days[r]:
                place_unit(r)
    free = sum(capacity - load[d] for d in range(5))
    if free and not expanded:
        warnings.append(f"Haftada {free} nöbet yeri boş kaldı (öğretmen sayısı yetmedi). "
                        "'Gerekirse haftada 2 nöbet' seçeneğini açabilirsiniz.")

    if cfg.admins:
        cfg.admins_by_day = distribute_admins(cfg.admins, schedule, history)
    entries, weeks = build_entries(cfg, by_day)
    for t, why in cfg.exempt.items():
        if t in cfg.teachers:
            reasons[t] = "Muaf" + (f" ({why})" if why else "")
    for t in pool:
        if t not in unassigned and not any(t in by_day[d] for d in range(5)):
            unassigned.append(t)
    return Result(by_day, entries, weeks, warnings, unassigned, reasons)


def distribute_admins(admins, schedule, history=None):
    """Nöbetçi idarecileri haftanın günlerine adil dağıtır: {"0".."4": idareci}.

    Herkese sırayla gün verilir (5 gün idareci sayısına eşit bölünür); bu yıl daha az nöbetçi
    idarecilik yapan önce seçer. Her idareci okulda olduğu (dersi olan) günü tercih eder.
    """
    history = history or {}
    admins = sorted(admins, key=lambda a: (history.get(a, 0), normalize(a)))
    if not admins:
        return {}
    count = {a: 0 for a in admins}
    out = {}
    # Gün sırası: en az idarecinin dersi olan gün önce dağıtılır (seçenek az olan önce)
    days = sorted(range(5), key=lambda d: sum(1 for a in admins if lesson_count(schedule, a, d)))
    for d in days:
        best = min(admins, key=lambda a: (count[a], 0 if lesson_count(schedule, a, d) else 1,
                                          history.get(a, 0), normalize(a)))
        out[str(d)] = best
        count[best] += 1
    return out


def build_entries(cfg, by_day):
    """Gün dağılımından tarihli nöbet kayıtlarını üretir.

    Yerler karışık sırayla (Bahçe, Zemin, 1. Kat, ...) verilir ve her hafta bir kaydırılır;
    yere sabitlenen öğretmen her hafta aynı yerde kalır.
    """
    places = [(str(p).strip(), int(n)) for p, n in cfg.places if str(p).strip() and int(n) > 0]
    fixed_place = {f["teacher"]: f.get("place") or "" for f in cfg.fixed if f.get("place")}
    entries = []
    weeks = month_weeks(cfg.month)
    for d in range(5):
        fixed_here = [t for t in by_day.get(d, []) if t in fixed_place]
        rotating = sorted((t for t in by_day.get(d, []) if t not in fixed_place), key=normalize)
        remaining = dict(places)
        for t in fixed_here:
            if fixed_place[t] in remaining:
                remaining[fixed_place[t]] -= 1
        slots, left = [], dict(remaining)
        while any(v > 0 for v in left.values()):
            for p, _n in places:
                if left.get(p, 0) > 0:
                    slots.append(p)
                    left[p] -= 1
        while len(slots) < len(rotating):      # elle fazladan kişi eklendiyse yerleri tekrarla
            slots += [p for p, _n in places] or [""]
        slots = slots[:len(rotating)]
        for w, (_monday, dates) in enumerate(weeks):
            for date in dates:
                if date.weekday() != d:
                    continue
                shift = w if cfg.rotate else 0
                for i, t in enumerate(rotating):
                    place = slots[(i + shift) % len(slots)] if slots else ""
                    entries.append(DutyEntry(d, t, place, date.isoformat()))
                for t in fixed_here:
                    entries.append(DutyEntry(d, t, fixed_place[t], date.isoformat()))
                admin = cfg.admins_by_day.get(str(d)) or cfg.admins_by_day.get(d)
                if admin:
                    entries.append(DutyEntry(d, admin, ADMIN_PLACE, date.isoformat()))
    return entries, weeks


def move_teacher(cfg, result, schedule, teacher, new_day):
    """Elle düzeltme: öğretmenin nöbet gününü değiştirir (new_day None = nöbetten çıkar).

    Uyarı metni döner (boşsa sorun yok). Sonuç ve tarihli kayıtlar yerinde güncellenir.
    """
    for d in range(5):
        if teacher in result.by_day.get(d, []):
            result.by_day[d].remove(teacher)
    note = ""
    if new_day is not None:
        result.by_day.setdefault(new_day, []).append(teacher)
        if teacher in result.unassigned:
            result.unassigned.remove(teacher)
        if lesson_count(schedule, teacher, new_day) == 0:
            note = f"{teacher} {DAYS[new_day]} günü dersi olmadığı halde nöbete yazıldı."
        elif len(result.by_day[new_day]) > cfg.capacity():
            note = (f"{DAYS[new_day]} günü nöbetçi sayısı ({len(result.by_day[new_day])}) nöbet "
                    f"yeri sayısını ({cfg.capacity()}) aştı; bazı yerlerde fazladan kişi olur.")
    elif teacher not in result.unassigned:
        result.unassigned.append(teacher)
    result.entries, result.weeks = build_entries(cfg, result.by_day)
    return note


def rule_text(kind, rule):
    if kind == "fixed":
        day = rule.get("day")
        when = "herhangi bir gün" if day in (None, "", -1) else DAYS[int(day)]
        return f"{rule['teacher']} → {when}" + (f", {rule['place']}" if rule.get("place") else "")
    if kind == "together":
        return f"{rule[0]} ile {rule[1]} aynı gün"
    if kind == "apart":
        return f"{rule[0]} ile {rule[1]} farklı günlerde"
    if kind == "allowed":
        teacher, days = rule
        return f"{teacher} yalnızca " + ", ".join(DAYS[int(d)] for d in sorted(days))
    if kind == "exempt":
        teacher, reason = rule
        return f"{teacher} nöbetten muaf" + (f" — mazeret: {reason}" if reason else "")
    return str(rule)
