#!/usr/bin/env python3
"""finals-prepper Phase 0: 递归扫描资料目录，按章节自动分组，产出 manifest.json。

用法: python scan.py <资料目录>
"""
import argparse
import json
import os
import re
from collections import OrderedDict

SUPPORTED = {".pptx", ".ppt", ".docx", ".doc", ".pdf",
             ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


def chapter_key_from_name(name: str):
    """从文件名推断章节号，推断不出返回 None。"""
    patterns = [
        r"第\s*(\d+)\s*[章讲节]",
        r"[Cc]hapter\s*(\d+)",
        r"[Cc]h[.\s_]*(\d+)",
        r"^(\d+)[_\-.\s、]",
    ]
    for p in patterns:
        m = re.search(p, name)
        if m:
            return int(m.group(1))
    return None


def scan(root: str) -> dict:
    root = os.path.abspath(root)
    groups = OrderedDict()   # 子目录名 -> {'label', 'files'}
    ungrouped = []           # 根目录直接放的文件

    for dirpath, dirnames, filenames in os.walk(root):
        # 跳过隐藏目录和中间产物目录
        dirnames[:] = sorted(
            d for d in dirnames
            if not d.startswith(".") and d != ".final_prep"
        )
        rel = os.path.relpath(dirpath, root)
        files = sorted(
            f for f in filenames
            if os.path.splitext(f)[1].lower() in SUPPORTED
        )
        if not files:
            continue

        if rel == ".":
            ungrouped.extend(os.path.join(dirpath, f) for f in files)
        else:
            chapter_dir = rel.split(os.sep)[0]
            g = groups.setdefault(chapter_dir, {"label": chapter_dir, "files": []})
            g["files"].extend(os.path.join(dirpath, f) for f in files)

    chapters = []
    idx = 1

    # 子目录优先：每个子目录 = 一章
    for g in groups.values():
        chapters.append({"id": f"ch{idx}", "label": g["label"], "files": g["files"]})
        idx += 1

    # 根目录散文件：按文件名章节号归组，无编号的归入末尾单章
    if ungrouped:
        bynum = OrderedDict()
        for f in ungrouped:
            n = chapter_key_from_name(os.path.basename(f))
            k = n if n is not None else 0
            bynum.setdefault(k, []).append(f)
        for k in sorted(bynum.keys(), key=lambda x: (x == 0, x)):
            label = None if k == 0 else f"第{k}章"
            chapters.append({"id": f"ch{idx}", "label": label, "files": bynum[k]})
            idx += 1

    return {
        "course": os.path.basename(root) or "课程",
        "root": root,
        "chapters": chapters,
    }


def main():
    ap = argparse.ArgumentParser(description="扫描资料目录并做章节分组")
    ap.add_argument("root", help="资料目录")
    args = ap.parse_args()

    manifest = scan(args.root)
    outdir = os.path.join(manifest["root"], ".final_prep")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "manifest.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"扫描完成：共 {len(manifest['chapters'])} 章")
    for c in manifest["chapters"]:
        label = c["label"] or "(待 AI 命名)"
        print(f"  {c['id']}  {label}: {len(c['files'])} 个文件")
    print(f"manifest -> {out}")


if __name__ == "__main__":
    main()
