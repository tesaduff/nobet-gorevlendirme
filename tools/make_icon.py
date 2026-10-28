"""Program simgesini üretir: assets/icon.png (512px) ve assets/icon.ico (çok boyutlu).

Çalıştırmak için: python tools/make_icon.py   (PySide6 ve Pillow gerekir)
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen)

OUT = os.path.join(os.path.dirname(__file__), "..", "assets")


def draw(size=512):
    """Sade ve güçlü simge: takvim sayfası (nöbet çizelgesi) + kalın onay (görevlendirme)
    + köşede kalkan (nöbet). Küçük boyutta da okunacak kadar az ayrıntı."""
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 512

    # Zemin: canlı geçiş + üstte hafif parlama
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor("#7c3aed"))
    g.setColorAt(1, QColor("#2563eb"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawRoundedRect(QRectF(12 * s, 12 * s, 488 * s, 488 * s), 116 * s, 116 * s)
    shine = QLinearGradient(0, 0, 0, 260 * s)
    shine.setColorAt(0, QColor(255, 255, 255, 60))
    shine.setColorAt(1, QColor(255, 255, 255, 0))
    p.setBrush(QBrush(shine))
    p.drawRoundedRect(QRectF(12 * s, 12 * s, 488 * s, 250 * s), 116 * s, 116 * s)

    # Takvim sayfası (gölgeli)
    page = QRectF(96 * s, 116 * s, 320 * s, 300 * s)
    p.setBrush(QColor(15, 23, 42, 70))
    p.drawRoundedRect(page.translated(0, 12 * s), 44 * s, 44 * s)
    p.setBrush(QColor("white"))
    p.drawRoundedRect(page, 44 * s, 44 * s)
    # Turuncu üst şerit
    head = QPainterPath()
    head.addRoundedRect(QRectF(96 * s, 116 * s, 320 * s, 96 * s), 44 * s, 44 * s)
    cut = QPainterPath()
    cut.addRect(QRectF(96 * s, 170 * s, 320 * s, 42 * s))
    p.setBrush(QColor("#f97316"))
    p.drawPath(head.united(cut))
    # Halkalar
    for x in (176, 336):
        p.setBrush(QColor("#1e293b"))
        p.drawRoundedRect(QRectF((x - 15) * s, 84 * s, 30 * s, 76 * s), 15 * s, 15 * s)
    # Kalın onay işareti
    pen = QPen(QColor("#16a34a"), 50 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    check = QPainterPath()
    check.moveTo(QPointF(174 * s, 314 * s))
    check.lineTo(QPointF(236 * s, 368 * s))
    check.lineTo(QPointF(340 * s, 254 * s))
    p.drawPath(check)

    # Kalkan rozeti (sağ alt)
    p.setPen(QPen(QColor("white"), 14 * s))
    p.setBrush(QColor("#facc15"))
    shield = QPainterPath()
    cx, top = 388 * s, 300 * s
    shield.moveTo(cx, top)
    shield.cubicTo(cx + 34 * s, top + 18 * s, cx + 58 * s, top + 20 * s, cx + 70 * s, top + 20 * s)
    shield.lineTo(cx + 70 * s, top + 80 * s)
    shield.cubicTo(cx + 70 * s, top + 124 * s, cx + 36 * s, top + 148 * s, cx, top + 164 * s)
    shield.cubicTo(cx - 36 * s, top + 148 * s, cx - 70 * s, top + 124 * s, cx - 70 * s, top + 80 * s)
    shield.lineTo(cx - 70 * s, top + 20 * s)
    shield.cubicTo(cx - 58 * s, top + 20 * s, cx - 34 * s, top + 18 * s, cx, top)
    shield.closeSubpath()
    p.drawPath(shield)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#b45309"))
    star = QPainterPath()
    import math
    for i in range(10):
        r = (30 if i % 2 == 0 else 13) * s
        ang = -math.pi / 2 + i * math.pi / 5
        pt = QPointF(cx + r * math.cos(ang), top + 84 * s + r * math.sin(ang))
        star.moveTo(pt) if i == 0 else star.lineTo(pt)
    star.closeSubpath()
    p.drawPath(star)
    p.end()
    return img


def main():
    QGuiApplication(sys.argv)
    os.makedirs(OUT, exist_ok=True)
    png = os.path.join(OUT, "icon.png")
    draw(512).save(png)
    from PIL import Image
    Image.open(png).save(os.path.join(OUT, "icon.ico"),
                         sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
                                (256, 256)])
    print("assets/icon.png ve assets/icon.ico oluşturuldu")


if __name__ == "__main__":
    main()
