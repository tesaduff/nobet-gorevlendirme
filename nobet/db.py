"""SQLite veri katmanı. Veriler kullanıcı klasöründe tutulur; güncellemede silinmez."""
import datetime as dt
import os
import sqlite3
import sys

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS schedule_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    valid_from TEXT NOT NULL,          -- bu tarihten itibaren geçerli
    source TEXT,
    imported_at TEXT
);
CREATE TABLE IF NOT EXISTS schedule_entries (
    version_id INTEGER NOT NULL REFERENCES schedule_versions(id) ON DELETE CASCADE,
    teacher TEXT NOT NULL,
    day INTEGER NOT NULL,              -- 0 = Pazartesi
    hour INTEGER NOT NULL,             -- 1 = 1. ders
    info TEXT,
    PRIMARY KEY (version_id, teacher, day, hour)
);

CREATE TABLE IF NOT EXISTS duty_entries (
    month TEXT NOT NULL,               -- 'YYYY-AA': bu aydan itibaren geçerli çizelge
    weekday INTEGER NOT NULL,
    date TEXT,                         -- tarih bazlı çizelgelerde
    teacher TEXT NOT NULL,
    place TEXT
);
CREATE INDEX IF NOT EXISTS duty_month ON duty_entries(month);

CREATE TABLE IF NOT EXISTS absences (
    date TEXT NOT NULL,
    teacher TEXT NOT NULL,
    reason TEXT,
    PRIMARY KEY (date, teacher)
);

CREATE TABLE IF NOT EXISTS assignments (
    date TEXT NOT NULL,
    hour INTEGER NOT NULL,
    absent_teacher TEXT NOT NULL,
    info TEXT,
    assigned TEXT,                     -- NULL: atanamadı
    kind TEXT,                         -- nobetci | bos | elle | yok
    note TEXT,
    PRIMARY KEY (date, hour, absent_teacher)
);
CREATE INDEX IF NOT EXISTS assign_date ON assignments(date);
"""


def data_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    path = os.path.join(base, "NobetGorevlendirme")
    os.makedirs(path, exist_ok=True)
    return path


class Database:
    def __init__(self, path=None):
        self.path = path or os.path.join(data_dir(), "veri.db")
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- ayarlar ----
    def get_setting(self, key, default=None):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, str(value)))
        self.conn.commit()

    # ---- ders programı ----
    def save_schedule(self, teachers, valid_from, source=""):
        """teachers: {öğretmen: {(gün, saat): bilgi}}. Aynı başlangıç tarihli sürümün yerine geçer."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM schedule_versions WHERE valid_from=?", (valid_from,))
        cur.execute("INSERT INTO schedule_versions (valid_from, source, imported_at) VALUES (?,?,?)",
                    (valid_from, source, dt.datetime.now().isoformat(timespec="seconds")))
        vid = cur.lastrowid
        cur.executemany(
            "INSERT OR REPLACE INTO schedule_entries VALUES (?,?,?,?,?)",
            [(vid, t, d, h, info) for t, slots in teachers.items() for (d, h), info in slots.items()])
        self.conn.commit()
        return vid

    def schedule_versions(self):
        return self.conn.execute(
            "SELECT v.id, v.valid_from, v.source, v.imported_at, COUNT(DISTINCT e.teacher) "
            "FROM schedule_versions v LEFT JOIN schedule_entries e ON e.version_id = v.id "
            "GROUP BY v.id ORDER BY v.valid_from DESC").fetchall()

    def delete_schedule_version(self, vid):
        self.conn.execute("DELETE FROM schedule_versions WHERE id=?", (vid,))
        self.conn.commit()

    def schedule_version_for(self, date):
        row = self.conn.execute(
            "SELECT id FROM schedule_versions WHERE valid_from <= ? ORDER BY valid_from DESC, id DESC "
            "LIMIT 1", (date,)).fetchone()
        if not row:
            row = self.conn.execute(
                "SELECT id FROM schedule_versions ORDER BY valid_from LIMIT 1").fetchone()
        return row[0] if row else None

    def schedule(self, version_id):
        out = {}
        for t, d, h, info in self.conn.execute(
                "SELECT teacher, day, hour, info FROM schedule_entries WHERE version_id=?",
                (version_id,)):
            out.setdefault(t, {})[(d, h)] = info
        return out

    def replace_schedule_entries(self, version_id, teachers):
        self.conn.execute("DELETE FROM schedule_entries WHERE version_id=?", (version_id,))
        self.conn.executemany(
            "INSERT OR REPLACE INTO schedule_entries VALUES (?,?,?,?,?)",
            [(version_id, t, d, h, info) for t, s in teachers.items() for (d, h), info in s.items()])
        self.conn.commit()

    def all_teachers(self):
        return [r[0] for r in self.conn.execute(
            "SELECT DISTINCT teacher FROM schedule_entries ORDER BY teacher")]

    # ---- nöbet ----
    def save_duty(self, month, entries):
        self.conn.execute("DELETE FROM duty_entries WHERE month=?", (month,))
        self.conn.executemany(
            "INSERT INTO duty_entries VALUES (?,?,?,?,?)",
            [(month, e.weekday, e.date, e.teacher, e.place) for e in entries])
        self.conn.commit()

    def duty_months(self):
        return self.conn.execute(
            "SELECT month, COUNT(DISTINCT teacher) FROM duty_entries GROUP BY month "
            "ORDER BY month DESC").fetchall()

    def delete_duty_month(self, month):
        self.conn.execute("DELETE FROM duty_entries WHERE month=?", (month,))
        self.conn.commit()

    def duty_month_for(self, date):
        """Tarihe uygulanacak çizelgenin ayı: o ay yoksa en son yüklenen önceki ay."""
        month = date[:7]
        row = self.conn.execute(
            "SELECT month FROM duty_entries WHERE month <= ? ORDER BY month DESC LIMIT 1",
            (month,)).fetchone()
        return row[0] if row else None

    def duty_rows(self, month):
        return self.conn.execute(
            "SELECT weekday, date, teacher, place FROM duty_entries WHERE month=? "
            "ORDER BY weekday, place, teacher", (month,)).fetchall()

    def duty_for(self, date):
        """Tarihteki nöbetçiler: [(öğretmen, yer)], kullanılan ay."""
        month = self.duty_month_for(date)
        if not month:
            return [], None
        weekday = dt.date.fromisoformat(date).weekday()
        rows = self.conn.execute(
            "SELECT teacher, place FROM duty_entries WHERE month=? AND date=?",
            (month, date)).fetchall()
        if not rows:
            rows = self.conn.execute(
                "SELECT teacher, place FROM duty_entries WHERE month=? AND date IS NULL "
                "AND weekday=?", (month, weekday)).fetchall()
        if not rows:
            # Haftalık çizelgede bu hafta yoksa aynı günün en yakın haftasını kullan.
            near = self.conn.execute(
                "SELECT date FROM duty_entries WHERE month=? AND weekday=? AND date IS NOT NULL "
                "ORDER BY abs(julianday(date) - julianday(?)) LIMIT 1",
                (month, weekday, date)).fetchone()
            if near:
                rows = self.conn.execute(
                    "SELECT teacher, place FROM duty_entries WHERE month=? AND date=?",
                    (month, near[0])).fetchall()
        return rows, month

    # ---- devamsızlık ve görevlendirme ----
    def absences(self, date):
        return dict(self.conn.execute(
            "SELECT teacher, reason FROM absences WHERE date=?", (date,)).fetchall())

    def save_day(self, date, absences, assignments):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM absences WHERE date=?", (date,))
        cur.execute("DELETE FROM assignments WHERE date=?", (date,))
        cur.executemany("INSERT INTO absences VALUES (?,?,?)",
                        [(date, t, r) for t, r in absences.items()])
        cur.executemany("INSERT INTO assignments VALUES (?,?,?,?,?,?,?)",
                        [(date, a.hour, a.absent, a.info, a.assigned, a.kind, a.note)
                         for a in assignments])
        self.conn.commit()

    def delete_day(self, date):
        self.conn.execute("DELETE FROM absences WHERE date=?", (date,))
        self.conn.execute("DELETE FROM assignments WHERE date=?", (date,))
        self.conn.commit()

    def assignments(self, date):
        return self.conn.execute(
            "SELECT hour, absent_teacher, info, assigned, kind, note FROM assignments "
            "WHERE date=? ORDER BY hour, absent_teacher", (date,)).fetchall()

    def saved_dates(self, month):
        return [r[0] for r in self.conn.execute(
            "SELECT DISTINCT date FROM assignments WHERE substr(date,1,7)=? ORDER BY date",
            (month,))]

    def counts(self, month, exclude_date=None):
        """Ay içindeki ders doldurma sayıları: {öğretmen: (toplam, nöbetçi olarak, nöbetçi değilken)}."""
        rows = self.conn.execute(
            "SELECT assigned, kind, COUNT(*) FROM assignments WHERE substr(date,1,7)=? "
            "AND assigned IS NOT NULL AND date != ? GROUP BY assigned, kind",
            (month, exclude_date or "")).fetchall()
        out = {}
        for t, kind, n in rows:
            tot, duty, free = out.get(t, (0, 0, 0))
            tot += n
            if kind == "nobetci":
                duty += n
            elif kind == "bos":
                free += n
            out[t] = (tot, duty, free)
        return out

    def total_counts(self, exclude_date=None):
        return dict(self.conn.execute(
            "SELECT assigned, COUNT(*) FROM assignments WHERE assigned IS NOT NULL AND date != ? "
            "GROUP BY assigned", (exclude_date or "",)).fetchall())

    def duty_days_in_month(self, month):
        """Ay içinde her öğretmenin kaç gün nöbetçi olduğu (iş günleri)."""
        import calendar
        y, m = (int(x) for x in month.split("-"))
        days = calendar.monthrange(y, m)[1]
        out = {}
        for d in range(1, days + 1):
            date = dt.date(y, m, d)
            if date.weekday() >= 5:
                continue
            rows, _ = self.duty_for(date.isoformat())
            for t, _p in rows:
                out[t] = out.get(t, 0) + 1
        return out
