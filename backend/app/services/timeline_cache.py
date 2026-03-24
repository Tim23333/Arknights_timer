import json
import re
from pathlib import Path
from typing import Any, Dict


class TimelineCacheService:
    """File-based per-user timeline cache."""

    def __init__(self) -> None:
        self.cache_dir = Path(__file__).resolve().parents[2] / "data" / "timeline_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _safe_user_id(self, user_id: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", (user_id or "").strip())
        return clean or "default"

    def _file_path(self, user_id: str) -> Path:
        return self.cache_dir / f"{self._safe_user_id(user_id)}.json"

    def load(self, user_id: str) -> Dict[str, Any]:
        path = self._file_path(user_id)
        if not path.exists():
            return {
                "ok": True,
                "user_id": self._safe_user_id(user_id),
                "has_cache": False,
                "data": None,
            }
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            return {
                "ok": True,
                "user_id": self._safe_user_id(user_id),
                "has_cache": True,
                "data": content,
            }
        except (OSError, json.JSONDecodeError):
            return {
                "ok": False,
                "user_id": self._safe_user_id(user_id),
                "has_cache": False,
                "data": None,
                "message": "缓存文件读取失败或已损坏。",
            }

    def save(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = self._file_path(user_id)
        try:
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return {
                "ok": True,
                "user_id": self._safe_user_id(user_id),
                "message": "缓存保存成功。",
            }
        except OSError:
            return {
                "ok": False,
                "user_id": self._safe_user_id(user_id),
                "message": "缓存保存失败。",
            }
