"""Spatial-complexity probe: edge density + color entropy, bad vs good."""
import sys

sys.path.insert(0, ".")

import cv2
import numpy as np

from src.clipper.motion import grab_frame

VID = {
    "cro": "output/garrett-crochet/20260923T104950Z/sources/myyfpqlODso/source/original.mp4",
    "oht": "output/shohei-ohtani/20260923T100612Z/sources/av5KQk1HNbc/source/original.mp4",
    "yam": "output/yoshinobu-yamamoto/20260923T005044Z/sources/Q8Bl2X4VKuw/source/original.mp4",
    "ske": "output/paul-skenes/20260923T095225Z/sources/q2dSaXzowlw/source/original.mp4",
    "mil": "output/mason-miller/20260923T111351Z/sources/q7ndAVBppQQ/source/original.mp4",
    "dev": r"C:\Users\lingz\AppData\Local\Temp\opencode\mlb_test_ohtani.mp4",
}
CASES = [
    ("BAD cro-s024", "cro", 137.0), ("BAD oht-s079", "oht", 518.5),
    ("BAD yam-s236", "yam", 1564.0), ("BAD yam-s322", "yam", 2105.0),
    ("GOOD oht-s118", "oht", 765.0), ("GOOD yam-s013", "yam", 121.0),
    ("GOOD ske-ev", "ske", 2.0), ("GOOD mil-ev", "mil", 4.0),
    ("GOOD cro-s076", "cro", 378.0), ("GOOD dev-s035", "dev", 226.0),
]


def stats(img):
    a = cv2.resize(img, (256, 144))
    a = cv2.cvtColor(a, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    edge = cv2.Canny(gray, 80, 160).mean() / 255.0
    q = (a // 32).reshape(-1, 3)
    ent = len(np.unique(q, axis=0)) / len(q)
    return round(edge, 4), round(ent, 4)


for name, v, t in CASES:
    f = grab_frame(VID[v], t)
    print(name, stats(f) if f is not None else "UNREADABLE")
