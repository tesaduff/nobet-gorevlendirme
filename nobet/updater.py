"""GitHub Releases üzerinden kendini güncelleme."""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

from .version import __version__

REPO = "tesaduff/nobet-gorevlendirme"
ASSET_NAME = "NobetGorevlendirme.exe"
API = f"https://api.github.com/repos/{REPO}/releases/latest"


class UpdateError(Exception):
    pass


def _parse(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def is_newer(remote, local=__version__):
    return _parse(remote) > _parse(local)


def _request(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={
        "Accept": accept, "User-Agent": "NobetGorevlendirme/" + __version__})
    return urllib.request.urlopen(req, timeout=30)


def check():
    """En son sürümü döndürür: {'version', 'notes', 'url', 'size'} veya hata."""
    try:
        with _request(API) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError("Henüz yayınlanmış bir sürüm yok.") from e
        raise UpdateError(f"GitHub yanıtı: {e.code}") from e
    except Exception as e:
        raise UpdateError(f"İnternete bağlanılamadı: {e}") from e
    asset = next((a for a in data.get("assets", []) if a["name"].lower() == ASSET_NAME.lower()),
                 None)
    return {
        "version": data.get("tag_name", "").lstrip("vV"),
        "notes": data.get("body") or "",
        "url": asset["browser_download_url"] if asset else None,
        "size": asset["size"] if asset else 0,
    }


def can_self_update():
    return getattr(sys, "frozen", False) and sys.platform == "win32"


def download(info, progress=None):
    """Yeni exe'yi mevcut exe'nin yanına indirir ve yolunu döndürür."""
    if not info.get("url"):
        raise UpdateError("Sürümde exe dosyası bulunamadı.")
    exe = sys.executable
    target = exe + ".yeni"
    try:
        with _request(info["url"], accept="application/octet-stream") as r, \
                open(target, "wb") as f:
            total = int(r.headers.get("Content-Length") or info.get("size") or 0)
            done = 0
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except PermissionError as e:
        raise UpdateError("Programın bulunduğu klasöre yazılamıyor. Exe'yi Masaüstü veya "
                          "Belgeler gibi bir klasöre taşıyın.") from e
    except Exception as e:
        raise UpdateError(f"İndirme başarısız: {e}") from e
    if os.path.getsize(target) < 1_000_000:
        os.remove(target)
        raise UpdateError("İndirilen dosya bozuk görünüyor.")
    return target


def apply_and_restart(new_file):
    """Program kapandıktan sonra exe'yi değiştiren ve yeniden açan bir betik başlatır."""
    exe = sys.executable
    script = os.path.join(tempfile.gettempdir(), "nobet_guncelle.bat")
    with open(script, "w", encoding="cp1254", errors="replace") as f:
        f.write(f"""@echo off
set /a n=0
:bekle
timeout /t 1 /nobreak >nul
move /y "{new_file}" "{exe}" >nul 2>&1
if not errorlevel 1 goto tamam
set /a n+=1
if %n% lss 30 goto bekle
:tamam
start "" "{exe}"
del "%~f0"
""")
    subprocess.Popen(["cmd", "/c", script], creationflags=0x08000000)  # CREATE_NO_WINDOW
