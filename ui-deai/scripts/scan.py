#!/usr/bin/env python3
"""客观扫描前端文件中的 AI 味信号，用真实正则匹配代替"读一遍凭印象判断"。
用法：python3 scan.py <文件或目录> [<文件或目录> ...]
退出码：命中数为 0 时返回 0，否则返回 1（可用于强制流程判断是否通过）。
"""
import argparse
import json
import os
import re
import sys

EXTS = {".html", ".htm", ".vue", ".tsx", ".jsx", ".svelte", ".css", ".scss", ".less"}

EMOJI_PATTERN = (
    r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    r"\U00002190-\U000021FF\U00002B00-\U00002BFF]"
)

CATEGORIES = {
    "布局套路化": [
        r"grid-cols-3", r"grid-cols-4",
        r"10,000\+", r"99\.9%", r"500\+\s*企业", r"12,345",
        r"\d+K\+?\s*Users", r"\bUptime\b",
    ],
    "配色 AI 感": [
        r"#667eea", r"#764ba2", r"linear-gradient", r"bg-gradient-to-",
        r"bg-clip-text", r"text-transparent",
        r"bg-(black|gray-9\d\d|slate-9\d\d|zinc-9\d\d|neutral-9\d\d)\b",
        r"background(-color)?\s*:\s*#[01][0-9a-f]{5}\b",
        r"background(-color)?\s*:\s*#[0-2][0-9a-f]{2}\b(?![0-9a-f])",
    ],
    "视觉效果堆砌": [
        r"border-radius\s*:\s*1[2-9]px", r"border-radius\s*:\s*2\dpx",
        r"rounded-xl", r"rounded-2xl", r"rounded-3xl",
        r"box-shadow", r"shadow-lg", r"shadow-xl",
        r"backdrop-blur", r"blur-3xl", r"filter\s*:\s*blur",
        r"radial-gradient",
    ],
    "装饰元素通用化": [
        EMOJI_PATTERN,
        r"lucide-react", r"heroicons",
        r">\s*(New!?|Popular|Hot)\s*<",
    ],
    "交互动效套路化": [
        r"hover:scale-", r"hover:-translate-y-", r"transition-all duration-300",
    ],
    "内部内容泄露": [
        r"<!--", r"TODO", r"FIXME", r"请输入", r"在此输入", r"console\.log",
    ],
    "文案 AI 腔": [
        r"为您提供", r"一站式", r"赋能", r"沉浸式", r"立即开始体验",
        r"高效协作", r"智能驱动", r"流畅体验", r"全新升级", r"极致体验",
        r"实时互动平台", r"强大功能",
        r"\bSeamless\b", r"\bPowerful\b", r"\bEffortless\b", r"\bUnlock\b",
        r"Next-generation", r"\bStreamlined\b", r"\bIntelligent\b",
        r"Boost productivity", r"Modern solution", r"Real-time collaboration",
        r"Get Started", r"Learn More", r"Try for Free",
    ],
    "缺乏真实产品感": [
        r"John Doe", r"Jane Doe", r"Lorem ipsum",
        r"\$29\s*/\s*mo",
    ],
}

NOTE = "排版机械化：无法用正则可靠检测（字号步进/标题套路属于语义判断），需人工对照 SKILL.md「快速识别信号」表核查。"


def collect_files(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                for name in names:
                    if os.path.splitext(name)[1].lower() in EXTS:
                        files.append(os.path.join(root, name))
        elif os.path.isfile(p):
            files.append(p)
    return files


def scan_file(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = f.read().splitlines()
    except OSError as e:
        return {"error": str(e)}
    hits = {}
    for cat, patterns in CATEGORIES.items():
        cat_hits = []
        for pat in patterns:
            regex = re.compile(pat, re.IGNORECASE)
            for i, line in enumerate(lines, 1):
                if regex.search(line):
                    cat_hits.append({"pattern": pat, "line": i, "text": line.strip()[:120]})
        if cat_hits:
            hits[cat] = cat_hits
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="要扫描的文件或目录")
    args = ap.parse_args()

    files = collect_files(args.paths)
    findings = {}
    total_hits = 0
    for f in files:
        h = scan_file(f)
        if h:
            findings[f] = h
            total_hits += sum(len(v) for v in h.values())

    result = {
        "files_scanned": len(files),
        "total_hits": total_hits,
        "findings": findings,
        "note": NOTE,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(1 if total_hits > 0 else 0)


if __name__ == "__main__":
    main()