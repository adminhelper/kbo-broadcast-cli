"""KBO 10개 구단 메타데이터 (팀 코드, 이름, 색상, 홈구장, 마스코트)."""

from __future__ import annotations

from typing import TypedDict


class TeamMeta(TypedDict):
    code: str
    name: str
    full_name: str
    color: str  # rich color name 또는 hex
    stadium: str
    mascot: str


TEAMS: dict[str, TeamMeta] = {
    "HT": {"code": "HT", "name": "KIA",  "full_name": "KIA 타이거즈",   "color": "red",          "stadium": "광주-기아 챔피언스 필드", "mascot": "호걸이"},
    "SS": {"code": "SS", "name": "삼성", "full_name": "삼성 라이온즈",   "color": "blue",         "stadium": "대구 삼성라이온즈파크",    "mascot": "블레오"},
    "LG": {"code": "LG", "name": "LG",   "full_name": "LG 트윈스",       "color": "magenta",      "stadium": "잠실 야구장",              "mascot": "럭키"},
    "OB": {"code": "OB", "name": "두산", "full_name": "두산 베어스",     "color": "navy_blue",    "stadium": "잠실 야구장",              "mascot": "철웅이"},
    "SK": {"code": "SK", "name": "SSG",  "full_name": "SSG 랜더스",      "color": "red3",         "stadium": "인천 SSG 랜더스필드",      "mascot": "랜디"},
    "LT": {"code": "LT", "name": "롯데", "full_name": "롯데 자이언츠",   "color": "dark_red",     "stadium": "사직 야구장",              "mascot": "누리/아라"},
    "KT": {"code": "KT", "name": "KT",   "full_name": "KT 위즈",         "color": "grey50",       "stadium": "수원 KT위즈파크",          "mascot": "빅, 빙, 빈"},
    "WO": {"code": "WO", "name": "키움", "full_name": "키움 히어로즈",   "color": "dark_red",     "stadium": "고척 스카이돔",            "mascot": "동글이"},
    "HH": {"code": "HH", "name": "한화", "full_name": "한화 이글스",     "color": "orange3",      "stadium": "한화생명 볼파크",          "mascot": "수리"},
    "NC": {"code": "NC", "name": "NC",   "full_name": "NC 다이노스",     "color": "dark_cyan",    "stadium": "창원 NC파크",              "mascot": "단디·쎄리"},
}


def team(code: str | None) -> TeamMeta:
    if not code:
        return {"code": "", "name": code or "-", "full_name": code or "-",
                "color": "white", "stadium": "", "mascot": ""}
    return TEAMS.get(code.upper(), {
        "code": code, "name": code, "full_name": code,
        "color": "white", "stadium": "", "mascot": "",
    })


def colored(code: str | None, label: str | None = None) -> str:
    """Rich 마크업 컬러로 팀명 렌더링."""
    t = team(code)
    name = label or t["name"]
    return f"[bold {t['color']}]{name}[/]"
