"""Genel belge okuyucu: PDF, Excel ve CSV dosyalarından tablo + metin çıkarır.

Her belge "sayfa" listesine dönüşür. Bir sayfa: {"text": str, "tables": [[[hücre, ...], ...], ...]}
Excel'de her çalışma sayfası bir sayfa olarak döner.
"""
import csv
import os


class ReadError(Exception):
    pass


def read_document(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _read_pdf(path)
    if ext in (".xlsx", ".xlsm"):
        return _read_xlsx(path)
    if ext == ".csv":
        return _read_csv(path)
    raise ReadError(f"Desteklenmeyen dosya türü: {ext} (PDF, XLSX veya CSV seçin)")


def _cell(v):
    if v is None:
        return ""
    return str(v).replace("\r", "").strip()


def _read_pdf(path):
    try:
        import pdfplumber
    except ImportError as e:  # pragma: no cover
        raise ReadError("pdfplumber kurulu değil") from e
    pages = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                tables = []
                # Önce çizgili tablo, bulunamazsa metin hizasına göre tablo dene.
                for settings in (None, {"vertical_strategy": "text", "horizontal_strategy": "lines"},
                                 {"vertical_strategy": "text", "horizontal_strategy": "text"}):
                    try:
                        raw = page.extract_tables(settings) if settings else page.extract_tables()
                    except Exception:
                        raw = []
                    raw = [t for t in raw if t and len(t) >= 2 and max(len(r) for r in t) >= 3]
                    if raw:
                        tables = [[[_cell_raw(c) for c in row] for row in t] for t in raw]
                        break
                pages.append({"text": text, "tables": tables})
    except ReadError:
        raise
    except Exception as e:
        raise ReadError(f"PDF okunamadı: {e}") from e
    if not any(p["text"].strip() or p["tables"] for p in pages):
        raise ReadError("PDF'te okunabilir metin yok. Belge taranmış (resim) olabilir; "
                        "e-Okul/MEBBİS'ten PDF veya Excel olarak yeniden indirin.")
    return pages


def _cell_raw(v):
    # PDF'te birleştirilmiş hücreler None döner; bunu "" yerine None olarak korumak
    # başlıkları sağa doğru doldurmak için gerekli.
    if v is None:
        return None
    return str(v).replace("\r", "").strip()


def _read_xlsx(path):
    try:
        import openpyxl
    except ImportError as e:  # pragma: no cover
        raise ReadError("openpyxl kurulu değil") from e
    try:
        wb = openpyxl.load_workbook(path, data_only=True, read_only=False)
    except Exception as e:
        raise ReadError(f"Excel dosyası açılamadı: {e}") from e
    pages = []
    for ws in wb.worksheets:
        rows = []
        merged_tail = set()
        for rng in ws.merged_cells.ranges:
            for r in range(rng.min_row, rng.max_row + 1):
                for c in range(rng.min_col, rng.max_col + 1):
                    if (r, c) != (rng.min_row, rng.min_col):
                        merged_tail.add((r, c))
        for r_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            cells = []
            for c_idx, v in enumerate(row, start=1):
                cells.append(None if (r_idx, c_idx) in merged_tail else _cell(v))
            if any(cells):
                rows.append(cells)
        text = "\n".join(" ".join(c for c in r if c) for r in rows)
        pages.append({"text": text, "tables": [rows] if rows else []})
    return pages


def _read_csv(path):
    for enc in ("utf-8-sig", "cp1254", "latin-1"):
        try:
            with open(path, newline="", encoding=enc) as f:
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
                except csv.Error:
                    dialect = csv.excel
                rows = [[_cell(c) for c in r] for r in csv.reader(f, dialect)]
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ReadError("CSV kodlaması çözülemedi")
    rows = [r for r in rows if any(r)]
    text = "\n".join(" ".join(c for c in r if c) for r in rows)
    return [{"text": text, "tables": [rows] if rows else []}]
