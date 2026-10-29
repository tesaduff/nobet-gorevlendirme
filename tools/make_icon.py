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
    """Simge: sıcak renkli zeminde öğretmen figürü ve onu çevreleyen iki yönlü oklar
    (gelmeyenin yerine görevlendirme), köşede takvim rozeti (nöbet çizelgesi)."""
    import math
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 512

    # Zemin: turuncudan pembeye canlı geçiş, üstten yumuşak parlama
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor("#fbbf24"))
    g.setColorAt(0.45, QColor("#f97316"))
    g.setColorAt(1, QColor("#db2777"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawRoundedRect(QRectF(10 * s, 10 * s, 492 * s, 492 * s), 124 * s, 124 * s)
    shine = QLinearGradient(0, 0, 0, size)
    shine.setColorAt(0, QColor(255, 255, 255, 80))
    shine.setColorAt(0.5, QColor(255, 255, 255, 0))
    p.setBrush(QBrush(shine))
    p.drawRoundedRect(QRectF(10 * s, 10 * s, 492 * s, 492 * s), 124 * s, 124 * s)

    cx, cy = 248 * s, 262 * s
    # İki yönlü dairesel oklar
    ring = 158 * s
    pen = QPen(QColor("white"), 34 * s, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    rect = QRectF(cx - ring, cy - ring, 2 * ring, 2 * ring)
    for start in (20, 200):                      # iki yay, aralarında boşluk
        p.drawArc(rect, int(start * 16), int(130 * 16))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("white"))
    for end in (150, 330):                       # yayların ucunda ok başları
        ang = math.radians(end)
        tip = QPointF(cx + ring * math.cos(ang), cy - ring * math.sin(ang))
        # yay yönüne teğet (saat yönünün tersi)
        tx, ty = -math.sin(ang), -math.cos(ang)
        nx, ny = math.cos(ang), -math.sin(ang)
        L, W = 62 * s, 46 * s
        head = QPainterPath()
        head.moveTo(QPointF(tip.x() + tx * L * 0.55, tip.y() + ty * L * 0.55))
        head.lineTo(QPointF(tip.x() - tx * L * 0.45 + nx * W, tip.y() - ty * L * 0.45 + ny * W))
        head.lineTo(QPointF(tip.x() - tx * L * 0.45 - nx * W, tip.y() - ty * L * 0.45 - ny * W))
        head.closeSubpath()
        p.drawPath(head)

    # Öğretmen figürü (baş + omuzlar), hafif gölgeli
    for dy, color in ((10 * s, QColor(124, 45, 18, 90)), (0, QColor("white"))):
        p.setBrush(color)
        p.drawEllipse(QPointF(cx, cy - 46 * s + dy), 46 * s, 46 * s)
        body = QPainterPath()
        body.moveTo(QPointF(cx - 82 * s, cy + 86 * s + dy))
        body.cubicTo(QPointF(cx - 82 * s, cy + 18 * s + dy), QPointF(cx - 42 * s, cy + 8 * s + dy),
                     QPointF(cx, cy + 8 * s + dy))
        body.cubicTo(QPointF(cx + 42 * s, cy + 8 * s + dy), QPointF(cx + 82 * s, cy + 18 * s + dy),
                     QPointF(cx + 82 * s, cy + 86 * s + dy))
        body.closeSubpath()
        p.drawPath(body)

    # Takvim rozeti (sağ üst)
    bx, by, bw = 352 * s, 52 * s, 118 * s
    p.setBrush(QColor(15, 23, 42, 70))
    p.drawRoundedRect(QRectF(bx, by + 8 * s, bw, bw), 26 * s, 26 * s)
    p.setPen(QPen(QColor("white"), 8 * s))
    p.setBrush(QColor("#1e3a8a"))
    p.drawRoundedRect(QRectF(bx, by, bw, bw), 26 * s, 26 * s)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#ef4444"))
    top = QPainterPath()
    top.addRoundedRect(QRectF(bx + 4 * s, by + 4 * s, bw - 8 * s, 34 * s), 22 * s, 22 * s)
    p.drawPath(top)
    p.setBrush(QColor("white"))
    for i in range(3):
        for j in range(2):
            p.drawRoundedRect(QRectF(bx + (18 + i * 30) * s, by + (50 + j * 30) * s, 22 * s, 20 * s),
                              5 * s, 5 * s)
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
