#!/usr/bin/env python3
"""用 macOS Vision OCR 质检裁图：有没有把答案/解析裁进去，题号有没有被切掉。

用法：
    python3 quiz/tools/qa_crops.py            # 检查全部
    python3 quiz/tools/qa_crops.py wmo-18b5   # 只检查一套

依赖 macOS 自带 Vision（pyobjc），无需装 tesseract。
"""
import json
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import Quartz
import Vision
from Foundation import NSURL
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
QUIZ = ROOT / "quiz"

# 预先在主线程取一次符号，避免多线程下 pyobjc 懒加载竞态
_SRC_CREATE_WITH_URL = Quartz.CGImageSourceCreateWithURL
_SRC_CREATE_IMAGE_AT = Quartz.CGImageSourceCreateImageAtIndex

LEAK_WORDS = ("【答案】", "答案】", "【解析】", "考查能力", "考查知识点")
NOISE = re.compile(r"公众号|微信扫一扫|领取试卷答案|扫码")


def ocr_text(path: Path) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
        Image.open(path).convert("RGB").save(tmp.name)
        url = NSURL.fileURLWithPath_(tmp.name)
        src = _SRC_CREATE_WITH_URL(url, None)
        if src is None:
            return ""
        img = _SRC_CREATE_IMAGE_AT(src, 0, None)
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(0)                      # accurate
        req.setRecognitionLanguages_(["zh-Hans", "en-US"])
        req.setUsesLanguageCorrection_(False)
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
        ok, err = handler.performRequests_error_([req], None)
        if not ok:
            return ""
        out = []
        for obs in req.results():
            cand = obs.topCandidates_(1)
            if cand and len(cand) > 0:
                out.append(str(cand[0].string()))
        return "\n".join(out)


def normalize(s: str) -> str:
    return re.sub(r"\s+", "", s)


def check_one(q):
    path = QUIZ / q["img"]
    text = ocr_text(path)
    flat = normalize(text)
    problems = []

    if any(w in flat for w in LEAK_WORDS):
        problems.append("疑似裁进了答案/解析")
    if len(flat) < 20:
        problems.append("识别不出文字")

    no = q["no"]
    m = re.match(r"^(\d+)(?:-(\d+))?$", no)
    if m:
        head = flat[:40]
        main_no, sub_no = m.group(1), m.group(2)
        if sub_no:
            # 小问在卷面上通常只印「（1）」；两种写法都算命中
            ok = re.search(rf"{main_no}\D{{0,3}}{sub_no}", head) or \
                 re.search(rf"[（(]\s*{sub_no}\s*[）)]", head)
        else:
            ok = re.search(rf"(?<!\d){main_no}\s*[.．、]", head)
        if not ok:
            problems.append("题号可能被切掉")

    return q["id"], problems, flat[:60]


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    data = json.loads((QUIZ / "data" / "questions.json").read_text(encoding="utf-8"))
    qs = [q for q in data["questions"] if not only or q["setId"] == only]
    print(f"质检 {len(qs)} 张…")
    bad = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for iid, problems, head in ex.map(check_one, qs):
            if problems:
                bad += 1
                print(f"✗ {iid:20s} {' / '.join(problems)}   «{head}»")
    print(f"\n完成：{len(qs)} 张，异常 {bad} 张")


if __name__ == "__main__":
    main()
