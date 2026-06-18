"""
广告合规审核 Pipeline 配置
"""

from pathlib import Path

# ── 项目根目录 ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent        # D:/Desktop/黑客松
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
DATA_DIR     = PROJECT_ROOT / "数据集"

# ── 数据文件路径 ─────────────────────────────────────────────
AD_LAW_FILE            = DATA_DIR / "《中华人民共和国广告法》释义.md"
INTERNET_AD_FILE       = DATA_DIR / "互联网广告管理办法（公开征求意见稿）.md"
BANNED_WORDS_FILE      = DATA_DIR / "禁用词清单.md"
WORD_REPLACEMENT_FILE  = DATA_DIR / "禁用词替代映射表.md"
INDUSTRY_RULES_FILE    = DATA_DIR / "行业广告禁区规则.md"
PENALTY_CASES_FILE     = DATA_DIR / "处罚案例库.md"
BANNED_WORDS_JSON_FILE = PIPELINE_DIR / "data" / "禁用词" / "banned_words.json"

DATA_FILES = {
    "ad_law":           AD_LAW_FILE,
    "internet_ad":      INTERNET_AD_FILE,
    "banned_words":     BANNED_WORDS_FILE,
    "word_replacement": WORD_REPLACEMENT_FILE,
    "industry_rules":   INDUSTRY_RULES_FILE,
    "penalty_cases":    PENALTY_CASES_FILE,
}

# ── vmem 向量数据库 ──────────────────────────────────────────
VMEM_DIR  = PROJECT_ROOT / "vmem"
DB_PATH   = PIPELINE_DIR / "data" / "vmem.db"

# ── Embedding 模型 ───────────────────────────────────────────
EMBEDDING_MODEL    = "BAAI/bge-small-zh-v1.5"
EMBEDDING_DIM      = 512
EMBEDDING_DEVICE   = "cpu"          # 可改为 "cuda" / "mps"
EMBEDDING_BATCH    = 64

# ── 子库 source 标识 ─────────────────────────────────────────
SOURCE_AD_LAW        = "ad_law"
SOURCE_PENALTY_CASE  = "penalty_case"
SOURCE_INDUSTRY_RULE = "industry_rule"

# ── chunk 策略 ───────────────────────────────────────────────
# 法规条文：按条文边界切分（正则匹配 "第X条"），不设固定 chunk_size
# 案例   ：按条（每个案例为一个 chunk）
# 规则   ：按条目（每个禁用词/规则为一个 chunk）
CHUNK_STRATEGY = {
    "ad_law":       {"mode": "article_boundary", "pattern": r"^第.{1,5}条"},
    "penalty_case": {"mode": "case_per_chunk"},
    "industry_rule":{"mode": "entry_per_chunk"},
}
