"""Türkçe isim normalleştirme ve öğretmen adı eşleştirme."""
import difflib
import re

_TR_MAP = str.maketrans({
    "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
    "â": "a", "î": "i", "û": "u",
})

DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]

_DAY_KEYS = [
    ("pazartesi", 0), ("pzt", 0), ("pts", 0),
    ("sali", 1), ("sal", 1),
    ("carsamba", 2), ("crs", 2), ("car", 2),
    ("persembe", 3), ("prs", 3), ("per", 3),
    ("cuma", 4), ("cum", 4),
]


def tr_lower(text: str) -> str:
    return text.replace("I", "ı").replace("İ", "i").lower()


def tr_upper(text: str) -> str:
    return text.replace("i", "İ").replace("ı", "I").upper()


def normalize(text) -> str:
    """Büyük/küçük harf ve Türkçe karakter farklarını yok sayan anahtar."""
    if text is None:
        return ""
    s = tr_lower(str(text)).translate(_TR_MAP)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def clean_name(text: str) -> str:
    """Görüntülemek için ismi düzenler: 'ahmet  YILMAZ' -> 'Ahmet YILMAZ'."""
    s = re.sub(r"\s+", " ", str(text or "")).strip(" .,-:;/")
    return s


def parse_day(text):
    """Hücredeki gün adını 0-4 arası indekse çevirir; gün değilse None."""
    s = normalize(text)
    if not s:
        return None
    first = s.split(" ")[0]
    if first.startswith("cumartesi") or first.startswith("pazar") and not first.startswith("pazartesi"):
        return None
    for key, idx in _DAY_KEYS:
        if first == key or (len(key) >= 4 and first.startswith(key)):
            return idx
    # "Çarş.", "Perş", "Pazt" gibi kısaltmalar
    if len(first) >= 3 and first != "paz":
        for idx, full in enumerate(("pazartesi", "sali", "carsamba", "persembe", "cuma")):
            if full.startswith(first):
                return idx
    # "1.gün" gibi ifadeler gün değildir; kısaltmalar yalnızca tam eşleşirse kabul.
    return None


def looks_like_class(text) -> bool:
    """'9-A', '10/B', '11 C', 'Hazırlık A', '5A' gibi şube adları."""
    s = normalize(text)
    if not s:
        return False
    if re.fullmatch(r"(\d{1,2}) ?[a-z]{1,2}", s.replace(" sinif", "")):
        return True
    if re.fullmatch(r"(hazirlik|hz|anasinifi|ana sinifi) ?[a-z]?", s):
        return True
    return False


def looks_like_person(text) -> bool:
    """En az iki kelimeden oluşan, rakam içermeyen ifade."""
    s = clean_name(text)
    if not s or re.search(r"\d", s):
        return False
    words = [w for w in re.split(r"[\s.]+", s) if w]
    if len(words) < 2 or len(words) > 5:
        return False
    return all(re.fullmatch(r"[A-Za-zÇĞİÖŞÜçğıöşüÂâÎîÛû'-]+", w) for w in words)


class NameMatcher:
    """Bilinen öğretmen listesine karşı bulanık eşleştirme yapar."""

    def __init__(self, names):
        self.names = sorted(set(n for n in names if n))
        self._norm = {n: normalize(n) for n in self.names}
        self._by_norm = {}
        for n, k in self._norm.items():
            self._by_norm.setdefault(k, n)

    def match(self, text):
        key = normalize(text)
        if len(key) < 3:
            return None
        if key in self._by_norm:
            return self._by_norm[key]
        tokens = key.split()
        # Boşluk farkı: "ÜMMÜGÜLSÜM KÖKLÜ" == "ÜMMÜ GÜLSÜM KÖKLÜ"
        squashed = key.replace(" ", "")
        hits = [n for n, k in self._norm.items() if k.replace(" ", "") == squashed]
        if len(hits) == 1:
            return hits[0]
        # Kelime kümesi: "YILMAZ Ahmet" == "Ahmet YILMAZ"
        hits = [n for n, k in self._norm.items() if sorted(k.split()) == sorted(tokens)]
        if len(hits) == 1:
            return hits[0]
        # Baş harf + soyad: "A. YILMAZ" veya "Ahmet Y."
        if len(tokens) >= 2:
            hits = [n for n, k in self._norm.items() if _initial_match(tokens, k.split())]
            if len(hits) == 1:
                return hits[0]
        # İkinci adı yazılmamış: "Mehmet Ali KAYA" -> "Mehmet KAYA"
        if len(tokens) >= 2:
            hits = [n for n, k in self._norm.items()
                    if set(tokens) <= set(k.split()) or set(k.split()) <= set(tokens)]
            hits = [h for h in hits if len(self._norm[h].split()) >= 2]
            if len(hits) == 1:
                return hits[0]
        close = difflib.get_close_matches(key, list(self._by_norm), n=2, cutoff=0.85)
        if len(close) == 1 or (len(close) == 2 and
                               difflib.SequenceMatcher(None, key, close[0]).ratio() -
                               difflib.SequenceMatcher(None, key, close[1]).ratio() > 0.05):
            return self._by_norm[close[0]]
        return None

    def find_all(self, text):
        """Bir hücrede geçen tüm öğretmenleri döndürür (satır, virgül, tire ile ayrılmış)."""
        if not text:
            return []
        found = []
        parts = re.split(r"[\n,;/+&]| - | – |\s{3,}", str(text))
        for part in parts:
            m = self.match(part)
            if m:
                found.append(m)
        if not found:
            # Tüm hücre içinde bilinen isimleri ara (ayırıcı olmayan durumlar için).
            whole = " " + normalize(text) + " "
            for n, k in self._norm.items():
                if len(k) >= 5 and (" " + k + " ") in whole:
                    found.append(n)
        out = []
        for f in found:
            if f not in out:
                out.append(f)
        return out


def _initial_match(a, b):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x == y:
            continue
        if len(x) == 1 and y.startswith(x):
            continue
        if len(y) == 1 and x.startswith(y):
            continue
        return False
    return True


_CLASS_RE = re.compile(r"(?<![\w/])(\d{1,2}\s*[-/.]?\s*[A-ZÇĞİÖŞÜ])(?![\wçğıöşü])")


def split_info(info):
    """'TÜRKÇE 6/B' veya '9-A Matematik' -> ('6/B', 'TÜRKÇE'). Sınıf bulunamazsa ('', info)."""
    text = re.sub(r"\s+", " ", str(info or "")).strip()
    classes = []
    for m in _CLASS_RE.finditer(text):
        c = m.group(1).replace(" ", "")
        if c not in classes:
            classes.append(c)
    if not classes:
        return "", text
    lesson = _CLASS_RE.sub(" ", text)
    lesson = re.sub(r"\s*\+\s*", " ", lesson)
    words = []
    for w in lesson.split():
        if w not in words:
            words.append(w)
    return ", ".join(classes), " ".join(words).strip(" -,")


def lesson_label(ders):
    """Ders adı belgede nasıl yazıyorsa öyle gösterilir ("DESTEK", "BİLG." …); yalnızca
    fazla boşluklar temizlenir."""
    return re.sub(r"\s+", " ", str(ders or "")).strip()


def needs_class(info):
    """Sınıfı olması gereken ama yazılmamış ders mi? "DESTEK" dersleri belgede sınıfsız
    yazılır; olduğu gibi bırakılır, eksik sayılmaz."""
    return bool(info) and not split_info(info)[0] and "destek" not in normalize(info)
