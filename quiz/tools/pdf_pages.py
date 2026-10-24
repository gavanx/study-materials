#!/usr/bin/env python3
"""把 PDF 每页渲染成 PNG，便于直接看图（答案册多是 PDF）。

用法：
    python3 quiz/tools/pdf_pages.py <input.pdf> <outdir> [dpi]
"""
import sys
from pathlib import Path

import pymupdf


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 150
    outdir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(src)
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(dpi=dpi)
        out = outdir / f"{src.stem}-p{i}.png"
        pix.save(out)
        print(out)


if __name__ == "__main__":
    main()
