import os
from pathlib import Path
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DB_PATH = os.getenv("VMEM_DB_PATH", str(_PROJECT_ROOT / "pipeline" / "data" / "vmem.db"))
BANNED_WORDS_PATH = os.getenv("BANNED_WORDS_PATH", str(_PROJECT_ROOT / "pipeline" / "data" / "禁用词" / "banned_words.json"))
REPLACEMENT_PATH = os.getenv("REPLACEMENT_PATH", str(_PROJECT_ROOT / "pipeline" / "data" / "parsed" / "replacement.json"))
