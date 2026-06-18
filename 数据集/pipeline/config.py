"""
广告法合规审查 Agent — 数据管线配置
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================
# 路径
# ============================================================
DATA_DIR = Path(r"D:\Desktop\黑客松\数据集")

# 原始数据文件
LAW_FILE        = DATA_DIR / "《中华人民共和国广告法》释义.md"
INTERNET_ADS    = DATA_DIR / "互联网广告管理办法（公开征求意见稿）.md"
CASE_FILE       = DATA_DIR / "处罚案例库.md"
INDUSTRY_FILE   = DATA_DIR / "行业广告禁区规则.md"
BANNED_FILE     = DATA_DIR / "禁用词清单.md"
REPLACEMENT_FILE = DATA_DIR / "禁用词替代映射表.md"


# ============================================================
# 子库 source 标识
# ============================================================
SOURCE_LAW      = "ad_law"          # 子库 A: 法规条文
SOURCE_CASE     = "ad_case"         # 子库 B: 处罚案例
SOURCE_INDUSTRY = "ad_industry"     # 子库 C: 行业规则
SOURCE_BANNED   = "ad_banned"       # 辅助: 禁用词清单
SOURCE_REPLACE  = "ad_replacement"  # 辅助: 替代映射表


# ============================================================
# vmem 存储 key 前缀
# ============================================================
KEY_PREFIX_LAW       = "law"
KEY_PREFIX_CASE      = "case"
KEY_PREFIX_INDUSTRY  = "industry"
KEY_PREFIX_BANNED    = "banned"
KEY_PREFIX_REPLACE   = "replace"
KEY_PREFIX_FEEDBACK  = "feedback"


# ============================================================
# Embedding 配置
# ============================================================
@dataclass
class EmbeddingConfig:
    model_name: str = "text2vec-base-chinese"  # 中文 embedding 模型
    batch_size: int = 32
    max_length: int = 512


# ============================================================
# 检索配置
# ============================================================
@dataclass
class RetrievalConfig:
    top_k: int = 10
    # search_fusion 四路权重
    w_vec: float = 0.5    # 向量相似度
    w_fts: float = 0.2    # 全文检索
    w_time: float = 0.1   # 时间衰减
    w_conf: float = 0.2   # 反馈置信度
    # 子库权重（用于三库结果融合时的 boost）
    law_weight: float = 0.4
    case_weight: float = 0.3
    industry_weight: float = 0.3


# ============================================================
# 切分配置
# ============================================================
@dataclass
class ChunkingConfig:
    # 法规条文切分
    article_pattern: str = r"^第.{1,3}条"
    # 处罚案例切分
    case_pattern: str = r"^###\s*案例\s*(\d+)"
    # 行业规则切分
    industry_pattern: str = r"^##\s*[一二三四五六七八九十]+[、.]\s*(.+)"
    # 禁用词分类切分
    banned_pattern: str = r"^##\s*[一二三四五六七八九十]+[、.]\s*(.+)"
    # 通用: 释义标记
    interpretation_marker: str = "【释义】"
    # 最小 chunk 字数 (低于此值合并到前一个 chunk)
    min_chunk_chars: int = 50


# ============================================================
# 评测配置
# ============================================================
@dataclass
class EvalConfig:
    agent_eval_count: int = 30
    rag_eval_count: int = 15
    eval_output_dir: Path = DATA_DIR / "eval_results"
