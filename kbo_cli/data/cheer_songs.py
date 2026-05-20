"""각 구단 응원 구호/대표 응원가 안내.

저작권 문제로 전체 가사 대신 응원가 제목과 짧은 대표 구호만 포함합니다.
"""

from __future__ import annotations

CHEER: dict[str, dict[str, list[str] | str]] = {
    "KIA": {
        "battle_cry": "아 ~ 기아 타이거즈! 승리를 위하여!",
        "songs": ["KIA 응원가 메들리", "남행열차 (개사)", "최강 KIA"],
        "famous_chant": "최강 KIA! 최강 KIA!",
    },
    "SS": {
        "battle_cry": "사자가 나가신다! 길을 비켜라!",
        "songs": ["라이온즈 송", "단결의 함성", "푸른 피의 함성"],
        "famous_chant": "라이온즈! 라이온즈!",
    },
    "LG": {
        "battle_cry": "엘! 지! 트윈스!",
        "songs": ["승리의 함성", "엘지 트윈스 응원가", "신바람 LG"],
        "famous_chant": "엘! 지! 승리! 트윈스!",
    },
    "OB": {
        "battle_cry": "두산 베어스! 가자!",
        "songs": ["두산 베어스 송", "안타송", "Drink Beer"],
        "famous_chant": "두산 베어스! 두산 베어스!",
    },
    "SSG": {
        "battle_cry": "SSG 랜더스! 인천의 자존심!",
        "songs": ["랜더스 응원가", "연안부두 (개사)", "Let's Go SSG"],
        "famous_chant": "SSG! 랜더스!",
    },
    "LT": {
        "battle_cry": "롯데! 자이언츠! 우~",
        "songs": ["부산 갈매기", "돌아와요 부산항에 (개사)", "롯데 자이언츠 응원가", "사직노래방"],
        "famous_chant": "롯! 데! 자이언츠!",
    },
    "KT": {
        "battle_cry": "마법사들의 함성! KT 위즈!",
        "songs": ["위즈 송", "수원의 자존심", "Magic Time"],
        "famous_chant": "KT! 위즈!",
    },
    "WO": {
        "battle_cry": "히어로즈! 영웅들의 함성!",
        "songs": ["히어로즈 응원가", "Go Heroes Go", "고척 함성"],
        "famous_chant": "키움! 히어로즈!",
    },
    "HH": {
        "battle_cry": "최강 한화! 이글스 파이팅!",
        "songs": ["한화 이글스 응원가", "내 사랑 한화", "독수리 5형제"],
        "famous_chant": "최강! 한화! 이글스!",
    },
    "NC": {
        "battle_cry": "공룡들의 포효! NC 다이노스!",
        "songs": ["다이노스 송", "창원의 함성", "공룡의 도시"],
        "famous_chant": "엔! 씨! 다이노스!",
    },
}


def cheer(team_code: str) -> dict[str, list[str] | str]:
    from .teams import normalize
    return CHEER.get(normalize(team_code), {
        "battle_cry": "-",
        "songs": [],
        "famous_chant": "-",
    })
