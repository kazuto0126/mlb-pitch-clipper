"""Measure within-shot visual homogeneity for guard calibration."""
import sys

sys.path.insert(0, ".")

import cv2
import numpy as np

from src.clipper.motion import grab_frame, hist_corr

CASES = [
    # (name, video, start, end, expect)
    ("oht-s005-BAD", r"C:\Users\lingz\AppData\Local\Temp\opencode\mlb_test_ohtani.mp4",
     35.6, 42.2, "veto"),
    ("cro-s024-BAD", None, 129.7, 145.9, "veto"),  # filled below
    ("cro-s087-BAD", None, 440.8, 448.8, "veto"),
    ("oht-s030-BAD", None, 185.8, 213.8, "veto"),
    ("yam-s013-GOOD", None, 116.9, 125.5, "keep"),
    ("ske-s000-GOOD", None, 0.0, 7.4, "keep"),
    ("mil-s000-GOOD", None, 0.0, 7.0, "keep"),
]
VIDS = {
    "cro-s024-BAD": "output/garrett-crochet/20260923T104950Z/sources/myyfpqlODso/source/original.mp4",
    "cro-s087-BAD": "output/garrett-crochet/20260923T104950Z/sources/myyfpqlODso/source/original.mp4",
    "oht-s030-BAD": "output/shohei-ohtani/20260923T100612Z/sources/av5KQk1HNbc/source/original.mp4",
    "yam-s013-GOOD": "output/yoshinobu-yamamoto/20260923T005044Z/sources/Q8Bl2X4VKuw/source/original.mp4",
    "ske-s000-GOOD": "output/paul-skenes/20260923T095225Z/sources/q2dSaXzowlw/source/original.mp4",
    "mil-s000-GOOD": "output/mason-miller/20260923T111351Z/sources/q7ndAVBppQQ/source/original.mp4",
}

for name, vid, s, e, exp in CASES:
    vid = vid or VIDS[name]
    ts = [s + (e - s) * f for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
    fr = [grab_frame(vid, t) for t in ts]
    assert all(f is not None for f in fr), name
    adj = [round(hist_corr(fr[i], fr[i + 1]), 3) for i in range(4)]
    edge = round(hist_corr(fr[0], fr[-1]), 3)
    print(f"{name:16s} adj={adj} min_adj={min(adj)} edge={edge} expect={exp}")
