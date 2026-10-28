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

    # Zemin: yuvarlak köşeli kare, mavi -> turkuaz
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor("#2563eb"))
    g.setColorAt(1, QColor("#0d9488"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawRoundedRect(QRectF(16 * s, 16 * s, 480 * s, 480 * s), 112 * s, 112 * s)

    # Pano
    p.setBrush(QColor(0, 0, 0, 40))
    p.drawRoundedRect(QRectF(120 * s, 104 * s, 272 * s, 328 * s), 34 * s, 34 * s)
    p.setBrush(QColor("white"))
    p.drawRoundedRect(QRectF(112 * s, 94 * s, 272 * s, 328 * s), 34 * s, 34 * s)
    # Kıskaç
    p.setBrush(QColor("#1e3a8a"))
    p.drawRoundedRect(QRectF(184 * s, 70 * s, 128 * s, 54 * s), 22 * s, 22 * s)
    p.setBrush(QColor("white"))
    p.drawEllipse(QRectF(236 * s, 82 * s, 24 * s, 24 * s))

    # Liste: 3 satır, ilk ikisi onaylı
    for i, done in enumerate((True, True, False)):
        y = (172 + i * 78) * s
        box = QRectF(146 * s, y, 50 * s, 50 * s)
        if done:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#10b981"))
            p.drawRoundedRect(box, 12 * s, 12 * s)
            pen = QPen(QColor("white"), 11 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            path = QPainterPath()
            path.moveTo(QPointF(158 * s, y + 26 * s))
            path.lineTo(QPointF(168 * s, y + 36 * s))
            path.lineTo(QPointF(186 * s, y + 14 * s))
            p.drawPath(path)
        else:
            p.setPen(QPen(QColor("#94a3b8"), 7 * s))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(box, 12 * s, 12 * s)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#cbd5e1") if done else QColor("#e2e8f0"))
        p.drawRoundedRect(QRectF(214 * s, y + 10 * s, 136 * s, 14 * s), 7 * s, 7 * s)
        p.drawRoundedRect(QRectF(214 * s, y + 32 * s, 92 * s, 12 * s), 6 * s, 6 * s)

    # Saat rozeti (sağ alt)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#f59e0b"))
    p.drawEllipse(QRectF(318 * s, 318 * s, 150 * s, 150 * s))
    p.setBrush(QColor("white"))
    p.drawEllipse(QRectF(340 * s, 340 * s, 106 * s, 106 * s))
    pen = QPen(QColor("#b45309"), 12 * s, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(393 * s, 393 * s), QPointF(393 * s, 357 * s))
    p.drawLine(QPointF(393 * s, 393 * s), QPointF(420 * s, 408 * s))
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
