"""'kbo live --demo' 가 사용하는 가짜 relay 시퀀스.

실제 네이버 데이터를 흉내내서 1회초 ~ 2회말까지 진행한다:
  - 1회 초 시작 (0:0)
  - 1회 초 SSG 1점 (1:0)
  - 1회 말 KIA 무득점
  - 2회 초 SSG 솔로 홈런 (2:0)         ← textRelays 에 '홈런' 이벤트
  - 2회 말 KIA 솔로 홈런 (2:1)         ← 같은 패턴
  - 2회 말 KIA 추가 솔로 홈런 (2:2 동점) ← 두 번째 홈런

LiveBroadcastApp 이 demo=True 면 KBOClient 대신 DemoClient 가 호출되어
이 시퀀스를 폴링 주기마다 한 단계씩 진행시킨다.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .models import Game


DEMO_GAME_ID = "20260522SKHT02026"


def demo_game() -> Game:
    return Game.model_validate({
        "gameId": DEMO_GAME_ID,
        "categoryId": "kbo",
        "categoryName": "KBO리그",
        "gameDate": "2026-05-22",
        "gameDateTime": "2026-05-22T18:30:00",
        "stadium": "광주-기아 챔피언스 필드",
        "homeTeamCode": "KIA",
        "homeTeamName": "KIA",
        "homeTeamScore": 0,
        "awayTeamCode": "SSG",
        "awayTeamName": "SSG",
        "awayTeamScore": 0,
        "statusCode": "STARTED",
        "statusInfo": "1회초",
        "broadChannel": "DEMO",
    })


# ────────────────────── 라인업 ──────────────────────

_AWAY_BATTERS = [
    {"pcode": "67893", "name": "박성한", "posName": "유격수", "batOrder": 1, "seasonHra": 0.377, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "54812", "name": "정준재", "posName": "2루수", "batOrder": 2, "seasonHra": 0.310, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "50854", "name": "최지훈", "posName": "중견수", "batOrder": 3, "seasonHra": 0.236, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "53827", "name": "에레디아", "posName": "좌익수", "batOrder": 4, "seasonHra": 0.286, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "78224", "name": "김재환", "posName": "지명타자", "batOrder": 5, "seasonHra": 0.171, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "66864", "name": "안상현", "posName": "3루수", "batOrder": 6, "seasonHra": 0.303, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "60558", "name": "오태곤", "posName": "1루수", "batOrder": 7, "seasonHra": 0.248, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "62864", "name": "김민식", "posName": "포수", "batOrder": 8, "seasonHra": 0.250, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "53865", "name": "김정민", "posName": "우익수", "batOrder": 9, "seasonHra": 0.167, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
]

_AWAY_PITCHER = {
    "pcode": "56800", "name": "긴지로", "seasonEra": "3.21",
    "inn": "0.0", "kk": 0, "bb": 0, "run": 0, "er": 0, "hit": 0,
    "ballCount": 0, "wls": "", "tb": "선발",
}

_HOME_BATTERS = [
    {"pcode": "67449", "name": "김도영", "posName": "3루수", "batOrder": 1, "seasonHra": 0.353, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "62404", "name": "구자욱", "posName": "좌익수", "batOrder": 2, "seasonHra": 0.281, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "72443", "name": "최형우", "posName": "지명타자", "batOrder": 3, "seasonHra": 0.262, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "54400", "name": "디아즈", "posName": "1루수", "batOrder": 4, "seasonHra": 0.305, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "69418", "name": "박찬호", "posName": "유격수", "batOrder": 5, "seasonHra": 0.245, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "65586", "name": "최원준", "posName": "우익수", "batOrder": 6, "seasonHra": 0.290, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "55425", "name": "한준수", "posName": "포수", "batOrder": 7, "seasonHra": 0.270, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "55428", "name": "김선빈", "posName": "2루수", "batOrder": 8, "seasonHra": 0.275, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
    {"pcode": "55430", "name": "이우성", "posName": "중견수", "batOrder": 9, "seasonHra": 0.250, "ab": 0, "hit": 0, "run": 0, "rbi": 0, "hr": 0, "bb": 0, "kk": 0, "pa": 0, "sb": 0},
]

_HOME_PITCHER = {
    "pcode": "56036", "name": "양현종", "seasonEra": "2.94",
    "inn": "0.0", "kk": 0, "bb": 0, "run": 0, "er": 0, "hit": 0,
    "ballCount": 0, "wls": "", "tb": "선발",
}


def _make_state(
    *,
    inn: int, half: str,
    away_score: int, home_score: int,
    base1: bool = False, base2: bool = False, base3: bool = False,
    ball: int = 0, strike: int = 0, out: int = 0,
    batter_idx: int,  # 0-based in offense lineup
    text_relays: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    offense_is_home = (half == "말")
    batter_pool = _HOME_BATTERS if offense_is_home else _AWAY_BATTERS
    pitcher = _AWAY_PITCHER if offense_is_home else _HOME_PITCHER
    return {
        "category": "kbo",
        "gameId": DEMO_GAME_ID,
        "no": 100 + (inn * 10) + (0 if half == "초" else 1),
        "inn": inn,
        "homeOrAway": "1" if offense_is_home else "0",
        "pitcherVsBatterCareerStats": "데모 데이터",
        "inningScore": {
            "away": {str(i): str(away_score if i == inn else 0) for i in range(1, 10)},
            "home": {str(i): str(home_score if i == inn else 0) for i in range(1, 10)},
        },
        "currentGameState": {
            "awayScore": str(away_score),
            "homeScore": str(home_score),
            "awayHit": str(away_score), "homeHit": str(home_score),
            "awayBallFour": "0", "homeBallFour": "0",
            "awayError": "0", "homeError": "0",
            "pitcher": pitcher["pcode"],
            "batter": batter_pool[batter_idx % 9]["pcode"],
            "ball": str(ball), "strike": str(strike), "out": str(out),
            "base1": batter_pool[0]["pcode"] if base1 else "0",
            "base2": batter_pool[0]["pcode"] if base2 else "0",
            "base3": batter_pool[0]["pcode"] if base3 else "0",
        },
        "awayLineup": {"batter": _AWAY_BATTERS, "pitcher": [_AWAY_PITCHER]},
        "homeLineup": {"batter": _HOME_BATTERS, "pitcher": [_HOME_PITCHER]},
        "awayEntry": {"batter": [], "pitcher": []},
        "homeEntry": {"batter": [], "pitcher": []},
        "textRelays": text_relays or [],
    }


def _event(no: int, inn: int, half: str, title: str, text: str = "",
           is_header: bool = False) -> dict[str, Any]:
    return {
        "no": no,
        "inn": inn,
        "homeOrAway": "1" if half == "말" else "0",
        "title": title,
        "titleStyle": "0" if is_header else "8",
        "type": 0 if is_header else 8,
        "textOptions": [{"text": text or title}],
        "statusCode": 0,
    }


# ────────────────────── 시퀀스 ──────────────────────

DEMO_SEQUENCE: list[dict[str, Any]] = [
    _make_state(inn=1, half="초", away_score=0, home_score=0,
                batter_idx=0,
                text_relays=[_event(101, 1, "초", "1회초 SSG 공격", is_header=True)]),
    _make_state(inn=1, half="초", away_score=0, home_score=0,
                ball=1, strike=2, out=1, batter_idx=1,
                text_relays=[_event(101, 1, "초", "1회초 SSG 공격", is_header=True),
                              _event(102, 1, "초", "1번타자 박성한"),
                              _event(103, 1, "초", "2번타자 정준재")]),
    # SSG 1점 (적시타) — score 1:0
    _make_state(inn=1, half="초", away_score=1, home_score=0,
                base1=True, out=2, batter_idx=2,
                text_relays=[_event(101, 1, "초", "1회초 SSG 공격", is_header=True),
                              _event(102, 1, "초", "1번타자 박성한", "안타"),
                              _event(103, 1, "초", "2번타자 정준재", "1타점 적시타  ※ SSG 1점")]),
    # 1회말 시작 — KIA 무득점
    _make_state(inn=1, half="말", away_score=1, home_score=0, out=2, batter_idx=2,
                text_relays=[_event(110, 1, "말", "1회말 KIA 공격", is_header=True),
                              _event(111, 1, "말", "1번타자 김도영"),
                              _event(112, 1, "말", "2번타자 구자욱"),
                              _event(113, 1, "말", "3번타자 최형우")]),
    # 2회초 시작
    _make_state(inn=2, half="초", away_score=1, home_score=0, batter_idx=3,
                text_relays=[_event(120, 2, "초", "2회초 SSG 공격", is_header=True),
                              _event(121, 2, "초", "4번타자 에레디아")]),
    # 2회초 SSG 솔로 홈런 → score 2:0
    _make_state(inn=2, half="초", away_score=2, home_score=0, batter_idx=4,
                text_relays=[_event(120, 2, "초", "2회초 SSG 공격", is_header=True),
                              _event(122, 2, "초", "4번타자 에레디아", "솔로 홈런!!  💥"),
                              _event(123, 2, "초", "5번타자 김재환")]),
    # 2회말 시작 (KIA 공격)
    _make_state(inn=2, half="말", away_score=2, home_score=0, batter_idx=3,
                text_relays=[_event(130, 2, "말", "2회말 KIA 공격", is_header=True),
                              _event(131, 2, "말", "4번타자 디아즈")]),
    # 2회말 KIA 솔로 홈런 → 2:1
    _make_state(inn=2, half="말", away_score=2, home_score=1, batter_idx=4,
                text_relays=[_event(130, 2, "말", "2회말 KIA 공격", is_header=True),
                              _event(132, 2, "말", "4번타자 디아즈", "솔로 홈런!! 💥"),
                              _event(133, 2, "말", "5번타자 박찬호")]),
    # 2회말 KIA 추가 솔로 홈런 → 2:2 동점
    _make_state(inn=2, half="말", away_score=2, home_score=2, batter_idx=5,
                text_relays=[_event(130, 2, "말", "2회말 KIA 공격", is_header=True),
                              _event(132, 2, "말", "4번타자 디아즈", "솔로 홈런!!"),
                              _event(134, 2, "말", "5번타자 박찬호", "백투백 솔로 홈런!! 💥"),
                              _event(135, 2, "말", "6번타자 최원준")]),
]


class DemoClient:
    """KBOClient 와 동일한 시그니처를 갖는 시뮬레이션 클라이언트."""

    def __init__(self, *, step_seconds: float = 3.0) -> None:
        self.step_seconds = step_seconds
        self._idx = 0
        # 첫 호출 후 마지막 단계까지 가면 거기서 정지

    async def __aenter__(self) -> "DemoClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def aclose(self) -> None:
        return None

    async def relay(self, game_id: str, inning: int | None = None) -> dict[str, Any]:
        state = DEMO_SEQUENCE[min(self._idx, len(DEMO_SEQUENCE) - 1)]
        # 다음 호출에서 한 단계 진행
        if self._idx < len(DEMO_SEQUENCE) - 1:
            self._idx += 1
        return state

    async def schedule(self, on: date, to_date: date | None = None) -> list[Game]:
        return [demo_game()]

    async def record(self, game_id: str) -> dict[str, Any]:
        return {}

    async def preview(self, game_id: str) -> dict[str, Any]:
        return {}
