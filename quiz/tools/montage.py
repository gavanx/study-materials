#!/usr/bin/env python3
"""把某一套卷子的裁切图拼成一张校对图，便于逐张检查有没有截断。

用法：
    python3 quiz/tools/montage.py wmo-26f5 [输出路径]
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
QUIZ = ROOT / "quiz"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sid = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(f"/tmp/montage-{sid}.png")

    data = json.loads((QUIZ / "data" / "questions.json").read_text(encoding="utf-8"))
    qs = [q for q in data["questions"] if q["setId"] == sid]
    if not qs:
        sys.exit(f"{sid} 没有题目")

    cols, cw, ch, pad = 4, 330, 420, 8
    rows = math.ceil(len(qs) / cols)
    sheet = Image.new("RGB", (cols * (cw + pad) + pad, rows * (ch + pad + 18) + pad), "white")
    dr = ImageDraw.Draw(sheet)
    for i, q in enumerate(qs):
        im = Image.open(QUIZ / q["img"]).convert("RGB")
        r = min(cw / im.width, ch / im.height)
        im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
        x = pad + (i % cols) * (cw + pad)
        y = pad + (i // cols) * (ch + pad + 18)
        dr.text((x, y), f"{q['no']} {q['kind']}", fill="black")
        sheet.paste(im, (x, y + 16))
    sheet.save(out)
    print(f"{len(qs)} 条 → {out}  {sheet.size}")


if __name__ == "__main__":
    main()
