"""실시간 KBO 중계 TUI (Textual).

데이터 가져오기 전략:
- relay (스코어, 카운트, 주자, 문자중계): 짧은 주기 폴링 (기본 2초)
- schedule + record (게임 메타, 박스스코어): 긴 주기 폴링 (기본 60초)
- 두 워커가 백그라운드에서 캐시를 갱신하면 UI는 0.5초 주기로 캐시만 다시 렌더한다.

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
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static

from .api import KBOClient
from .data.teams import colored
from .formatters import scoreboard, text_relay_lines
from .models import Game


class ScoreboardWidget(Static):
    pass


class RelayWidget(Static):
    pass


class SidePanelWidget(Static):
    pass


class LiveBroadcastApp(App):
    CSS = """
    Screen { layout: vertical; }
    #top { height: 60%; }
    #scoreboard {
        width: 70%; height: 100%;
        border: round cyan;
        padding: 0 1;
    }
    #side {
        width: 30%; height: 100%;
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

    def __init__(
        self,
        game_id: str,
        poll_relay: float = 2.0,
        poll_meta: float = 60.0,
        render_interval: float = 0.5,
    ) -> None:
        super().__init__()
        self.game_id = game_id
        self.poll_relay = poll_relay
        self.poll_meta = poll_meta
        self.render_interval = render_interval
        self.client: KBOClient | None = None
        self._relay: dict[str, Any] = {}
        self._game: Game | None = None
        self._record: dict[str, Any] = {}
        self._error: str | None = None
        self._dirty: bool = True

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

        # 초기 fetch는 동기 대기해서 첫 화면이 비지 않게 한다.
        await self._fetch_meta()
        await self._fetch_relay()
        self._render()

        # 백그라운드 워커: relay (짧은 주기), meta (긴 주기), render (UI 새로고침)
        self.set_interval(self.poll_relay, self._fetch_relay)
        self.set_interval(self.poll_meta, self._fetch_meta)
        self.set_interval(self.render_interval, self._render)

    async def on_unmount(self) -> None:
        if self.client:
            await self.client.aclose()

    async def action_refresh(self) -> None:
        # 사용자가 'r'을 누르면 둘 다 즉시 다시 가져온다.
        await asyncio.gather(self._fetch_relay(), self._fetch_meta())
        self._render()

    # ───────────────────── fetch ─────────────────────

    async def _fetch_relay(self) -> None:
        if self.client is None:
            return
        try:
            data = await self.client.relay(self.game_id)
            if data:
                self._relay = data
                self._error = None
                self._dirty = True
        except Exception as e:
            self._error = f"relay 조회 실패: {e}"
            self._dirty = True

    async def _fetch_meta(self) -> None:
        if self.client is None:
            return
        try:
            day = datetime.strptime(self.game_id[:8], "%Y%m%d").date()
            games = await self.client.schedule(day)
            self._game = next((g for g in games if g.game_id == self.game_id), None)
            self._dirty = True
        except Exception:
            pass
        try:
            self._record = await self.client.record(self.game_id) or {}
        except Exception:
            self._record = {}

    # ───────────────────── render ─────────────────────

    def _render(self) -> None:
        if not self._dirty:
            return
        self._dirty = False

        if self._error and not self._relay:
            self.query_one("#relay", RelayWidget).update(f"[red]{self._error}[/]")
            return

        if self._game:
            self.query_one("#scoreboard", ScoreboardWidget).update(
                scoreboard(self._game, self._relay)
            )
        self.query_one("#side", SidePanelWidget).update(self._side_panel(self._relay))
        self.query_one("#relay", RelayWidget).update(
            text_relay_lines(self._relay, limit=30)
        )

    def _side_panel(self, relay: dict[str, Any]):
        """현재 타자 정보 + 선공/후공 표시."""
        from rich.console import Group
        from rich.panel import Panel

        hoa = str(relay.get("homeOrAway", "-"))
        offense_label = "선공 (원정)" if hoa == "0" else "후공 (홈)"
        inn = relay.get("inn", "-")

        batter_name = "-"
        batter_avg = "-"
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

        poll_info = Text.from_markup(
            f"[dim]폴링 {self.poll_relay:.1f}s · 메타 {self.poll_meta:.0f}s[/]"
        )

        body = Text.from_markup(
            f"[bold]{inn}회[/]  [yellow]{offense_label}[/]\n\n"
            f"[bold]현재 타자[/]\n  {batter_name}  ({batter_avg})\n\n"
            f"[bold]상대 전적[/]\n  {career}\n"
        )
        return Panel(
            Group(matchup, Text(""), body, Text(""), poll_info),
            title="[bold magenta]경기 정보[/]",
            border_style="magenta",
        )
