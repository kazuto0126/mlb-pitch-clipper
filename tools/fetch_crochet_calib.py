"""One-off calibration material: 3 sections of Crochet every_pitch (LHP)."""
import sys

sys.path.insert(0, ".")

from src.clipper.acquisition.preview_acquire import download_section
from src.clipper.pipeline import run_pipeline as run_m1

URL = "https://www.youtube.com/watch?v=myyfpqlODso"
DUR = 23 * 60
for i, frac in enumerate((0.30, 0.50, 0.70)):
    start = DUR * frac - 10.0
    dest = f"output/calib_crochet/seg{i:02d}.mp4"
    import os
    os.makedirs("output/calib_crochet", exist_ok=True)
    p = download_section(URL, start, 20.0, dest)
    print(i, p.method, p.error)
    if p.method != "failed":
        run_m1(dest, f"output/calib_crochet/m1_{i:02d}", prefer_clip=True)
        print("m1 done", i)
