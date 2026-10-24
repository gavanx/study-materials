#!/usr/bin/env python3
"""批量校验 manifest：id 唯一、答案齐全、选项包含答案、页图存在、y 区间合法。

用法：
    python3 quiz/tools/validate.py            # 校验全部
    python3 quiz/tools/validate.py wmo-26f5   # 只校验一套
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = ROOT / "quiz" / "tools" / "manifest"


def check(path: Path):
    errs, warns = [], []
    data = json.loads(path.read_text(encoding="utf-8"))
    meta = data.get("set", {})
    sid = meta.get("id")
    if not sid:
        errs.append("set.id 缺失")
    for key in ("name", "shortName"):
        if not meta.get(key):
            errs.append(f"set.{key} 缺失")
    if not data.get("pages"):
        errs.append("pages 为空")

    ids, stems = set(), set()
    total = 0
    for page in data.get("pages", []):
        src = ROOT / page.get("file", "")
        if not src.exists():
            errs.append(f"页图不存在：{page.get('file')}")
        for item in page.get("items", []):
            total += 1
            iid = item.get("id", "")
            if not iid:
                errs.append(f"{page.get('file')} 有条目缺 id"); continue
            if iid in ids:
                errs.append(f"id 重复：{iid}")
            ids.add(iid)
            y = item.get("y") or []
            if len(y) != 2 or not (0 <= y[0] < y[1] <= 1):
                errs.append(f"{iid}: y 非法 {y}")
            elif y[1] - y[0] < 0.004:
                warns.append(f"{iid}: y 区间过窄 {y}")
            kind = item.get("kind")
            if kind not in ("choice", "fill", "stem"):
                errs.append(f"{iid}: kind 非法 {kind}")
            if kind == "stem":
                stems.add(iid)
            if kind == "choice":
                ch = item.get("choices") or {}
                if sorted(ch) != ["A", "B", "C", "D"]:
                    warns.append(f"{iid}: 选项不是 ABCD {sorted(ch)}")
                if item.get("answer") not in ch:
                    errs.append(f"{iid}: answer={item.get('answer')} 不在选项里")
            if kind == "fill" and not item.get("answer"):
                errs.append(f"{iid}: 填空题缺 answer")
            if item.get("stemId") and item["stemId"] not in stems:
                # stem 可能定义在后面，最后统一复查
                pass
            if not item.get("text"):
                warns.append(f"{iid}: 缺 text")
            if not item.get("tags"):
                warns.append(f"{iid}: 缺 tags")

    for page in data.get("pages", []):
        for item in page.get("items", []):
            sidref = item.get("stemId")
            if sidref and sidref not in stems:
                errs.append(f"{item.get('id')}: stemId 指向不存在的 {sidref}")

    return total, errs, warns


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    files = sorted(MANIFEST_DIR.glob("*.json"))
    if only:
        files = [f for f in files if f.stem == only]
    grand, bad = 0, 0
    for f in files:
        total, errs, warns = check(f)
        grand += total
        status = "✓" if not errs else "✗"
        print(f"{status} {f.stem:12s} {total:3d} 条")
        for e in errs:
            print(f"    ERROR {e}")
        for w in warns[:6]:
            print(f"    warn  {w}")
        if len(warns) > 6:
            print(f"    warn  …另有 {len(warns) - 6} 条")
        bad += len(errs)
    print(f"\n合计 {len(files)} 套 / {grand} 条，错误 {bad} 个")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
