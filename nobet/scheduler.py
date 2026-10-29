"""Boş kalan derslere adil öğretmen görevlendirmesi."""
import datetime as dt
from dataclasses import dataclass, field

KIND_LABELS = {
    "nobetci": "Nöbetçi",
    "bos": "Nöbetçi değil (boş saati)",
    "joker": "Joker öğretmen",
    "elle": "Elle seçildi",
    "yok": "Atanamadı",
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
    jokers: list = field(default_factory=list)


def teachers_with_lessons(schedule, weekday):
    return sorted(t for t, slots in schedule.items() if any(d == weekday for d, _ in slots))


JOKER_MAX = 7   # joker öğretmenin günde girebileceği en fazla ders (kendi dersleri dahil)


def plan_day(date, schedule, duty, absences, month_counts, total_counts, max_per_day=0,
             excluded=(), year_counts=None, jokers=()):
    """Günün görevlendirmesini hesaplar.

    schedule: {öğretmen: {(gün, saat): bilgi}}
    duty: [(öğretmen, yer)] o günün nöbetçileri
    absences: {öğretmen: sebep}
    month_counts: {öğretmen: (ay toplamı, nöbetçi, boş)} — bu gün hariç
    total_counts: {öğretmen: tüm zamanlar toplamı} — bu gün hariç
    max_per_day: bir nöbetçiye günde en fazla kaç ders verileceği (0 = sınırsız). Sınıra
        ulaşan nöbetçinin yerine boş öğretmen aranır; kimse yoksa yine nöbetçiye verilir.
    excluded: otomatik görevlendirilmeyecekler (ör. idareciler). Bunlar yalnızca elle seçim
        listesinde "idareci" etiketiyle yer alır.
    jokers: o gün okulda olup boş derslere girebilecek, elle eklenen öğretmenler. Boş nöbetçi
        kalmazsa diğer öğretmenlerden önce bunlar (adalet sırasıyla) görevlendirilir. Bir joker
        öğretmen o gün derssiz sayılır ve günde en fazla JOKER_MAX ders alır; jokerler dolunca
        (ya da o saatte başka bir göreve girmişlerse) o saatte dersi olmayan diğer öğretmenlere
        geçilir.
    """
    excluded = set(excluded)
    year_counts = year_counts or {}  # eğitim yılı toplamı: adalette önce buna bakılır
    weekday = dt.date.fromisoformat(date).weekday()
    duty_names = []
    for t, _ in duty:
        if t not in duty_names and t not in excluded:
            duty_names.append(t)
    teaching = teachers_with_lessons(schedule, weekday)
    joker_names = [t for t in dict.fromkeys(jokers) if t and t not in duty_names]

    def busy_hours(t):
        return {h for (d, h) in schedule.get(t, {}) if d == weekday}

    busy = {t: busy_hours(t) for t in set(schedule) | set(duty_names)}
    # Joker öğretmen o gün derssiz kabul edilir: bütün saatleri boştur, yalnızca verilen
    # görevler sayılır (günde en fazla JOKER_MAX).
    for t in joker_names:
        busy[t] = set()
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
        free_duty = [t for t in duty_names if t not in absences and h not in busy.get(t, set())]
        free_joker = [t for t in joker_names if t not in absences and h not in busy.get(t, set())
                      and len(busy.get(t, set())) < JOKER_MAX]
        free_other = [t for t in teaching if t not in absences and t not in duty_names
                      and t not in joker_names and t not in excluded
                      and h not in busy.get(t, set())]
        free_admins = [t for t in sorted(excluded) if t not in absences
                       and (t in teaching or t in {d for d, _ in duty})
                       and h not in busy.get(t, set())]
        a.options = ([(t, "nöbetçi") for t in sorted(free_duty, key=fairness)] +
                     [(t, "joker") for t in sorted(free_joker, key=fairness)] +
                     [(t, "pencere" if window(t, h) else "boş saat")
                      for t in sorted(free_other, key=lambda t: (fairness(t)[:2], not window(t, h),
                                                                 fairness(t)))] +
                     [(t, "idareci") for t in free_admins])
        under_cap = [t for t in free_duty if not max_per_day or today.get(t, 0) < max_per_day]
        if under_cap:
            pick = min(under_cap, key=fairness)
            a.assigned, a.kind = pick, "nobetci"
            a.note = ""
        elif free_joker:
            pick = min(free_joker, key=fairness)
            a.assigned, a.kind = pick, "joker"
            why = (f"boş nöbetçiler bugün {max_per_day} ders sınırına ulaştığı" if free_duty
                   else "bu saatte boş nöbetçi öğretmen olmadığı")
            a.note = f"Joker öğretmen: {why} için atandı."
        elif free_other:
            # Diğer öğretmenlerde de istatistik esastır: bu yıl en az derse giren önce seçilir;
            # eşitlikte iki dersi arasında boşluğu olan tercih edilir.
            pick = min(free_other, key=lambda t: (fairness(t)[:2], not window(t, h), fairness(t)))
            a.assigned, a.kind = pick, "bos"
            gap = "iki dersi arasında boş saati var" if window(pick, h) else "bu saatte dersi yok"
            jokers_full = [t for t in joker_names if t not in absences
                           and len(busy.get(t, set())) >= JOKER_MAX]
            why = (f"boş nöbetçiler bugün {max_per_day} ders sınırına ulaştığı" if free_duty
                   else "joker öğretmen(ler) günlük 7 ders sınırını doldurduğu" if joker_names
                   and len(jokers_full) == len([t for t in joker_names if t not in absences])
                   else "joker öğretmen(ler) bu saatte başka bir sınıfta görevli olduğu"
                   if joker_names
                   else "bu saatte boş nöbetçi öğretmen olmadığı")
            a.note = f"⚠ {pick} nöbetçi değil; {gap}. {why[0].upper() + why[1:]} için atandı."
        elif free_duty:
            pick = min(free_duty, key=fairness)
            a.assigned, a.kind = pick, "nobetci"
            a.note = f"Günlük {max_per_day} ders sınırı aşıldı; başka boş öğretmen yok."
        else:
            a.assigned, a.kind = None, "yok"
            a.note = "⚠ Bu saatte boş öğretmen yok. Elle seçin veya sınıf birleştirin."
        if a.assigned:
            busy.setdefault(a.assigned, set()).add(h)
            today[a.assigned] = today.get(a.assigned, 0) + 1

    # Ekranda ve çıktıda her gelmeyen öğretmenin dersleri saat sırasıyla alt alta görünür.
    slots.sort(key=lambda a: (a.absent, a.hour))
    return DayPlan(date=date, weekday=weekday, duty=duty, teaching=teaching,
                   absences=dict(absences), assignments=slots, jokers=joker_names)


def options_for(plan, schedule, index):
    """Elle değiştirme için: o saatte başka atanmamış ve boş olan öğretmenler."""
    a = plan.assignments[index]
    taken = {x.assigned for i, x in enumerate(plan.assignments)
             if i != index and x.hour == a.hour and x.assigned}
    return [(t, lab) for t, lab in a.options if t not in taken]
