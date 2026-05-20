"""네이버 스포츠 비공식 API + KBO 공식 사이트 스크래핑.

엔드포인트는 m.sports.naver.com 모바일 페이지에서 발견된 비공식 경로입니다.
사용에 책임은 사용자에게 있으며, 과도한 폴링은 피하세요.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from .models import Game, RawDict, TeamRank

NAVER_BASE = "https://api-gw.sports.naver.com"
KBO_BASE = "https://www.koreabaseball.com"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://m.sports.naver.com/",
}


class KBOClient:
    """네이버 스포츠 + KBO 공식 사이트 통합 클라이언트."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._http = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            follow_redirects=True,
        )

    async def __aenter__(self) -> "KBOClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._http.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    # ───────────────────────── Naver ─────────────────────────

    async def _get_json(self, path: str, **params: Any) -> RawDict:
        url = f"{NAVER_BASE}{path}"
        r = await self._http.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        if not data.get("success", False):
            raise RuntimeError(f"Naver API failed: {data}")
        return data.get("result", {}) or {}

    async def schedule(self, from_date: date, to_date: date | None = None) -> list[Game]:
        """KBO 일정 + 결과. 같은 날 단일 조회면 to_date 생략."""
        to_date = to_date or from_date
        data = await self._get_json(
            "/schedule/games",
            fields="basic,schedule,baseball",
            upperCategoryId="kbaseball",
            fromDate=from_date.isoformat(),
            toDate=to_date.isoformat(),
        )
        games = [Game.model_validate(g) for g in data.get("games", [])]
        # 시범경기/이벤트 매치는 제외, KBO 정규경기만
        return [g for g in games if g.is_kbo]

    async def calendar(self, on: date) -> RawDict:
        return await self._get_json(
            "/schedule/calendar",
            upperCategoryId="kbaseball",
            date=on.isoformat(),
        )

    async def relay(self, game_id: str, inning: int | None = None) -> RawDict:
        """문자 중계 + 현재 카운트/주자/이닝 점수."""
        params: dict[str, Any] = {}
        if inning is not None:
            params["inning"] = inning
        data = await self._get_json(f"/schedule/games/{game_id}/relay", **params)
        return data.get("textRelayData", {}) or {}

    async def record(self, game_id: str) -> RawDict:
        """박스스코어: 타자/투수 기록, 팀 기록, 결승타 등."""
        data = await self._get_json(f"/schedule/games/{game_id}/record")
        return data.get("recordData", {}) or {}

    async def preview(self, game_id: str) -> RawDict:
        """예고 라인업, 선발 투수, 시즌 기록, 상대 전적."""
        data = await self._get_json(f"/schedule/games/{game_id}/preview")
        return data.get("previewData", {}) or {}

    # ───────────────────────── KBO 공식 ─────────────────────────

    async def standings(self, season: int | None = None) -> list[TeamRank]:
        """KBO 공식 팀 순위표 HTML 스크래핑.

        네이버 standings 엔드포인트는 인증을 요구해서 KBO 공식 사이트의
        TeamRankDaily 페이지를 파싱합니다.
        """
        url = f"{KBO_BASE}/Record/TeamRank/TeamRankDaily.aspx"
        params = {}
        if season:
            params["seasonId"] = str(season)
        r = await self._http.get(url, params=params)
        r.raise_for_status()
        return _parse_kbo_standings(r.text)


# ────────────────────── 동기 헬퍼 (CLI용) ──────────────────────


def now_kst_date() -> date:
    """시스템 시각이 KST가 아닐 수 있으니 명시적으로 한국 시간 기준."""
    # 단순화: 시스템 로컬 사용. 환경에 따라 -9h 조정 필요.
    return datetime.now().date()


def _parse_kbo_standings(html: str) -> list[TeamRank]:
    """TeamRankDaily.aspx 테이블 파싱.

    페이지에는 두 종류의 순위표가 있습니다:
      1) 좌측: 전체 순위 (이게 메인)
      2) 우측: 전일 대비 변동 등 보조표
    `<table>` 의 첫 데이터 tbody만 사용합니다.
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="tData")
    if not table:
        # 클래스가 바뀐 경우 첫 번째 데이터성 테이블을 찾음
        for t in soup.find_all("table"):
            if t.find("tbody"):
                table = t
                break
    if table is None:
        return []

    name_to_code = {
        "KIA": "HT", "삼성": "SS", "LG": "LG", "두산": "OB", "SSG": "SK",
        "롯데": "LT", "KT": "KT", "키움": "WO", "한화": "HH", "NC": "NC",
    }

    ranks: list[TeamRank] = []
    rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")[1:]
    for tr in rows:
        cells = [c.get_text(strip=True) for c in tr.find_all("td")]
        if len(cells) < 11:
            continue
        try:
            rank = int(cells[0])
            name = cells[1]
            games = int(cells[2])
            wins = int(cells[3])
            losses = int(cells[4])
            draws = int(cells[5])
            wr = float(cells[6])
            gb_raw = cells[7].replace("-", "0").strip() or "0"
            gb = float(gb_raw)
            recent10 = cells[8]
            streak = cells[9]
        except (ValueError, IndexError):
            continue
        ranks.append(TeamRank(
            rank=rank,
            team_code=name_to_code.get(name, name),
            team_name=name,
            games=games,
            wins=wins,
            losses=losses,
            draws=draws,
            win_rate=wr,
            games_behind=gb,
            recent10=recent10,
            streak=streak,
        ))
        if len(ranks) >= 10:
            break
    return ranks
