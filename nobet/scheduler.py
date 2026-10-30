"""Boş kalan derslere adil öğretmen görevlendirmesi."""
import datetime as dt
from dataclasses import dataclass, field

KIND_LABELS = {
    "nobetci": "Nöbetçi",
    "bos": "Nöbetçi değil (elle seçildi)",
    "elle": "Elle seçildi",
    "joker": "Elle seçildi",        # eski kayıtlar
    "yok": "Atanmadı",
}


@dataclass
class Assignment:
    hour: int
    absent: str
    info: str
    assigned: str = None
    kind: str = "yok"
    note: str = ""
    options: list = field(default_factory=list)  # [(öğretmen, etiket)]


@dataclass
class DayPlan:
    date: str
    weekday: int
    duty: list            # [(öğretmen, yer)]
    teaching: list        # o gün dersi olan öğretmenler
    absences: dict        # öğretmen -> sebep
    assignments: list


def teachers_with_lessons(schedule, weekday):
    return sorted(t for t, slots in schedule.items() if any(d == weekday for d, _ in slots))


def plan_day(date, schedule, duty, absences, month_counts, total_counts, max_per_day=0,
             excluded=(), year_counts=None, blocked=None):
    """Günün görevlendirmesini hesaplar.

    Yalnızca o günün nöbetçi öğretmenlerine, o saatte dersi boş olanlara görev verilir; bu
    sırayla bu eğitim yılı en az derse girmiş olan seçilir. O saatte boş nöbetçi yoksa ders
    BOŞ bırakılır (kimse atanmaz); kullanıcı açılır listeden elle seçer.

    schedule: {öğretmen: {(gün, saat): bilgi}}
    duty: [(öğretmen, yer)] o günün nöbetçileri
    absences: {öğretmen: sebep}
    month_counts: {öğretmen: (ay toplamı, nöbetçi, boş)} — bu gün hariç
    total_counts: {öğretmen: tüm zamanlar toplamı} — bu gün hariç
    max_per_day: bir nöbetçiye günde en fazla kaç ders verileceği (0 = sınırsız)
    excluded: otomatik görevlendirilmeyecekler (ör. idareciler); yalnızca elle seçim listesinde
        "idareci" etiketiyle yer alır.
    blocked: {öğretmen: {saat, ...}} — o gün bu saatlerde öğretmene ders görevlendirilmez
        (mazereti var); elle seçim listesinde de çıkmaz.
    """
    excluded = set(excluded)
    blocked = {t: set(h) for t, h in (blocked or {}).items()}
    year_counts = year_counts or {}  # eğitim yılı toplamı: adalette önce buna bakılır
    weekday = dt.date.fromisoformat(date).weekday()
    duty_names = []
    for t, _ in duty:
        if t not in duty_names and t not in excluded:
            duty_names.append(t)
    teaching = teachers_with_lessons(schedule, weekday)

    def busy_hours(t):
        return {h for (d, h) in schedule.get(t, {}) if d == weekday}

    busy = {t: busy_hours(t) for t in set(schedule) | set(duty_names)}
    today = {}

    slots = []
    for t in sorted(absences):
        for h in sorted(busy.get(t, ())):
            slots.append(Assignment(hour=h, absent=t, info=schedule[t][(weekday, h)] or ""))
    slots.sort(key=lambda a: (a.hour, a.absent))

    def month_total(t):
        return month_counts.get(t, (0, 0, 0))[0]

    def fairness(t):
        # Güncel toplam: o gün verilen dersler de anında sayılır (aynı gün üst üste
        # aynı kişiye yığılmasın). Önce eğitim yılı toplamı, sonra ay, sonra tüm zamanlar.
        now = today.get(t, 0)
        return (year_counts.get(t, (0,))[0] + now, month_total(t) + now,
                total_counts.get(t, 0) + now, t)

    def window(t, h):
        hs = busy.get(t, set())
        return bool(hs) and min(hs) < h < max(hs)

    for a in slots:
        h = a.hour
        free_duty = [t for t in duty_names if t not in absences
                     and h not in busy.get(t, set()) and h not in blocked.get(t, ())]
        free_other = [t for t in teaching if t not in absences and t not in duty_names
                      and t not in excluded and h not in busy.get(t, set())
                      and h not in blocked.get(t, ())]
        free_admins = [t for t in sorted(excluded) if t not in absences
                       and (t in teaching or t in {d for d, _ in duty})
                       and h not in busy.get(t, set()) and h not in blocked.get(t, ())]
        # Elle seçim listesi: önce nöbetçiler, sonra o saatte dersi olmayan diğer öğretmenler
        a.options = ([(t, "nöbetçi") for t in sorted(free_duty, key=fairness)] +
                     [(t, "pencere" if window(t, h) else "boş saat")
                      for t in sorted(free_other, key=lambda t: (fairness(t)[:2],
                                                                 not window(t, h), fairness(t)))] +
                     [(t, "idareci") for t in free_admins])
        under_cap = [t for t in free_duty if not max_per_day or today.get(t, 0) < max_per_day]
        if under_cap:
            pick = min(under_cap, key=fairness)
            a.assigned, a.kind = pick, "nobetci"
            a.note = ""
        elif free_duty:
            pick = min(free_duty, key=fairness)
            a.assigned, a.kind = pick, "nobetci"
            a.note = f"Günlük {max_per_day} ders sınırı aşıldı; başka boş nöbetçi yok."
        else:
            # Boş nöbetçi yok: ders boş kalır, elle seçilir
            a.assigned, a.kind = None, "yok"
            a.note = "Bu saatte boş nöbetçi öğretmen yok — açılır listeden elle seçin."
        if a.assigned:
            busy.setdefault(a.assigned, set()).add(h)
            today[a.assigned] = today.get(a.assigned, 0) + 1

    # Ekranda ve çıktıda her gelmeyen öğretmenin dersleri saat sırasıyla alt alta görünür.
    slots.sort(key=lambda a: (a.absent, a.hour))
    return DayPlan(date=date, weekday=weekday, duty=duty, teaching=teaching,
                   absences=dict(absences), assignments=slots)


def options_for(plan, schedule, index):
    """Elle değiştirme için: o saatte başka atanmamış ve boş olan öğretmenler."""
    a = plan.assignments[index]
    taken = {x.assigned for i, x in enumerate(plan.assignments)
             if i != index and x.hour == a.hour and x.assigned}
    return [(t, lab) for t, lab in a.options if t not in taken]
