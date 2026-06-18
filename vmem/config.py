"""
Hermes Memory System — 路径和配置管理
所有路径基于用户主目录自动检测，支持通过环境变量或 config.json 覆盖。
"""

import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# 自动检测路径
# ---------------------------------------------------------------------------

_HOME = Path.home()

# 默认路径（基于用户主目录，自动适配任何机器）
DEFAULTS = {
    "home": str(_HOME),
    "claude_dir": str(_HOME / ".claude"),
    "memory_dir": str(_HOME / ".claude" / "memory"),
    "db_path": str(_HOME / ".claude" / "memory" / "vmem.db"),
    "mcp_servers_dir": str(_HOME / ".claude" / "mcp-servers"),
    "hooks_dir": str(_HOME / ".claude" / "hooks"),
    "model_path": str(_HOME / "bge-small-zh-v1.5"),
}

# ---------------------------------------------------------------------------
# 加载 config.json（如果存在）
# ---------------------------------------------------------------------------

_CONFIG_PATHS = [
    Path(__file__).parent / "config.json",           # 包内的 config
    _HOME / ".claude" / "memory" / "config.json",     # 用户 memory 目录
]

_CONFIG = {}


def _load_config():
    global _CONFIG
    for p in _CONFIG_PATHS:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    _CONFIG = json.load(f)
                return
            except Exception:
                continue
    _CONFIG = {}


_load_config()


# ---------------------------------------------------------------------------
# 环境变量覆盖（优先级最高）
# ---------------------------------------------------------------------------

def get(key: str) -> str:
    """获取配置值。优先级：环境变量 > config.json > 默认值。"""
    env_key = f"HMS_{key.upper()}"
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val
    return _CONFIG.get(key, DEFAULTS.get(key, ""))


# 便捷访问
DB_PATH = get("db_path")
MODEL_PATH = get("model_path")
CLAUDE_DIR = get("claude_dir")
MEMORY_DIR = get("memory_dir")
MCP_SERVERS_DIR = get("mcp_servers_dir")
HOOKS_DIR = get("hooks_dir")
HOME_DIR = get("home")

# 确保目录存在
os.makedirs(MEMORY_DIR, exist_ok=True)
