"""
广告法合规审查 Agent — 数据解析器

负责将原始 Markdown 文件解析为结构化的 chunk 列表。
每个 chunk 是一个 dict:
{
    "key": str,           # vmem 存储 key
    "text": str,          # chunk 正文
    "source": str,        # 子库标识
    "tags": list[str],    # 标签列表
    "metadata": dict      # 额外元数据
}
"""
import re
from pathlib import Path
from typing import Optional
from config import (
    SOURCE_LAW, SOURCE_CASE, SOURCE_INDUSTRY,
    SOURCE_BANNED, SOURCE_REPLACE,
    KEY_PREFIX_LAW, KEY_PREFIX_CASE, KEY_PREFIX_INDUSTRY,
    KEY_PREFIX_BANNED, KEY_PREFIX_REPLACE,
    ChunkingConfig,
)

cfg = ChunkingConfig()


# ============================================================
# 工具函数
# ============================================================

def read_file(path: Path) -> str:
    """读取文件，返回纯文本。"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def strip_page_markers(text: str) -> str:
    """去除 PDF 转换遗留的页码标记: <!-- 第 N 页 -->"""
    text = re.sub(r"<!--\s*第\s*\d+\s*页\s*-->", "", text)
    # 去除孤立的纯数字行 (页码残留)
    text = re.sub(r"^\d+\s*$", "", text, flags=re.MULTILINE)
    return text


def clean_text(text: str) -> str:
    """通用文本清洗。"""
    text = strip_page_markers(text)
    # 去除连续空行，保留最多 1 个
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 去除行首全角空格中的孤立空格行
    text = re.sub(r"^\s+$", "", text, flags=re.MULTILINE)
    return text.strip()


def extract_chapter(text_before: str) -> str:
    """从当前位置之前的文本中提取最近的章名。"""
    chapters = re.findall(r"(第.{1,2}章\s*\S+)", text_before)
    return chapters[-1] if chapters else ""


def extract_chapter_for_article(article_num: str, law_text: str) -> str:
    """根据条文号确定所属章。"""
    # 章→条文范围映射 (2015修订版)
    chapter_ranges = {
        "第一章 总则": (1, 7),
        "第二章 广告内容准则": (8, 28),
        "第三章 广告行为规范": (29, 45),
        "第四章 监督管理": (46, 53),
        "第五章 法律责任": (54, 73),
        "第六章 附则": (74, 75),
    }
    # 提取条文数字
    num_match = re.search(r"\d+", article_num)
    if not num_match:
        return ""
    num = int(num_match.group())
    for chapter, (lo, hi) in chapter_ranges.items():
        if lo <= num <= hi:
            return chapter
    return ""


# ============================================================
# 子库 A: 法规条文解析
# ============================================================

def parse_law_articles(file_path: Path) -> list[dict]:
    """
    解析《广告法》释义.md，按「第X条」切分。

    每条包含：条文原文 + 释义内容。
    同时解析《互联网广告管理办法》补充入库。
    """
    chunks = []
    raw = read_file(file_path)
    text = clean_text(raw)

    # 定位释义部分的起始 (第一个「第一章 总则」后面跟着「第一条 ... 【释义】」)
    # 文件结构: 前言 → 目录 → 法律正文 → 释义部分
    # 释义部分从 line 851 附近开始，有 【释义】 标记

    # 按条文切分
    # 匹配: 第一条、第二条 ... 第七十五条
    article_pattern = re.compile(
        r"(第.{1,3}条)\s*(.*?)(?=\n第.{1,3}条\s|\Z)",
        re.DOTALL
    )

    matches = list(article_pattern.finditer(text))

    for m in matches:
        article_num = m.group(1).strip()
        content = m.group(2).strip()

        # 只处理有释义标记的内容 (释义部分)
        if cfg.interpretation_marker not in content and len(content) < 200:
            # 这是法律正文，不是释义，跳过短文本
            continue

        # 提取释义
        parts = content.split(cfg.interpretation_marker, 1)
        article_text = parts[0].strip()
        interpretation = parts[1].strip() if len(parts) > 1 else ""

        # 合并: 条文 + 释义
        full_text = f"{article_num}\n{article_text}"
        if interpretation:
            full_text += f"\n\n【释义】{interpretation}"

        # 去除过短的 chunk
        if len(full_text) < cfg.min_chunk_chars:
            continue

        chapter = extract_chapter_for_article(article_num, text)
        chapter_short = chapter.split()[-1] if chapter else ""

        # 提取该条涉及的关键词 (用于 tags)
        tag_keywords = _extract_law_tags(full_text)

        chunks.append({
            "key": f"{KEY_PREFIX_LAW}:{article_num}",
            "text": full_text,
            "source": SOURCE_LAW,
            "tags": ["法规条文", article_num, chapter_short] + tag_keywords,
            "metadata": {
                "article_num": article_num,
                "chapter": chapter,
                "has_interpretation": bool(interpretation),
                "char_count": len(full_text),
            },
        })

    return chunks


def parse_internet_ads_rules(file_path: Path) -> list[dict]:
    """解析《互联网广告管理办法》，按条文切分。"""
    chunks = []
    raw = read_file(file_path)
    text = clean_text(raw)

    article_pattern = re.compile(
        r"(第.{1,3}条)\s*(.*?)(?=\n第.{1,3}条\s|\Z)",
        re.DOTALL
    )

    for m in article_pattern.finditer(text):
        article_num = m.group(1).strip()
        content = m.group(2).strip()

        if len(content) < cfg.min_chunk_chars:
            continue

        chunks.append({
            "key": f"{KEY_PREFIX_LAW}:internet:{article_num}",
            "text": f"【互联网广告管理办法】{article_num}\n{content}",
            "source": SOURCE_LAW,
            "tags": ["法规条文", "互联网广告", article_num],
            "metadata": {
                "article_num": article_num,
                "source_doc": "互联网广告管理办法",
                "char_count": len(content),
            },
        })

    return chunks


def _extract_law_tags(text: str) -> list[str]:
    """从法规文本中提取关键词标签。"""
    tag_map = {
        "极限用语": ["最高级", "最佳", "国家级"],
        "虚假广告": ["虚假", "引人误解"],
        "医疗广告": ["医疗", "药品", "医疗器械"],
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
# 子库 B: 处罚案例解析
# ============================================================

def parse_cases(file_path: Path) -> list[dict]:
    """
    解析处罚案例库.md，按「案例 N」切分。

    每个案例包含: 标题、违规内容、处罚依据、处罚结果、行业、违规类型。
    """
    chunks = []
    raw = read_file(file_path)
    text = clean_text(raw)

    # 按案例切分
    case_pattern = re.compile(
        r"(###\s*案例\s*\d+)\s*\n(.*?)(?=###\s*案例\s*\d+|\Z)",
        re.DOTALL
    )

    for m in case_pattern.finditer(text):
        case_id = m.group(1).strip()
        case_body = m.group(2).strip()

        # 提取结构化字段
        fields = _parse_case_fields(case_body)

        # 构建可读文本
        readable = _format_case(case_id, fields)

        case_num = re.search(r"\d+", case_id)
        num = case_num.group() if case_num else "0"

        chunks.append({
            "key": f"{KEY_PREFIX_CASE}:{num}",
            "text": readable,
            "source": SOURCE_CASE,
            "tags": [
                "处罚案例",
                fields.get("industry", ""),
                fields.get("violation_type", ""),
            ],
            "metadata": {
                "case_id": case_id,
                "title": fields.get("title", ""),
                "industry": fields.get("industry", ""),
                "violation_type": fields.get("violation_type", ""),
                "penalty": fields.get("penalty", ""),
                "law_basis": fields.get("law_basis", ""),
            },
        })

    return chunks


def _parse_case_fields(body: str) -> dict:
    """从案例正文提取结构化字段。"""
    fields = {}
    patterns = {
        "title": r"\*\*标题\*\*[：:]\s*(.+)",
        "violation": r"\*\*违规内容\*\*[：:]\s*(.+)",
        "law_basis": r"\*\*处罚依据\*\*[：:]\s*(.+)",
        "penalty": r"\*\*处罚结果\*\*[：:]\s*(.+)",
        "industry": r"\*\*行业\*\*[：:]\s*(.+)",
        "violation_type": r"\*\*违规类型\*\*[：:]\s*(.+)",
    }
    for field_name, pat in patterns.items():
        match = re.search(pat, body)
        if match:
            fields[field_name] = match.group(1).strip()
    return fields


def _format_case(case_id: str, fields: dict) -> str:
    """格式化案例为可读文本。"""
    lines = [case_id]
    if fields.get("title"):
        lines.append(f"标题: {fields['title']}")
    if fields.get("violation"):
        lines.append(f"违规内容: {fields['violation']}")
    if fields.get("law_basis"):
        lines.append(f"处罚依据: {fields['law_basis']}")
    if fields.get("penalty"):
        lines.append(f"处罚结果: {fields['penalty']}")
    if fields.get("industry"):
        lines.append(f"行业: {fields['industry']}")
    if fields.get("violation_type"):
        lines.append(f"违规类型: {fields['violation_type']}")
    return "\n".join(lines)


# ============================================================
# 子库 C: 行业规则解析
# ============================================================

def parse_industry_rules(file_path: Path) -> list[dict]:
    """
    解析行业广告禁区规则.md，按「行业」切分。

    每个行业一个 chunk，包含: 法律依据、禁区规则表、高频违规场景。
    """
    chunks = []
    raw = read_file(file_path)
    text = clean_text(raw)

    # 按行业切分: ## 一、食品行业
    industry_pattern = re.compile(
        r"(##\s*[一二三四五六七八九十]+[、.]\s*(.+?)\s*\n)"
        r"(.*?)(?=\n##\s*[一二三四五六七八九十]+[、.]|\Z)",
        re.DOTALL
    )

    for m in industry_pattern.finditer(text):
        industry_name = m.group(2).strip()
        industry_body = m.group(3).strip()

        # 构建 key
        industry_key = _industry_name_to_key(industry_name)

        # 构建可读文本
        readable = f"行业: {industry_name}\n\n{industry_body}"

        # 提取规则数
        rule_count = len(re.findall(r"\|\s*不得|须", industry_body))

        chunks.append({
            "key": f"{KEY_PREFIX_INDUSTRY}:{industry_key}",
            "text": readable,
            "source": SOURCE_INDUSTRY,
            "tags": ["行业规则", industry_name],
            "metadata": {
                "industry": industry_name,
                "rule_count": rule_count,
            },
        })

    return chunks


def _industry_name_to_key(name: str) -> str:
    """行业名转 key 标识。"""
    mapping = {
        "食品行业": "food",
        "化妆品行业": "cosmetic",
        "教育培训行业": "education",
        "金融理财行业": "finance",
        "房地产行业": "real_estate",
        "医疗/药品行业": "medical",
        "医疗": "medical",
        "酒类行业": "alcohol",
    }
    for cn, en in mapping.items():
        if cn in name:
            return en
    return re.sub(r"[^\w]", "_", name).lower()


# ============================================================
# 辅助库: 禁用词清单解析
# ============================================================

def parse_banned_words(file_path: Path) -> list[dict]:
    """
    解析禁用词清单.md，按「分类」切分。
    每个分类一个 chunk，含所有禁用词。
    """
    chunks = []
    raw = read_file(file_path)
    text = clean_text(raw)

    # 去掉头部元信息 (--- 之前)
    meta_end = text.find("---")
    if meta_end > 0:
        text = text[meta_end + 3:].strip()

    # 按二级标题切分
    sections = re.split(r"\n(?=## )", text)

    for section in sections:
        section = section.strip()
        if not section.startswith("##"):
            continue

        # 提取分类名
        title_match = re.match(r"##\s*[一二三四五六七八九十]+[、.]\s*(.+)", section)
        if not title_match:
            continue
        category = title_match.group(1).strip()

        # 提取所有禁用词 (从 ``` 包裹的代码块中)
        words = re.findall(r"```\s*\n?(.*?)```", section, re.DOTALL)
        all_words = []
        for block in words:
            # 按中文逗号、顿号、换行分隔
            w = re.split(r"[，、\n]+", block)
            all_words.extend([x.strip() for x in w if x.strip()])

        if not all_words:
            continue

        # 每个子分类单独一个 chunk (如果太长，按子标题 ### 切分)
        sub_sections = re.split(r"\n(?=### )", section)
        for sub in sub_sections:
            sub = sub.strip()
            if not sub:
                continue
            sub_title_match = re.match(r"###?\s*[\d.]*\s*(.+)", sub)
            sub_title = sub_title_match.group(1).strip() if sub_title_match else category

            # 提取该子分类的词
            sub_words_blocks = re.findall(r"```\s*\n?(.*?)```", sub, re.DOTALL)
            sub_words = []
            for block in sub_words_blocks:
                w = re.split(r"[，、\n]+", block)
                sub_words.extend([x.strip() for x in w if x.strip()])

            if not sub_words:
                # 该子 section 没有代码块词，使用整个 section
                continue

            chunk_text = f"禁用词分类: {category} - {sub_title}\n\n"
            chunk_text += "禁用词列表:\n" + "、".join(sub_words)
            chunk_text += f"\n\n共计 {len(sub_words)} 个禁用词/短语。"

            cat_key = re.sub(r"[^\w]", "_", sub_title)[:30]

            chunks.append({
                "key": f"{KEY_PREFIX_BANNED}:{cat_key}",
                "text": chunk_text,
                "source": SOURCE_BANNED,
                "tags": ["禁用词", category, sub_title],
                "metadata": {
                    "category": category,
                    "subcategory": sub_title,
                    "word_count": len(sub_words),
                    "words": sub_words,
                },
            })

    return chunks


# ============================================================
# 辅助库: 替代映射表解析
# ============================================================

def parse_replacements(file_path: Path) -> list[dict]:
    """
    解析禁用词替代映射表.md，按分类切分。
    每个分类一个 chunk，含映射关系。
    """
    chunks = []
    raw = read_file(file_path)
    text = clean_text(raw)

    # 去掉头部元信息
    meta_end = text.find("---")
    if meta_end > 0:
        text = text[meta_end + 3:].strip()

    sections = re.split(r"\n(?=## )", text)

    for section in sections:
        section = section.strip()
        if not section.startswith("##"):
            continue

        title_match = re.match(r"##\s*[一二三四五六七八九十]+[、.]\s*(.+)", section)
        if not title_match:
            continue
        category = title_match.group(1).strip()

        # 解析表格行
        rows = re.findall(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", section)
        pairs = []
        for row in rows:
            banned = row[0].strip()
            replacement = row[1].strip()
            note = row[2].strip()
            if banned == "禁用词" or "---" in banned:
                continue  # 跳过表头和分隔行
            if banned and replacement:
                pairs.append({
                    "banned": banned,
                    "replacement": replacement,
                    "note": note,
                })

        if not pairs:
            continue

        # 构建文本
        chunk_text = f"替代映射分类: {category}\n\n"
        for p in pairs:
            chunk_text += f"- {p['banned']} → {p['replacement']}"
            if p["note"]:
                chunk_text += f" ({p['note']})"
            chunk_text += "\n"

        cat_key = re.sub(r"[^\w]", "_", category)[:30]

        chunks.append({
            "key": f"{KEY_PREFIX_REPLACE}:{cat_key}",
            "text": chunk_text,
            "source": SOURCE_REPLACE,
            "tags": ["替代映射", category],
            "metadata": {
                "category": category,
                "pair_count": len(pairs),
                "pairs": pairs,
            },
        })

    return chunks


# ============================================================
# 统一入口
# ============================================================

def parse_all() -> dict[str, list[dict]]:
    """
    解析所有数据文件，返回按子库分组的 chunk 字典。

    Returns:
        {
            "law": [...],        # 子库 A: 法规条文
            "case": [...],       # 子库 B: 处罚案例
            "industry": [...],   # 子库 C: 行业规则
            "banned": [...],     # 辅助: 禁用词
            "replacement": [...],# 辅助: 替代映射
        }
    """
    from config import LAW_FILE, INTERNET_ADS, CASE_FILE, INDUSTRY_FILE, \
        BANNED_FILE, REPLACEMENT_FILE

    law_chunks = parse_law_articles(LAW_FILE)
    internet_chunks = parse_internet_ads_rules(INTERNET_ADS)
    case_chunks = parse_cases(CASE_FILE)
    industry_chunks = parse_industry_rules(INDUSTRY_FILE)
    banned_chunks = parse_banned_words(BANNED_FILE)
    replacement_chunks = parse_replacements(REPLACEMENT_FILE)

    return {
        "law": law_chunks + internet_chunks,
        "case": case_chunks,
        "industry": industry_chunks,
        "banned": banned_chunks,
        "replacement": replacement_chunks,
    }


if __name__ == "__main__":
    all_chunks = parse_all()
    for name, chunks in all_chunks.items():
        print(f"[{name}] {len(chunks)} chunks")
        if chunks:
            print(f"  sample key: {chunks[0]['key']}")
            print(f"  sample text (前100字): {chunks[0]['text'][:100]}")
            print(f"  sample tags: {chunks[0]['tags']}")
        print()
