#!/usr/bin/env python3
"""
Parse 禁用词清单.md and generate banned_words.json
"""
import re
import json
from pathlib import Path

MD_PATH = Path("D:/Desktop/黑客松/数据集/禁用词清单.md")
OUT_PATH = Path("D:/Desktop/黑客松/pipeline/data/禁用词/banned_words.json")

# ── Section → (category, regulation_ref) mapping ──────────────────────────
SECTION_META = {
    "一": ("极限用语", "广告法第九条第(三)项"),
    "二": ("虚假宣传", "广告法第四条/第二十八条"),
    "三": ("对比贬低", "广告法第十一条/第十三条"),
    "四": ("资质虚构", "广告法第十一条"),
    "五": ("诱导焦虑", "广告法第四条/第二十八条"),
    "六": ("行业禁区", "广告法第十七条/第十八条"),
    "七": ("极限用语", "广告法第九条第(三)项"),   # 第七章"其他高频违规词"归入极限用语
}

# ── Regex pattern builder ─────────────────────────────────────────────────
def build_pattern(word: str) -> str:
    """
    Build a regex pattern that supports common word-form variations.

    Rules:
    - A standalone "最" becomes a prefix pattern  最.{0,4}  to match
      最好/最佳/最强 etc. (up to 4 extra chars)
    - Words already containing "最" (e.g. "最好") use literal match
    - XX placeholders → .{1,8} wildcard
    - Phrases with parenthetical conditions → strip the condition,
      match the core phrase
    - Otherwise → re.escape(literal)
    """
    w = word.strip()

    # Strip parenthetical qualifiers like "(非真实时)" — they are editorial
    # comments, not part of the matched string
    w = re.sub(r'（[^）]*）', '', w).strip()
    w = re.sub(r'\([^)]*\)', '', w).strip()

    if not w:
        return ""

    # XX → wildcard (e.g. "一次瘦XX斤" → "一次瘦.{1,8}斤")
    if "XX" in w:
        pat = re.escape(w).replace(r"XX", ".{1,8}")
        return pat

    # Single-char "最" → prefix pattern
    if w == "最":
        return "最.{0,4}"

    # Generic literal
    return re.escape(w)


# ── Parse markdown ────────────────────────────────────────────────────────
def parse_md(text: str) -> list[dict]:
    entries: list[dict] = []
    current_section = None   # "一", "二", ...
    in_code_block = False

    for line in text.splitlines():
        stripped = line.strip()

        # Detect major section header: "## 一、..."  "## 二、..."
        m_sec = re.match(r'^##\s+[一二三四五六七]、(.+)', stripped)
        if m_sec:
            current_section = stripped[m_sec.start(0)+3 : m_sec.start(0)+4]
            in_code_block = False
            continue

        # Track code fences
        if stripped == "```":
            in_code_block = not in_code_block
            continue

        # Skip non-code lines
        if not in_code_block or not stripped:
            continue

        if current_section is None:
            continue

        cat, reg = SECTION_META.get(current_section, ("极限用语", "广告法第九条第(三)项"))

        # Split comma-separated or newline-separated words
        # The md uses 、as well as ，and plain commas
        words = re.split(r'[、，,]+', stripped)
        for w in words:
            w = w.strip()
            if not w or len(w) < 2:
                continue
            # Strip trailing editorial meta-text that got attached to
            # the last item in a comma list, e.g.
            # "减害的用语均禁止" → "减害"
            w = re.sub(r'的用语.*$', '', w).strip()
            if not w or len(w) < 2:
                continue

            pattern = build_pattern(w)
            if not pattern:
                continue

            entries.append({
                "word": w,
                "category": cat,
                "regulation_ref": reg,
                "pattern": pattern,
            })

    return entries


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    text = MD_PATH.read_text(encoding="utf-8")
    entries = parse_md(text)

    # De-duplicate by (word, category)
    seen = set()
    unique = []
    for e in entries:
        key = (e["word"], e["category"])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    # Write JSON
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(unique, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Written {len(unique)} entries to {OUT_PATH}")

    # Quick validation
    data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    print(f"Validation: {len(data)} words loaded")
    print(json.dumps(data[0], ensure_ascii=False))
    print(f"\nCategory distribution:")
    from collections import Counter
    cats = Counter(e["category"] for e in data)
    for c, n in cats.most_common():
        print(f"  {c}: {n}")


if __name__ == "__main__":
    main()
