"""사용자 설정 (선호 팀 등) 저장.

저장 위치는 XDG_CONFIG_HOME을 따른다:
  - $XDG_CONFIG_HOME/kbo-cli/config.json
  - 없으면 ~/.config/kbo-cli/config.json
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "kbo-cli"


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class Config:
    favorite_team: str | None = None  # 팀 코드 (KIA, SSG, LG, ...)
    # 향후 확장 여지 (알림, 색 테마, 폴링 간격 등)
    extras: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Config":
        p = config_path()
        if not p.exists():
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return cls(
                favorite_team=data.get("favorite_team"),
                extras=data.get("extras") or {},
            )
        except (OSError, json.JSONDecodeError):
            return cls()

    def save(self) -> Path:
        d = config_dir()
        d.mkdir(parents=True, exist_ok=True)
        p = config_path()
        p.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    @property
    def is_configured(self) -> bool:
        return bool(self.favorite_team)
