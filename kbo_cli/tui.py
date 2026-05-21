"""실시간 KBO 중계 TUI (Textual).

데이터 가져오기:
- relay (스코어/카운트/주자/문자중계): 짧은 주기 (기본 2초)
- schedule + record (게임 메타, 박스스코어): 긴 주기 (기본 60초)
- 두 워커가 백그라운드에서 캐시를 채우고, UI는 0.5초마다 캐시를 다시 렌더한다.

레이아웃 (티빙 느낌, 3 column):
  ┌──────────┬────────────────────────┬──────────┐
  │  LINEUP  │      SCOREBOARD        │   RELAY  │
  │  (양팀   │  + 이닝 그리드          │  (문자   │
  │  라인업) │  + 다이아몬드/카운트     │  중계)   │
  │          │                        │          │
  └──────────┴────────────────────────┴──────────┘
  ┌─────────────────────────────────────────────┐
  │  FOOTER: 현재 투수 vs 타자, 상대전적          │
  └─────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static

from .api import KBOClient
from .data.teams import colored, team
from .formatters import scoreboard, text_relay_lines
from .models import Game


class LineupWidget(Static):
    pass


class ScoreboardWidget(Static):
    pass


class RelayWidget(Static):
    pass


class FooterPanelWidget(Static):
    pass


class LiveBroadcastApp(App):
    CSS = """
    Screen { layout: vertical; }

    #top { height: 1fr; }

    #lineup {
        width: 22%; height: 100%;
        border: round blue;
        padding: 0 1;
    }
    #scoreboard {
        width: 48%; height: 100%;
        border: round cyan;
        padding: 0 1;
    }
    #relay {
        width: 30%; height: 100%;
        border: round yellow;
        padding: 0 1;
    }
    #footer-panel {
        height: 5;
        border: round magenta;
        padding: 0 1;
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
            yield LineupWidget("[dim]라인업 로딩 중...[/]", id="lineup")
            yield ScoreboardWidget("[dim]스코어 로딩 중...[/]", id="scoreboard")
            yield RelayWidget("[dim]문자중계 로딩 중...[/]", id="relay")
        yield FooterPanelWidget("[dim]경기 정보 로딩 중...[/]", id="footer-panel")
        yield Footer()

    async def on_mount(self) -> None:
        self.client = KBOClient()
        self.title = f"KBO 라이브 - {self.game_id}"

        await self._fetch_meta()
        await self._fetch_relay()
        self._render()

        self.set_interval(self.poll_relay, self._fetch_relay)
        self.set_interval(self.poll_meta, self._fetch_meta)
        self.set_interval(self.render_interval, self._render)

    async def on_unmount(self) -> None:
        if self.client:
            await self.client.aclose()

    async def action_refresh(self) -> None:
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
        self.query_one("#lineup", LineupWidget).update(self._lineup_panel())
        self.query_one("#relay", RelayWidget).update(
            text_relay_lines(self._relay, limit=40)
        )
        self.query_one("#footer-panel", FooterPanelWidget).update(self._footer_panel())

    # ───────────────────── panels ─────────────────────

    def _lineup_panel(self) -> Panel:
        """좌측: 양팀 타자 라인업 (현재 타자 강조)."""
        relay = self._relay
        hoa = str(relay.get("homeOrAway", "-"))
        cur_idx = relay.get("homeBatOrder" if hoa == "1" else "awayBatOrder")
        cur_idx_int = int(cur_idx) if str(cur_idx).isdigit() else 0
        offense_side = "home" if hoa == "1" else "away"

        away_entry = (relay.get("awayEntry") or {}).get("batter") or []
        home_entry = (relay.get("homeEntry") or {}).get("batter") or []

        away_code = self._game.away_team_code if self._game else None
        home_code = self._game.home_team_code if self._game else None

        groups: list = []
        for side, label, batters, code in [
            ("away", "원정 (선공)", away_entry, away_code),
            ("home", "홈 (후공)", home_entry, home_code),
        ]:
            t = Table(show_header=False, box=None, padding=(0, 0), expand=True)
            t.add_column(width=2, no_wrap=True)
            t.add_column(no_wrap=True)
            t.add_column(style="dim", no_wrap=True)
            for i, b in enumerate(batters[:9], start=1):
                marker = ""
                style = ""
                if side == offense_side and i == cur_idx_int:
                    marker = "▶"
                    style = "bold yellow"
                name = b.get("name", "-")
                pos = b.get("pos", "")
                row = [
                    f"[{style}]{marker or i}[/]" if marker else f"[dim]{i}[/]",
                    f"[{style}]{name}[/]" if style else name,
                    pos,
                ]
                t.add_row(*row)
            header = Text.from_markup(f"[bold]{colored(code, label)}[/]")
            groups.append(header)
            groups.append(t)
            groups.append(Text(""))

        return Panel(
            Group(*groups),
            title="[bold bright_blue]라인업[/]",
            border_style="bright_blue",
        )

    def _footer_panel(self) -> Panel:
        """하단: 현재 타자 / 현재 투수 / 상대 전적 / 폴링 정보."""
        relay = self._relay
        hoa = str(relay.get("homeOrAway", "-"))
        offense_label = "선공 (원정)" if hoa == "0" else "후공 (홈)"
        inn = relay.get("inn", "-")

        # 현재 타자
        batter_name, batter_pcode = "-", None
        try:
            entry = relay.get("homeEntry" if hoa == "1" else "awayEntry", {}) or {}
            batters = entry.get("batter") or []
            cur_idx = relay.get("homeBatOrder" if hoa == "1" else "awayBatOrder")
            if cur_idx and batters:
                idx = int(cur_idx) - 1
                if 0 <= idx < len(batters):
                    b = batters[idx]
                    batter_name = b.get("name", "-")
                    batter_pcode = b.get("pcode")
        except (KeyError, IndexError, ValueError, TypeError):
            pass

        # 현재 투수 (defense side)
        pitcher_name = "-"
        try:
            defense = "awayEntry" if hoa == "1" else "homeEntry"
            entry = relay.get(defense, {}) or {}
            pitchers = entry.get("pitcher") or []
            if pitchers:
                pitcher_name = pitchers[-1].get("name", "-")
        except (KeyError, IndexError, TypeError):
            pass

        career = relay.get("pitcherVsBatterCareerStats") or "-"

        line1 = Text.from_markup(
            f"[bold]{inn}회[/]  [yellow]{offense_label}[/]   "
            f"[dim]투수[/] {pitcher_name}  →  "
            f"[dim]타자[/] [bold]{batter_name}[/]"
            f"{f' [dim](pcode {batter_pcode})[/]' if batter_pcode else ''}"
        )
        line2 = Text.from_markup(f"[dim]상대 전적:[/] {career}")
        line3 = Text.from_markup(
            f"[dim]폴링 {self.poll_relay:.1f}s · 메타 {self.poll_meta:.0f}s · "
            f"[bold]q[/] 종료, [bold]r[/] 즉시 새로고침[/]"
        )

        return Panel(
            Group(line1, line2, line3),
            title="[bold magenta]경기 상황[/]",
            border_style="magenta",
        )
