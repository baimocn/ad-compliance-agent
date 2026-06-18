"""工具1：禁用词规则匹配 — 纯确定性，不依赖 LLM"""
import re
import json
import sys
from pathlib import Path
_PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT / 'backend'))
from schemas import BannedWordHit


class BannedWordMatcher:
    def __init__(self, dict_path: str):
        self._entries = []
        self._load(dict_path)

    def _load(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        for item in raw:
            try:
                pattern = re.compile(item['pattern'], re.IGNORECASE)
                self._entries.append({
                    'word': item['word'],
                    'category': item['category'],
                    'regulation_ref': item['regulation_ref'],
                    'pattern': pattern,
                })
            except re.error:
                continue

    def match(self, text: str) -> list[BannedWordHit]:
        hits = []
        seen_positions = set()
        for entry in self._entries:
            for m in entry['pattern'].finditer(text):
                pos = (m.start(), m.end())
                if pos not in seen_positions:
                    seen_positions.add(pos)
                    hits.append(BannedWordHit(
                        word=m.group(),
                        category=entry['category'],
                        position=pos,
                        regulation_ref=entry['regulation_ref'],
                    ))
        return hits
