#!/usr/bin/env python3
"""打印页面里的墨迹块位置，供写 manifest 时确定每道题的 y 区间。

用法：
    python3 quiz/tools/scan_blocks.py 'wmo/五年级/第26届-复赛/试卷-1.jpg' ...

输出每页的块区间（归一化），块之间的空白就是题目分隔处。
注意：合并阈值 1.2% 页高以内的相邻行会并成一块，写 manifest 时按题目边界取舍。
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def blocks(path: Path):
    img = Image.open(path).convert("L")
    w, h = img.size
    a = np.asarray(img)
    ink = (a < 110).sum(axis=1) > max(8, int(w * 0.004))
    segs, start = [], None
    for i, v in enumerate(ink):
        if v and start is None:
            start = i
        elif not v and start is not None:
            segs.append((start, i - 1)); start = None
    if start is not None:
        segs.append((start, h - 1))
    merged = []
    for s, e in segs:
        if merged and s - merged[-1][1] < h * 0.012:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    print(f"== {path}  {w}x{h}")
    for s, e in merged:
        band = a[s:e + 1]
        cols = np.flatnonzero((band < 110).any(axis=0))
        x0, x1 = (cols[0], cols[-1]) if len(cols) else (0, w - 1)
        print(f"   y {s / h:.3f}-{e / h:.3f}   x {x0 / w:.3f}-{x1 / w:.3f}   h={(e - s) / h:.3f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        blocks(Path(p))
