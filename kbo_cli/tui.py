"""실시간 KBO 중계 TUI (Textual).

레이아웃:
  ┌─────────────────────────────┬──────────────────┐
  │       SCOREBOARD            │   SIDE: 선수정보  │
  ├─────────────────────────────┤   (예: 현재 타자) │
  │       문자중계 (스트림)        │                  │
  └─────────────────────────────┴──────────────────┘
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from .api import KBOClient
from .data.teams import colored, team
from .formatters import scoreboard, text_relay_lines
from .models import Game

POLL_SECONDS = 5.0


class ScoreboardWidget(Static):
    pass


class RelayWidget(Static):
    pass


class SidePanelWidget(Static):
    pass


class LiveBroadcastApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #top {
        height: 60%;
    }
    #scoreboard {
        width: 70%;
        height: 100%;
        border: round cyan;
        padding: 0 1;
    }
    #side {
        width: 30%;
        height: 100%;
        border: round magenta;
        padding: 0 1;
    }
    #relay {
        height: 40%;
        border: round yellow;
        padding: 0 1;
        overflow-y: scroll;
    }
    """

    BINDINGS = [
        ("q", "quit", "종료"),
        ("r", "refresh", "새로고침"),
    ]

    def __init__(self, game_id: str) -> None:
        super().__init__()
        self.game_id = game_id
        self.client: KBOClient | None = None
        self._poll_task: asyncio.Task | None = None
        self._last_relay: dict[str, Any] = {}
        self._game: Game | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="top"):
            yield ScoreboardWidget("로딩 중...", id="scoreboard")
            yield SidePanelWidget("로딩 중...", id="side")
        yield RelayWidget("[dim]문자중계 로딩 중...[/]", id="relay")
        yield Footer()

    async def on_mount(self) -> None:
        self.client = KBOClient()
        self.title = f"KBO 라이브 - {self.game_id}"
        await self._refresh()
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def on_unmount(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
        if self.client:
            await self.client.aclose()

    async def _poll_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(POLL_SECONDS)
                await self._refresh()
        except asyncio.CancelledError:
            pass

    async def action_refresh(self) -> None:
        await self._refresh()

    async def _refresh(self) -> None:
        assert self.client is not None
        # 게임 메타는 한 번만, 이후 status 갱신용으로만 가끔
        try:
            from datetime import datetime as _dt
            day = _dt.strptime(self.game_id[:8], "%Y%m%d").date()
            games = await self.client.schedule(day)
            self._game = next((g for g in games if g.game_id == self.game_id), None)
        except Exception:
            pass

        try:
            relay = await self.client.relay(self.game_id)
            self._last_relay = relay
        except Exception as e:
            self.query_one("#relay", RelayWidget).update(f"[red]문자중계 조회 실패: {e}[/]")
            return

        # 스코어보드 갱신
        if self._game:
            self.query_one("#scoreboard", ScoreboardWidget).update(scoreboard(self._game, relay))
        # 사이드 패널: 현재 타자 정보
        self.query_one("#side", SidePanelWidget).update(self._side_panel(relay))
        # 문자중계
        self.query_one("#relay", RelayWidget).update(text_relay_lines(relay, limit=30))

    def _side_panel(self, relay: dict[str, Any]):
        """현재 타자 정보 + 선공/후공 표시."""
        from rich.console import Group
        from rich.panel import Panel

        hoa = str(relay.get("homeOrAway", "-"))
        offense_label = "선공 (원정)" if hoa == "0" else "후공 (홈)"
        inn = relay.get("inn", "-")

        batter_name = "-"
        batter_avg = "-"
        # 현재 타자: homeEntry.batter 또는 awayEntry.batter 가운데 현재 타순 사람
        try:
            entry = relay.get("homeEntry" if hoa == "1" else "awayEntry", {}) or {}
            batters = entry.get("batter") or []
            cur_idx = relay.get("homeBatOrder" if hoa == "1" else "awayBatOrder")
            if cur_idx and batters:
                b = batters[int(cur_idx) - 1] if int(cur_idx) - 1 < len(batters) else batters[0]
                batter_name = b.get("name", "-")
                batter_avg = b.get("hra") or b.get("hraRate") or "-"
            elif batters:
                batter_name = batters[0].get("name", "-")
        except (KeyError, IndexError, ValueError, TypeError):
            pass

        career = relay.get("pitcherVsBatterCareerStats") or "-"

        if self._game:
            away = colored(self._game.away_team_code, self._game.away_team_name)
            home = colored(self._game.home_team_code, self._game.home_team_name)
            matchup = Text.from_markup(f"{away}  vs  {home}")
        else:
            matchup = Text("-")

        body = Text.from_markup(
            f"[bold]{inn}회[/]  [yellow]{offense_label}[/]\n\n"
            f"[bold]현재 타자[/]\n  {batter_name}  ({batter_avg})\n\n"
            f"[bold]상대 전적[/]\n  {career}\n"
        )
        return Panel(
            Group(matchup, Text(""), body),
            title="[bold magenta]경기 정보[/]",
            border_style="magenta",
        )
