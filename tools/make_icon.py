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
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 512

    # Zemin: yuvarlak köşeli kare, indigo -> mor geçiş
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor("#4f46e5"))
    g.setColorAt(1, QColor("#7c3aed"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawRoundedRect(QRectF(16 * s, 16 * s, 480 * s, 480 * s), 108 * s, 108 * s)

    # Kalkan
    shield = QPainterPath()
    shield.moveTo(256 * s, 86 * s)
    shield.cubicTo(310 * s, 120 * s, 360 * s, 128 * s, 400 * s, 128 * s)
    shield.lineTo(400 * s, 250 * s)
    shield.cubicTo(400 * s, 340 * s, 340 * s, 400 * s, 256 * s, 438 * s)
    shield.cubicTo(172 * s, 400 * s, 112 * s, 340 * s, 112 * s, 250 * s)
    shield.lineTo(112 * s, 128 * s)
    shield.cubicTo(152 * s, 128 * s, 202 * s, 120 * s, 256 * s, 86 * s)
    shield.closeSubpath()
    p.setBrush(QColor("white"))
    p.drawPath(shield)

    # Onay işareti
    pen = QPen(QColor("#4f46e5"), 40 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    check = QPainterPath()
    check.moveTo(QPointF(186 * s, 262 * s))
    check.lineTo(QPointF(238 * s, 314 * s))
    check.lineTo(QPointF(330 * s, 212 * s))
    p.drawPath(check)

    # Küçük takvim rozeti (sağ alt)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#f59e0b"))
    p.drawRoundedRect(QRectF(336 * s, 336 * s, 128 * s, 128 * s), 26 * s, 26 * s)
    p.setBrush(QColor("white"))
    p.drawRoundedRect(QRectF(356 * s, 372 * s, 88 * s, 72 * s), 10 * s, 10 * s)
    p.setBrush(QColor("#f59e0b"))
    for i in range(3):
        for j in range(2):
            p.drawRect(QRectF((368 + i * 26) * s, (386 + j * 26) * s, 14 * s, 14 * s))
    p.setBrush(QColor("white"))
    for x in (376, 424):
        p.drawRoundedRect(QRectF((x - 5) * s, 352 * s, 10 * s, 28 * s), 5 * s, 5 * s)
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
