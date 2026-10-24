#!/usr/bin/env python3
"""按 manifest 把整页试卷裁成单题图片，并汇总成 quiz/data/questions.json。

用法：
    python3 quiz/tools/crop.py                       # 处理 manifest 目录下所有卷子
    python3 quiz/tools/crop.py wmo-34f5              # 只处理指定卷子

manifest 约定见 quiz/tools/manifest/*.json：
    set   —— 卷子元信息（id/name/grade/source/answerSource/answerNote）
    pages —— [{file, items:[{id, no, kind, y:[y0,y1], answer, text, choices, explain, tags, stemId, needsReview}]}]
    y 为页面高度的归一化区间；横向范围由脚本按墨迹自动收紧。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parents[2]          # study-materials/
QUIZ = ROOT / "quiz"
MANIFEST_DIR = QUIZ / "tools" / "manifest"
IMG_DIR = QUIZ / "data" / "img"

MAX_WIDTH = 1400
WEBP_QUALITY = 85
INK_THRESHOLD = 110          # 低于此灰度视为墨迹；浅灰水印会被忽略
PAD_X_RATIO = 0.015
PAD_Y_RATIO = 0.004


def ink_columns(gray: np.ndarray, y0: int, y1: int, x_lo: int = 0, x_hi: int | None = None):
    """返回 [y0,y1) 行区间、[x_lo,x_hi) 列区间内墨迹的最小/最大列号。"""
    x_hi = gray.shape[1] if x_hi is None else x_hi
    band = gray[y0:y1, x_lo:x_hi]
    cols = (band < INK_THRESHOLD).any(axis=0)
    if not cols.any():
        return None
    xs = np.flatnonzero(cols)
    return int(xs[0]) + x_lo, int(xs[-1]) + x_lo


def crop_item(img: Image.Image, gray: np.ndarray, item: dict, out_path: Path):
    """item["y"] 必填；item["x"] 可选，用于横版双栏卷子限定所属栏。"""
    w, h = img.size
    y0 = max(0, int(item["y"][0] * h))
    y1 = min(h, int(item["y"][1] * h))
    if item.get("x"):
        col_lo, col_hi = int(item["x"][0] * w), int(item["x"][1] * w)
    else:
        col_lo, col_hi = 0, w
    span = ink_columns(gray, y0, y1, col_lo, col_hi) or (col_lo, col_hi - 1)
    x0 = max(col_lo, span[0] - int(PAD_X_RATIO * w))
    x1 = min(col_hi, span[1] + int(PAD_X_RATIO * w))
    py = int(PAD_Y_RATIO * h)
    y0 = max(0, y0 - py)
    y1 = min(h, y1 + py)

    piece = img.crop((x0, y0, x1, y1))
    if piece.width > MAX_WIDTH:
        ratio = MAX_WIDTH / piece.width
        piece = piece.resize((MAX_WIDTH, max(1, int(piece.height * ratio))), Image.LANCZOS)
    piece = piece.convert("RGB")
    # 扫描件普遍发灰，做一次对比度拉伸 + 轻锐化，字更清爽
    piece = ImageOps.autocontrast(piece, cutoff=1)
    piece = piece.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=3))
    piece.save(out_path, "WEBP", quality=WEBP_QUALITY, method=6)
    return [round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4)]


def crop_parts(parts: list, out_path: Path):
    """题目跨栏/跨页时，按 parts 依次裁出后竖向拼接。

    parts: [{"file": 相对路径, "y": [y0,y1], "x": [x0,x1]?}, ...]
    """
    pieces = []
    for part in parts:
        img = Image.open(ROOT / part["file"])
        gray = np.asarray(img.convert("L"))
        tmp = {"y": part["y"], "x": part.get("x")}
        scratch = out_path.with_suffix(".part.webp")
        crop_item(img, gray, tmp, scratch)
        pieces.append(Image.open(scratch).convert("RGB"))
        scratch.unlink(missing_ok=True)

    width = min(p.width for p in pieces)
    scaled = [
        p.resize((width, max(1, int(p.height * width / p.width))), Image.LANCZOS)
        for p in pieces
    ]
    gap = 6
    total_h = sum(p.height for p in scaled) + gap * (len(scaled) - 1)
    canvas = Image.new("RGB", (width, total_h), "white")
    y = 0
    for p in scaled:
        canvas.paste(p, (0, y))
        y += p.height + gap
    canvas.save(out_path, "WEBP", quality=WEBP_QUALITY, method=6)
    return canvas.size


def build_manifest(path: Path, sets: list, questions: list, sheets: list):
    data = json.loads(path.read_text(encoding="utf-8"))
    meta = data["set"]
    sets.append({k: v for k, v in meta.items()})

    for page in data["pages"]:
        src = ROOT / page["file"]
        if not src.exists():
            raise FileNotFoundError(src)
        img = Image.open(src)
        gray = np.asarray(img.convert("L"))
        for item in page["items"]:
            out = IMG_DIR / f"{item['id']}.webp"
            if item.get("parts"):
                crop_parts(item["parts"], out)
                bbox = item.get("x") or [0, 0, 0, 0]
            else:
                bbox = crop_item(img, gray, item, out)
            questions.append({
                "id": item["id"],
                "setId": meta["id"],
                "no": item["no"],
                "kind": item["kind"],
                "text": item.get("text", ""),
                "choices": item.get("choices"),
                "answer": item.get("answer"),
                "explain": item.get("explain", ""),
                "stemId": item.get("stemId"),
                "tags": item.get("tags", []),
                "board": item.get("board"),
                "topic": item.get("topic"),
                "img": f"data/img/{item['id']}.webp",
                "page": src.name,
                "bbox": bbox,
                "needsReview": bool(item.get("needsReview", False)),
            })
            sheets.append((meta, item, out))


def write_contact_sheet(sheets):
    rows = []
    for meta, item, out in sheets:
        rel = out.relative_to(QUIZ)
        rows.append(
            f'<section><h3>{meta["shortName"]} · {item["no"]} · {item["kind"]}'
            f'{"" if not item.get("needsReview") else " · 待核对"}</h3>'
            f'<img src="{rel}" loading="lazy"></section>'
        )
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>裁切校对</title>
<style>
body{{font-family:-apple-system,"PingFang SC",sans-serif;background:#f8fafc;margin:0;padding:20px}}
h1{{font-size:20px}}
section{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px;margin:0 0 14px}}
h3{{font-size:14px;color:#374151;margin:0 0 8px;font-weight:600}}
img{{max-width:100%;display:block;border:1px solid #f1f5f9}}
</style></head><body>
<h1>裁切校对（{len(rows)} 张）</h1>
{''.join(rows)}
</body></html>"""
    (QUIZ / "tools" / "contact-sheet.html").write_text(html, encoding="utf-8")


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    files = sorted(MANIFEST_DIR.glob("*.json"))
    if only:
        files = [f for f in files if f.stem == only]
    if not files:
        sys.exit("没有找到 manifest")

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    sets, questions, sheets = [], [], []
    for path in files:
        build_manifest(path, sets, questions, sheets)
        print(f"✓ {path.name}: {len(questions)} 题累计")

    payload = {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "sets": sets,
        "questions": questions,
    }
    out = QUIZ / "data" / "questions.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_contact_sheet(sheets)
    print(f"写出 {out.relative_to(ROOT)}：{len(sets)} 套 / {len(questions)} 条")


if __name__ == "__main__":
    main()
