"""GitHub Releases üzerinden kendini güncelleme."""
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import urllib.request

from .version import __version__

REPO = "tesaduff/nobet-gorevlendirme"
ASSET_NAME = "NobetGorevlendirme.exe"            # taşınabilir tek dosya
INSTALLER_NAME = "NobetGorevlendirme-Kurulum.exe"  # kurulum sihirbazı
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"


class UpdateError(Exception):
    pass


def _parse(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def is_newer(remote, local=__version__):
    return _parse(remote) > _parse(local)


def _ssl_context():
    """Sertifikaları Windows'un kendi deposuyla doğrular.

    Okul/kurum ağları (ör. MEB filtresi) HTTPS trafiğini kendi sertifikalarıyla denetler.
    Bu sertifikalar Windows'a yüklüdür ama Python'un kendi listesinde yoktur; truststore
    doğrulamayı işletim sistemine bırakarak tarayıcının güvendiği her bağlantıya güvenir.
    """
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        return ssl.create_default_context()


def _request(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={
        "Accept": accept, "User-Agent": "NobetGorevlendirme/" + __version__})
    return urllib.request.urlopen(req, timeout=30, context=_ssl_context())


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
    want = INSTALLER_NAME if is_installed() else ASSET_NAME
    asset = next((a for a in data.get("assets", []) if a["name"].lower() == want.lower()), None)
    return {
        "version": data.get("tag_name", "").lstrip("vV"),
        "notes": data.get("body") or "",
        "url": asset["browser_download_url"] if asset else None,
        "size": asset["size"] if asset else 0,
    }


def is_installed():
    """Kurulum sihirbazıyla kurulduysa (yanında kaldırma programı vardır)."""
    if not getattr(sys, "frozen", False):
        return False
    return os.path.exists(os.path.join(os.path.dirname(sys.executable), "unins000.exe"))


def can_self_update():
    return getattr(sys, "frozen", False) and sys.platform == "win32"


def download(info, progress=None):
    """Yeni exe'yi mevcut exe'nin yanına indirir ve yolunu döndürür."""
    if not info.get("url"):
        raise UpdateError("Sürümde exe dosyası bulunamadı.")
    exe = sys.executable
    if is_installed():
        target = os.path.join(tempfile.gettempdir(), INSTALLER_NAME)
    else:
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
    """Program kapandıktan sonra güncellemeyi uygulayan ve programı yeniden açan betik başlatır.

    Kurulu sürümde yeni kurulum sihirbazı sessizce çalıştırılır (programı kendisi açar);
    taşınabilir sürümde exe dosyası yenisiyle değiştirilir.
    """
    exe = sys.executable
    script = os.path.join(tempfile.gettempdir(), "nobet_guncelle.bat")
    if new_file.lower().endswith(INSTALLER_NAME.lower()):
        with open(script, "w", encoding="cp1254", errors="replace") as f:
            f.write(f"""@echo off
timeout /t 2 /nobreak >nul
"{new_file}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
del "%~f0"
""")
        subprocess.Popen(["cmd", "/c", script], creationflags=0x08000000)  # CREATE_NO_WINDOW
        return
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
