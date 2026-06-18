"""
广告合规审核 Pipeline — 数据解析器

5 个解析函数，分别处理 5 类数据文件。
统一输出格式: list[dict]，每个 dict 含 key / value / source / tags 四个字段。
"""

import json
import re
from pathlib import Path


# ============================================================
# 工具函数
# ============================================================

def strip_page_markers(text: str) -> str:
    """去除 PDF 转换遗留的页码标记和分隔线。"""
    # 去除 <!-- 第 N 页 --> 标记
    text = re.sub(r"<!--\s*第\s*\d+\s*页\s*-->", "", text)
    # 去除孤立的纯数字行 (页码残留)
    text = re.sub(r"^\d+\s*$", "", text, flags=re.MULTILINE)
    # 去除分隔线 (---)
    text = re.sub(r"^---\s*$", "", text, flags=re.MULTILINE)
    # 去除连续空行，保留最多 1 个
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 去除行首空白行
    text = re.sub(r"^\s+$", "", text, flags=re.MULTILINE)
    return text.strip()


def _read_file(path) -> str:
    """读取文件，返回原始文本。"""
    p = Path(path) if not isinstance(path, Path) else path
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def _extract_chapter_for_article(article_num: str) -> str:
    """根据条文号确定所属章。"""
    chapter_ranges = {
        "总则": (1, 7),
        "广告内容准则": (8, 28),
        "广告行为规范": (29, 45),
        "监督管理": (46, 53),
        "法律责任": (54, 73),
        "附则": (74, 75),
    }
    num_match = re.search(r"\d+", article_num)
    if not num_match:
        return ""
    num = int(num_match.group())
    for chapter, (lo, hi) in chapter_ranges.items():
        if lo <= num <= hi:
            return chapter
    return ""


def _extract_law_tags(text: str) -> list[str]:
    """从法规文本中提取关键词标签。"""
    tag_map = {
        "极限用语": ["最高级", "最佳", "国家级", "最便宜", "销量第一"],
        "虚假广告": ["虚假", "引人误解", "欺骗"],
        "医疗广告": ["医疗", "药品", "医疗器械", "医疗机构"],
        "保健食品": ["保健食品", "保健"],
        "烟草广告": ["烟草"],
        "未成年人": ["未成年"],
        "代言": ["代言", "推荐", "证明"],
        "专利": ["专利"],
        "竞争": ["贬低", "竞争"],
        "处罚": ["罚款", "处罚", "法律责任"],
    }
    tags = []
    for tag, keywords in tag_map.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)
    return tags


# ============================================================
# 1. parse_law_articles — 广告法释义
# ============================================================

def parse_law_articles(md_path) -> list[dict]:
    """
    解析《广告法》释义.md，按"第X条"切分。

    每条包含：key, value(条文原文+释义), source="ad_law", tags
    处理【释义】标记，分离法条原文和释义。
    """
    raw = _read_file(md_path)
    text = strip_page_markers(raw)

    article_pattern = re.compile(
        r"(第.{1,3}条)\s*(.*?)(?=\n第.{1,3}条\s|\Z)",
        re.DOTALL,
    )

    results = []
    for m in article_pattern.finditer(text):
        article_num = m.group(1).strip()
        content = m.group(2).strip()

        # 只处理有释义标记的内容（释义部分，非纯法条正文）
        if "【释义】" not in content and len(content) < 200:
            continue

        # 分离法条原文与释义
        parts = content.split("【释义】", 1)
        article_text = parts[0].strip()
        interpretation = parts[1].strip() if len(parts) > 1 else ""

        # 合并为完整 value
        value = f"{article_num}\n{article_text}"
        if interpretation:
            value += f"\n\n【释义】{interpretation}"

        if len(value) < 50:
            continue

        chapter = _extract_chapter_for_article(article_num)
        extra_tags = _extract_law_tags(value)
        tags_list = ["广告法", article_num, chapter] + extra_tags
        tags = ",".join(t for t in tags_list if t)

        results.append({
            "key": f"ad_law:{article_num}",
            "value": value,
            "source": "ad_law",
            "tags": tags,
        })

    return results


# ============================================================
# 2. parse_penalty_cases — 处罚案例库
# ============================================================

def parse_penalty_cases(md_path) -> list[dict]:
    """
    解析处罚案例库.md，按"### 案例 N"切分。

    每条包含：key, value(完整案例文本), source="penalty_case", tags(行业+违规类型)
    """
    raw = _read_file(md_path)
    text = strip_page_markers(raw)

    case_pattern = re.compile(
        r"(###\s*案例\s*(\d+))\s*\n(.*?)(?=###\s*案例\s*\d+|\Z)",
        re.DOTALL,
    )

    results = []
    for m in case_pattern.finditer(text):
        case_header = m.group(1).strip()
        case_num = m.group(2).strip()
        case_body = m.group(3).strip()

        value = f"{case_header}\n{case_body}"

        # 提取行业和违规类型
        industry_match = re.search(r"\*\*行业\*\*[：:]\s*(.+)", case_body)
        violation_match = re.search(r"\*\*违规类型\*\*[：:]\s*(.+)", case_body)

        tags_list = ["处罚案例"]
        if industry_match:
            tags_list.append(industry_match.group(1).strip())
        if violation_match:
            tags_list.append(violation_match.group(1).strip())
        tags = ",".join(tags_list)

        results.append({
            "key": f"penalty_case:{case_num}",
            "value": value,
            "source": "penalty_case",
            "tags": tags,
        })

    return results


# ============================================================
# 3. parse_industry_rules — 行业广告禁区规则
# ============================================================

def parse_industry_rules(md_path) -> list[dict]:
    """
    解析行业广告禁区规则.md，按"## X、XX行业"切分。

    每条包含：key, value(规则文本), source="industry_rule", tags(行业)
    """
    raw = _read_file(md_path)
    text = strip_page_markers(raw)

    industry_pattern = re.compile(
        r"(##\s*[一二三四五六七八九十]+[、.]\s*(.+?)\s*\n)"
        r"(.*?)(?=\n##\s*[一二三四五六七八九十]+[、.]|\Z)",
        re.DOTALL,
    )

    results = []
    for m in industry_pattern.finditer(text):
        industry_name = m.group(2).strip()
        industry_body = m.group(3).strip()

        # 行业名转英文 key
        key_part = _industry_name_to_key(industry_name)

        value = f"行业: {industry_name}\n\n{industry_body}"

        tags_list = ["行业规则", industry_name]
        tags = ",".join(tags_list)

        results.append({
            "key": f"industry_rule:{key_part}",
            "value": value,
            "source": "industry_rule",
            "tags": tags,
        })

    return results


def _industry_name_to_key(name: str) -> str:
    """行业名转 key 标识。"""
    mapping = {
        "医疗器械": "medical_device",
        "医疗": "medical",
        "药品": "pharma",
        "保健食品": "health_food",
        "食品": "food",
        "化妆品": "cosmetic",
        "教育培训": "education",
        "教育": "education",
        "金融投资": "finance",
        "金融": "finance",
        "房地产": "real_estate",
        "烟草": "tobacco",
        "酒类": "alcohol",
    }
    for cn, en in mapping.items():
        if cn in name:
            return en
    return re.sub(r"[^\w]", "_", name).lower()


# ============================================================
# 4. parse_banned_words — 禁用词清单 (JSON)
# ============================================================

def parse_banned_words(json_path) -> list[dict]:
    """
    解析 banned_words.json。

    不入库 vmem（禁用词匹配是独立的规则引擎）。
    返回结构化列表供 BannedWordMatcher 使用。
    """
    p = Path(json_path) if not isinstance(json_path, Path) else json_path
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []
    for entry in data:
        word = entry.get("word", "")
        category = entry.get("category", "")
        regulation_ref = entry.get("regulation_ref", "")
        pattern = entry.get("pattern", word)

        results.append({
            "key": f"banned:{word}",
            "value": word,
            "source": "banned_word",
            "tags": category,
            # 额外字段供 BannedWordMatcher 使用
            "pattern": pattern,
            "regulation_ref": regulation_ref,
        })

    return results


# ============================================================
# 5. parse_replacement_map — 禁用词替代映射表
# ============================================================

def parse_replacement_map(md_path) -> list[dict]:
    """
    解析禁用词替代映射表.md，按表格行切分。

    每条包含：key, value(禁用词+替代词+说明), source="replacement", tags
    """
    raw = _read_file(md_path)
    text = strip_page_markers(raw)

    sections = re.split(r"\n(?=## )", text)

    results = []
    for section in sections:
        section = section.strip()
        if not section.startswith("##"):
            continue

        title_match = re.match(r"##\s*[一二三四五六七八九十]+[、.]\s*(.+)", section)
        if not title_match:
            continue
        category = title_match.group(1).strip()

        # 解析表格行: | 禁用词 | 替代词 | 说明 |
        rows = re.findall(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", section)

        for row in rows:
            banned = row[0].strip()
            replacement = row[1].strip()
            note = row[2].strip()

            # 跳过表头和分隔行
            if banned in ("禁用词", "---") or "---" in banned:
                continue
            if not banned or not replacement:
                continue

            value = f"禁用词: {banned} → 替代词: {replacement}"
            if note:
                value += f" | 说明: {note}"

            tags = ",".join(["替代映射", category, banned])

            results.append({
                "key": f"replacement:{banned}",
                "value": value,
                "source": "replacement",
                "tags": tags,
            })

    return results


# ============================================================
# 队友版数据解析函数
# ============================================================

# ── 队友版文件路径（硬编码，与 config.py 中的数据集目录一致）──

def _teammate_data_dir() -> Path:
    """返回数据集目录路径。"""
    return Path(__file__).resolve().parent.parent / "数据集"


TEAMMATE_FILES = {
    "ad_law":           _teammate_data_dir() / "广告法全文_队友版.md",
    "banned_words":     _teammate_data_dir() / "禁用词清单_队友版.md",
    "replacement":      _teammate_data_dir() / "禁用词替代映射表_队友版.md",
    "penalty_cases":    _teammate_data_dir() / "处罚案例_队友版.md",
    "industry_rules":   _teammate_data_dir() / "行业禁区规则_队友版.md",
}

PARSED_OUTPUT_DIR = Path(__file__).resolve().parent / "data" / "parsed"


def _parse_md_table_rows(text: str, expected_cols: int = 0) -> list[list[str]]:
    """
    通用 Markdown 表格行解析。
    自动跳过表头行和分隔行（含 ---），返回每行的列值列表。
    expected_cols: 如果 > 0，只返回恰好有这么多列的行。
    """
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        # 跳过分隔行
        if re.match(r"^\|[\s\-|:]+\|$", line):
            continue
        cells = [c.strip() for c in line.split("|")]
        # split("|") 会产生首尾空元素
        cells = [c for c in cells if c != ""]
        # 跳过表头行（第一个非空 cell 为 "序号" 或 "# " 开头）
        if cells and cells[0] == "序号":
            continue
        if expected_cols > 0 and len(cells) != expected_cols:
            continue
        if cells:
            rows.append(cells)
    return rows


# ── 6. parse_law_articles_teammate — 广告法全文（队友版）──

def parse_law_articles_teammate(md_path=None) -> list[dict]:
    """
    解析广告法全文_队友版.md。
    格式: **第X条** 后跟条文内容，无释义。
    按 **第X条** 模式切分。
    """
    path = md_path or TEAMMATE_FILES["ad_law"]
    raw = _read_file(path)
    text = strip_page_markers(raw)

    # 匹配 **第X条** 开头的段落
    article_pattern = re.compile(
        r"\*\*(第.{1,3}条)\*\*\s*(.*?)(?=\n\*\*第.{1,3}条\*\*|\n## |\Z)",
        re.DOTALL,
    )

    results = []
    for m in article_pattern.finditer(text):
        article_num = m.group(1).strip()
        content = m.group(2).strip()

        if len(content) < 10:
            continue

        value = f"{article_num}\n{content}"
        chapter = _extract_chapter_for_article(article_num)
        extra_tags = _extract_law_tags(value)
        tags_list = ["广告法", article_num, chapter] + extra_tags
        tags = ",".join(t for t in tags_list if t)

        results.append({
            "key": f"ad_law_team:{article_num}",
            "value": value,
            "source": "ad_law_team",
            "tags": tags,
        })

    return results


# ── 7. parse_banned_words_teammate — 禁用词清单（队友版表格）──

def parse_banned_words_teammate(md_path=None) -> list[dict]:
    """
    解析禁用词清单_队友版.md。
    格式: | 序号 | 禁用词 | 类别 | 替代建议 |
    """
    path = md_path or TEAMMATE_FILES["banned_words"]
    raw = _read_file(path)
    text = strip_page_markers(raw)

    # 提取当前 section 的类别标题
    sections = re.split(r"\n(?=## )", text)

    results = []
    current_category = ""

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # 提取 section 标题中的类别
        title_match = re.match(r"##\s*[一二三四五六七八九十]+[、.]\s*(.+)", section)
        if title_match:
            current_category = title_match.group(1).strip()
            # 去掉 "— 30+" 这样的数量后缀
            current_category = re.sub(r"\s*[—\-—]\s*\d+\+?\s*$", "", current_category)

        rows = _parse_md_table_rows(section, expected_cols=4)
        for cells in rows:
            seq, word, category, replacement = cells[0], cells[1], cells[2], cells[3]
            if not word:
                continue

            tags_list = ["禁用词", "队友版"]
            if category:
                tags_list.append(category)
            if current_category:
                tags_list.append(current_category)
            tags = ",".join(tags_list)

            value = f"禁用词: {word} | 类别: {category} | 替代建议: {replacement}"

            results.append({
                "key": f"banned_team:{word}",
                "value": value,
                "source": "banned_word_team",
                "tags": tags,
                "word": word,
                "category": category,
                "replacement_suggestion": replacement,
            })

    return results


# ── 8. parse_replacement_map_teammate — 禁用词替代映射表（队友版）──

def parse_replacement_map_teammate(md_path=None) -> list[dict]:
    """
    解析禁用词替代映射表_队友版.md。
    格式: | 序号 | 禁用词 | 替代词 | 使用场景 |
    """
    path = md_path or TEAMMATE_FILES["replacement"]
    raw = _read_file(path)
    text = strip_page_markers(raw)

    sections = re.split(r"\n(?=## )", text)

    results = []
    current_category = ""

    for section in sections:
        section = section.strip()
        if not section:
            continue

        title_match = re.match(r"##\s*[一二三四五六七八九十]+[、.]\s*(.+)", section)
        if title_match:
            current_category = title_match.group(1).strip()
            current_category = re.sub(r"\s*[—\-—]\s*\d+\+?\s*$", "", current_category)

        rows = _parse_md_table_rows(section, expected_cols=4)
        for cells in rows:
            seq, banned, replacement, usage = cells[0], cells[1], cells[2], cells[3]
            if not banned or not replacement:
                continue

            value = f"禁用词: {banned} → 替代词: {replacement}"
            if usage:
                value += f" | 使用场景: {usage}"

            tags_list = ["替代映射", "队友版"]
            if current_category:
                tags_list.append(current_category)
            tags = ",".join(tags_list)

            results.append({
                "key": f"replacement_team:{banned}",
                "value": value,
                "source": "replacement_team",
                "tags": tags,
            })

    return results


# ── 9. parse_penalty_cases_teammate — 处罚案例（队友版表格）──

def parse_penalty_cases_teammate(md_path=None) -> list[dict]:
    """
    解析处罚案例_队友版.md。
    格式: | 序号 | 案例 | 违法内容 | 处罚金额 | 处罚机关 |
    """
    path = md_path or TEAMMATE_FILES["penalty_cases"]
    raw = _read_file(path)
    text = strip_page_markers(raw)

    sections = re.split(r"\n(?=## )", text)

    results = []
    current_industry = ""

    for section in sections:
        section = section.strip()
        if not section:
            continue

        title_match = re.match(r"##\s*[一二三四五六七八九十]+[、.]\s*(.+)", section)
        if title_match:
            current_industry = title_match.group(1).strip()
            current_industry = re.sub(r"\s*[—\-—]\s*\d+\+?\s*$", "", current_industry)

        rows = _parse_md_table_rows(section, expected_cols=5)
        for cells in rows:
            seq, company, violation, penalty, authority = (
                cells[0], cells[1], cells[2], cells[3], cells[4]
            )
            if not company:
                continue

            value = (
                f"案例: {company}\n"
                f"违法内容: {violation}\n"
                f"处罚金额: {penalty}\n"
                f"处罚机关: {authority}"
            )

            tags_list = ["处罚案例", "队友版"]
            if current_industry:
                tags_list.append(current_industry)
            tags = ",".join(tags_list)

            results.append({
                "key": f"penalty_case_team:{seq}",
                "value": value,
                "source": "penalty_case_team",
                "tags": tags,
                "company": company,
                "penalty_amount": penalty,
                "authority": authority,
            })

    return results


# ── 10. parse_industry_rules_teammate — 行业禁区规则（队友版）──

def parse_industry_rules_teammate(md_path=None) -> list[dict]:
    """
    解析行业禁区规则_队友版.md。
    格式: ## 一、XX行业 + 子段落（核心禁令、常见违规点等）。
    """
    path = md_path or TEAMMATE_FILES["industry_rules"]
    raw = _read_file(path)
    text = strip_page_markers(raw)

    # 复用已有正则，能匹配 ## 一、XX行业 格式
    industry_pattern = re.compile(
        r"(##\s*[一二三四五六七八九十]+[、.]\s*(.+?)\s*\n)"
        r"(.*?)(?=\n##\s*[一二三四五六七八九十]+[、.]|\Z)",
        re.DOTALL,
    )

    # 追加匹配 "## 通用禁令" 这类非数字编号的 section
    general_pattern = re.compile(
        r"(##\s*(通用禁令.*?)\s*\n)"
        r"(.*?)(?=\n## |\Z)",
        re.DOTALL,
    )

    results = []

    for m in industry_pattern.finditer(text):
        industry_name = m.group(2).strip()
        industry_body = m.group(3).strip()

        key_part = _industry_name_to_key(industry_name)
        value = f"行业: {industry_name}\n\n{industry_body}"

        tags_list = ["行业规则", "队友版", industry_name]
        tags = ",".join(tags_list)

        results.append({
            "key": f"industry_rule_team:{key_part}",
            "value": value,
            "source": "industry_rule_team",
            "tags": tags,
        })

    for m in general_pattern.finditer(text):
        section_name = m.group(2).strip()
        section_body = m.group(3).strip()

        value = f"{section_name}\n\n{section_body}"
        tags = "行业规则,队友版,通用禁令"

        results.append({
            "key": "industry_rule_team:general",
            "value": value,
            "source": "industry_rule_team",
            "tags": tags,
        })

    return results


# ============================================================
# 验证入口
# ============================================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import (
        AD_LAW_FILE, PENALTY_CASES_FILE, INDUSTRY_RULES_FILE,
        BANNED_WORDS_JSON_FILE, WORD_REPLACEMENT_FILE,
    )

    print("=" * 60)
    print("parsers.py 解析验证")
    print("=" * 60)

    # 1. 法规条文
    law = parse_law_articles(AD_LAW_FILE)
    print(f"\n[1] parse_law_articles: {len(law)} 条")
    if law:
        print(f"    sample key:   {law[0]['key']}")
        print(f"    sample value: {law[0]['value'][:80]}...")
        print(f"    sample tags:  {law[0]['tags']}")

    # 2. 处罚案例
    cases = parse_penalty_cases(PENALTY_CASES_FILE)
    print(f"\n[2] parse_penalty_cases: {len(cases)} 条")
    if cases:
        print(f"    sample key:   {cases[0]['key']}")
        print(f"    sample value: {cases[0]['value'][:80]}...")
        print(f"    sample tags:  {cases[0]['tags']}")

    # 3. 行业规则
    industry = parse_industry_rules(INDUSTRY_RULES_FILE)
    print(f"\n[3] parse_industry_rules: {len(industry)} 条")
    if industry:
        print(f"    sample key:   {industry[0]['key']}")
        print(f"    sample value: {industry[0]['value'][:80]}...")
        print(f"    sample tags:  {industry[0]['tags']}")

    # 4. 禁用词 (JSON)
    banned = parse_banned_words(BANNED_WORDS_JSON_FILE)
    print(f"\n[4] parse_banned_words: {len(banned)} 条")
    if banned:
        print(f"    sample key:   {banned[0]['key']}")
        print(f"    sample value: {banned[0]['value']}")
        print(f"    sample tags:  {banned[0]['tags']}")

    # 5. 替代映射表
    replacement = parse_replacement_map(WORD_REPLACEMENT_FILE)
    print(f"\n[5] parse_replacement_map: {len(replacement)} 条")
    if replacement:
        print(f"    sample key:   {replacement[0]['key']}")
        print(f"    sample value: {replacement[0]['value'][:80]}...")
        print(f"    sample tags:  {replacement[0]['tags']}")

    total = len(law) + len(cases) + len(industry) + len(banned) + len(replacement)
    print(f"\n{'=' * 60}")
    print(f"原版数据合计: {total} 条")
    print(f"{'=' * 60}")

    # ── 队友版数据解析 ──────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("队友版数据解析")
    print(f"{'=' * 60}")

    # 确保输出目录存在
    PARSED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 6. 广告法全文（队友版）
    law_team = parse_law_articles_teammate()
    print(f"\n[6] parse_law_articles_teammate: {len(law_team)} 条")
    if law_team:
        print(f"    sample key:   {law_team[0]['key']}")
        print(f"    sample value: {law_team[0]['value'][:80]}...")
        print(f"    sample tags:  {law_team[0]['tags']}")
    with open(PARSED_OUTPUT_DIR / "ad_law_new.json", "w", encoding="utf-8") as f:
        json.dump(law_team, f, ensure_ascii=False, indent=2)
    print(f"    -> 已保存: {PARSED_OUTPUT_DIR / 'ad_law_new.json'}")

    # 7. 禁用词清单（队友版）
    banned_team = parse_banned_words_teammate()
    print(f"\n[7] parse_banned_words_teammate: {len(banned_team)} 条")
    if banned_team:
        print(f"    sample key:   {banned_team[0]['key']}")
        print(f"    sample value: {banned_team[0]['value'][:80]}...")
        print(f"    sample tags:  {banned_team[0]['tags']}")
    with open(PARSED_OUTPUT_DIR / "banned_words_new.json", "w", encoding="utf-8") as f:
        json.dump(banned_team, f, ensure_ascii=False, indent=2)
    print(f"    -> 已保存: {PARSED_OUTPUT_DIR / 'banned_words_new.json'}")

    # 8. 禁用词替代映射表（队友版）
    replacement_team = parse_replacement_map_teammate()
    print(f"\n[8] parse_replacement_map_teammate: {len(replacement_team)} 条")
    if replacement_team:
        print(f"    sample key:   {replacement_team[0]['key']}")
        print(f"    sample value: {replacement_team[0]['value'][:80]}...")
        print(f"    sample tags:  {replacement_team[0]['tags']}")
    with open(PARSED_OUTPUT_DIR / "replacement_new.json", "w", encoding="utf-8") as f:
        json.dump(replacement_team, f, ensure_ascii=False, indent=2)
    print(f"    -> 已保存: {PARSED_OUTPUT_DIR / 'replacement_new.json'}")

    # 9. 处罚案例（队友版）
    cases_team = parse_penalty_cases_teammate()
    print(f"\n[9] parse_penalty_cases_teammate: {len(cases_team)} 条")
    if cases_team:
        print(f"    sample key:   {cases_team[0]['key']}")
        print(f"    sample value: {cases_team[0]['value'][:80]}...")
        print(f"    sample tags:  {cases_team[0]['tags']}")
    with open(PARSED_OUTPUT_DIR / "penalty_cases_new.json", "w", encoding="utf-8") as f:
        json.dump(cases_team, f, ensure_ascii=False, indent=2)
    print(f"    -> 已保存: {PARSED_OUTPUT_DIR / 'penalty_cases_new.json'}")

    # 10. 行业禁区规则（队友版）
    industry_team = parse_industry_rules_teammate()
    print(f"\n[10] parse_industry_rules_teammate: {len(industry_team)} 条")
    if industry_team:
        print(f"    sample key:   {industry_team[0]['key']}")
        print(f"    sample value: {industry_team[0]['value'][:80]}...")
        print(f"    sample tags:  {industry_team[0]['tags']}")
    with open(PARSED_OUTPUT_DIR / "industry_rules_new.json", "w", encoding="utf-8") as f:
        json.dump(industry_team, f, ensure_ascii=False, indent=2)
    print(f"    -> 已保存: {PARSED_OUTPUT_DIR / 'industry_rules_new.json'}")

    # ── 汇总 ──────────────────────────────────────────────────
    total_team = (
        len(law_team) + len(banned_team) + len(replacement_team)
        + len(cases_team) + len(industry_team)
    )
    print(f"\n{'=' * 60}")
    print("队友版数据统计:")
    print(f"  广告法条文:      {len(law_team)} 条")
    print(f"  禁用词清单:      {len(banned_team)} 条")
    print(f"  替代映射表:      {len(replacement_team)} 条")
    print(f"  处罚案例:        {len(cases_team)} 条")
    print(f"  行业禁区规则:    {len(industry_team)} 条")
    print(f"  队友版合计:      {total_team} 条")
    print(f"  总计(原版+队友): {total + total_team} 条")
    print(f"{'=' * 60}")
