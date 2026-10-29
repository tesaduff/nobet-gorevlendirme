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
    """Güçlü ve sade simge: canlı zeminde beyaz kalkan (nöbet), içinde saat (ders saati /
    görevlendirme) ve köşede yeşil onay rozeti. 16 piksele kadar okunur."""
    import math
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 512

    # Zemin: lacivertten turkuaza çapraz geçiş, üstte parlama
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor("#1e1b4b"))
    g.setColorAt(0.55, QColor("#4338ca"))
    g.setColorAt(1, QColor("#06b6d4"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawRoundedRect(QRectF(10 * s, 10 * s, 492 * s, 492 * s), 120 * s, 120 * s)
    shine = QLinearGradient(0, 0, 0, size)
    shine.setColorAt(0, QColor(255, 255, 255, 70))
    shine.setColorAt(0.45, QColor(255, 255, 255, 0))
    p.setBrush(QBrush(shine))
    p.drawRoundedRect(QRectF(10 * s, 10 * s, 492 * s, 492 * s), 120 * s, 120 * s)

    # Kalkan
    def shield_path(cx, top, w, h):
        path = QPainterPath()
        path.moveTo(cx, top)
        path.cubicTo(cx + w * 0.30, top + h * 0.10, cx + w * 0.42, top + h * 0.11, cx + w * 0.5,
                     top + h * 0.11)
        path.lineTo(cx + w * 0.5, top + h * 0.50)
        path.cubicTo(cx + w * 0.5, top + h * 0.78, cx + w * 0.24, top + h * 0.92, cx, top + h)
        path.cubicTo(cx - w * 0.24, top + h * 0.92, cx - w * 0.5, top + h * 0.78, cx - w * 0.5,
                     top + h * 0.50)
        path.lineTo(cx - w * 0.5, top + h * 0.11)
        path.cubicTo(cx - w * 0.42, top + h * 0.11, cx - w * 0.30, top + h * 0.10, cx, top)
        path.closeSubpath()
        return path

    cx = 256 * s
    p.setBrush(QColor(15, 23, 42, 90))
    p.drawPath(shield_path(cx, 72 * s + 14 * s, 330 * s, 380 * s))
    p.setBrush(QColor("white"))
    p.drawPath(shield_path(cx, 72 * s, 330 * s, 380 * s))

    # Saat: lacivert halka, turuncu akrep ve yelkovan
    cy, r = 250 * s, 104 * s
    p.setBrush(QColor("#eef2ff"))
    p.setPen(QPen(QColor("#312e81"), 22 * s))
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.setPen(QPen(QColor("#312e81"), 9 * s, Qt.SolidLine, Qt.RoundCap))
    for i in range(12):
        ang = i * math.pi / 6
        inner = r - (30 if i % 3 == 0 else 20) * s
        p.drawLine(QPointF(cx + inner * math.sin(ang), cy - inner * math.cos(ang)),
                   QPointF(cx + (r - 12 * s) * math.sin(ang), cy - (r - 12 * s) * math.cos(ang)))
    hand = QPen(QColor("#f97316"), 20 * s, Qt.SolidLine, Qt.RoundCap)
    p.setPen(hand)
    p.drawLine(QPointF(cx, cy), QPointF(cx, cy - 66 * s))
    p.drawLine(QPointF(cx, cy), QPointF(cx + 50 * s, cy + 18 * s))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#312e81"))
    p.drawEllipse(QPointF(cx, cy), 15 * s, 15 * s)

    # Yeşil onay rozeti (sağ alt)
    bx, by, br = 376 * s, 372 * s, 78 * s
    p.setBrush(QColor(15, 23, 42, 90))
    p.drawEllipse(QPointF(bx, by + 8 * s), br, br)
    p.setPen(QPen(QColor("white"), 14 * s))
    p.setBrush(QColor("#16a34a"))
    p.drawEllipse(QPointF(bx, by), br, br)
    p.setPen(QPen(QColor("white"), 26 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    check = QPainterPath()
    check.moveTo(QPointF(bx - 38 * s, by + 2 * s))
    check.lineTo(QPointF(bx - 10 * s, by + 30 * s))
    check.lineTo(QPointF(bx + 40 * s, by - 26 * s))
    p.drawPath(check)
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
