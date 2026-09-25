"""Green-field fraction probe: verified CF vs close-up FPs."""
import sys

sys.path.insert(0, ".")

import cv2
import numpy as np

from src.clipper.motion import grab_frame

CASES = [
    # bad
    ("cro-s024", "output/garrett-crochet/20260923T104950Z/sources/myyfpqlODso/source/original.mp4", 136.0, 138.7),
    ("oht-s079", "output/shohei-ohtani/20260923T100612Z/sources/av5KQk1HNbc/source/original.mp4", 517.3, 520.4),
    ("yam-s236", "output/yoshinobu-yamamoto/20260923T005044Z/sources/Q8Bl2X4VKuw/source/original.mp4", 1562.6 - 2, 1562.6 + 2),
    ("tail-s060", "output/paul-skenes/20260923T095225Z/sources/q2dSaXzowlw/source/original.mp4", 319.3, 338.6),
    # good (audited-true events)
    ("oht-s118", "output/shohei-ohtani/20260923T100612Z/sources/av5KQk1HNbc/source/original.mp4", 763.6, 766.4),
    ("yam-s013", "output/yoshinobu-yamamoto/20260923T005044Z/sources/Q8Bl2X4VKuw/source/original.mp4", 118.2, 123.6),
    ("ske-ev", "output/paul-skenes/20260923T095225Z/sources/q2dSaXzowlw/source/original.mp4", 0.2, 4.1),
    ("mil-ev", "output/mason-miller/20260923T111351Z/sources/q7ndAVBppQQ/source/original.mp4", 1.6, 6.3),
    ("cro-s076", "output/garrett-crochet/20260923T104950Z/sources/myyfpqlODso/source/original.mp4", 377.1, 379.6),
]


def green_frac(img):
    hsv = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2HSV)
    m = ((hsv[..., 0] > 35) & (hsv[..., 0] < 85) & (hsv[..., 1] > 40))
    return round(float(m.mean()), 3)


for name, vid, s, e in CASES:
    ts = [s + (e - s) * f for f in (0.2, 0.5, 0.8)]
    fr = [grab_frame(vid, t) for t in ts]
    print(name, [green_frac(f) for f in fr])
