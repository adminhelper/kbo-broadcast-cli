"""네이버 스포츠 응답 → 도메인 모델 매핑.

네이버 내부 API는 비공식이라 스키마가 자주 바뀝니다.
필드는 모두 Optional이며, 누락 시 None 또는 빈 값으로 채워집니다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Game(BaseModel):
    """스케줄 API의 game 항목."""

    model_config = ConfigDict(extra="ignore")

    game_id: str = Field(alias="gameId")
    category_id: str | None = Field(default=None, alias="categoryId")
    category_name: str | None = Field(default=None, alias="categoryName")
    game_date: str | None = Field(default=None, alias="gameDate")
    game_date_time: str | None = Field(default=None, alias="gameDateTime")
    stadium: str | None = ""
    title: str | None = None
    home_team_code: str | None = Field(default=None, alias="homeTeamCode")
    home_team_name: str | None = Field(default=None, alias="homeTeamName")
    home_team_score: int | None = Field(default=0, alias="homeTeamScore")
    away_team_code: str | None = Field(default=None, alias="awayTeamCode")
    away_team_name: str | None = Field(default=None, alias="awayTeamName")
    away_team_score: int | None = Field(default=0, alias="awayTeamScore")
    winner: str | None = "DRAW"  # "HOME" | "AWAY" | "DRAW"
    status_code: str | None = Field(default=None, alias="statusCode")  # BEFORE/STARTED/RESULT/CANCEL
    status_info: str | None = Field(default="", alias="statusInfo")
    cancel: bool | None = False
    suspended: bool | None = False
    has_video: bool | None = Field(default=False, alias="hasVideo")
    reversed_home_away: bool | None = Field(default=False, alias="reversedHomeAway")
    home_starter_name: str | None = Field(default=None, alias="homeStarterName")
    away_starter_name: str | None = Field(default=None, alias="awayStarterName")
    broad_channel: str | None = Field(default=None, alias="broadChannel")
    round_name: str | None = Field(default=None, alias="roundName")

    @property
    def start_time(self) -> str:
        if not self.game_date_time:
            return "-"
        try:
            return datetime.fromisoformat(self.game_date_time).strftime("%H:%M")
        except ValueError:
            return self.game_date_time[-8:-3]

    @property
    def is_kbo(self) -> bool:
        return (self.category_id or "").lower() == "kbo"

    @property
    def is_finished(self) -> bool:
        return self.status_code == "RESULT"

    @property
    def is_live(self) -> bool:
        return self.status_code in {"STARTED", "BEFORE"} and not self.cancel and bool(self.game_date_time)

    @property
    def display_status(self) -> str:
        if self.cancel:
            return "취소"
        if self.suspended:
            return "중단"
        if self.status_code == "RESULT":
            return "종료"
        if self.status_code == "STARTED":
            return self.status_info or "진행중"
        if self.status_code == "BEFORE":
            return self.start_time
        return self.status_info or self.status_code or "-"


class TeamRank(BaseModel):
    """KBO 공식 사이트에서 스크래핑한 팀 순위."""

    rank: int
    team_code: str
    team_name: str
    games: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    games_behind: float
    recent10: str  # "7승0무3패"
    streak: str    # "1승" / "2패"


# Relay/Record/Preview 응답은 스키마가 너무 크고 변동이 잦아
# dict[str, Any] 그대로 다루되, formatter 단에서 안전하게 .get() 합니다.
RawDict = dict[str, Any]
