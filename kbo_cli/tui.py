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
        """좌측: 양팀 타자 라인업 (현재 타자 pcode 매칭으로 강조).

        데이터 소스: relay.awayLineup / relay.homeLineup
          - batOrder, name, posName, pcode
          - seasonHra (시즌 타율), ab, hit, run, rbi, hr, bb, kk (오늘 기록)
        """
        relay = self._relay
        hoa = str(relay.get("homeOrAway", "-"))
        cgs = relay.get("currentGameState") or {}
        cur_batter_pcode = str(cgs.get("batter") or "")
        offense_side = "home" if hoa == "1" else "away"

        away_batters = (relay.get("awayLineup") or {}).get("batter") or []
        home_batters = (relay.get("homeLineup") or {}).get("batter") or []

        away_code = self._game.away_team_code if self._game else None
        home_code = self._game.home_team_code if self._game else None

        groups: list = []
        for side, label, batters, code in [
            ("away", "원정 (선공)", away_batters, away_code),
            ("home", "홈 (후공)", home_batters, home_code),
        ]:
            t = Table(show_header=False, box=None, padding=(0, 0), expand=True)
            t.add_column(width=2, no_wrap=True)          # 타순/마커
            t.add_column(no_wrap=True)                   # 이름
            t.add_column(style="dim", no_wrap=True)      # 시즌 타율
            t.add_column(style="dim", no_wrap=True)      # 오늘 H-AB
            for b in batters[:9]:
                pcode = str(b.get("pcode") or "")
                is_current = (
                    side == offense_side
                    and cur_batter_pcode
                    and pcode == cur_batter_pcode
                )
                order = b.get("batOrder", "-")
                marker = "▶" if is_current else str(order)
                name = b.get("name", "-")
                avg = b.get("seasonHra")
                avg_s = f"{avg:.3f}" if isinstance(avg, (int, float)) else (avg or "-")
                ab = b.get("ab", 0)
                hit = b.get("hit", 0)
                today = f"{hit}-{ab}" if ab else "-"
                if is_current:
                    t.add_row(
                        f"[bold yellow]{marker}[/]",
                        f"[bold yellow]{name}[/]",
                        avg_s, today,
                    )
                else:
                    t.add_row(f"[dim]{marker}[/]", name, avg_s, today)
            header = Text.from_markup(f"[bold]{colored(code, label)}[/]")
            groups.append(header)
            groups.append(t)
            groups.append(Text(""))

        return Panel(
            Group(*groups),
            title="[bold blue]라인업 · 시즌타율 · 오늘 H-AB[/]",
            border_style="blue",
        )

    def _footer_panel(self) -> Panel:
        """하단: 현재 타자 / 현재 투수 / 상대 전적 / 폴링 정보."""
        relay = self._relay
        hoa = str(relay.get("homeOrAway", "-"))
        offense_label = "선공 (원정)" if hoa == "0" else "후공 (홈)"
        inn = relay.get("inn", "-")

        cgs = relay.get("currentGameState") or {}
        cur_batter_pcode = str(cgs.get("batter") or "")
        cur_pitcher_pcode = str(cgs.get("pitcher") or "")

        def _find(pcode: str, role: str, side: str) -> dict:
            """{home,away}Lineup.{batter,pitcher} 리스트에서 pcode로 매칭."""
            if not pcode:
                return {}
            lineup = relay.get("homeLineup" if side == "home" else "awayLineup", {}) or {}
            for item in (lineup.get(role) or []):
                if str(item.get("pcode") or "") == pcode:
                    return item
            return {}

        offense_side = "home" if hoa == "1" else "away"
        defense_side = "away" if hoa == "1" else "home"
        batter_row = _find(cur_batter_pcode, "batter", offense_side)
        pitcher_row = _find(cur_pitcher_pcode, "pitcher", defense_side)
        batter_name = batter_row.get("name", f"#{cur_batter_pcode}" if cur_batter_pcode else "-")
        pitcher_name = pitcher_row.get("name", f"#{cur_pitcher_pcode}" if cur_pitcher_pcode else "-")

        # 시즌 + 오늘 기록 보조 문자열
        b_avg = batter_row.get("seasonHra")
        b_avg_s = f"{b_avg:.3f}" if isinstance(b_avg, (int, float)) else (b_avg or "-")
        b_today = f"{batter_row.get('hit', 0)}-{batter_row.get('ab', 0)}" if batter_row else ""
        p_era = pitcher_row.get("seasonEra") or "-"
        p_inn = pitcher_row.get("inn") or "-"

        career = relay.get("pitcherVsBatterCareerStats") or "-"

        # 카운트 한 줄 + 점수
        ball = cgs.get("ball", "-")
        strike = cgs.get("strike", "-")
        out = cgs.get("out", "-")
        away_score = cgs.get("awayScore", "-")
        home_score = cgs.get("homeScore", "-")

        line1 = Text.from_markup(
            f"[bold]{inn}회 {'초' if hoa == '0' else '말'}[/]  "
            f"[yellow]{offense_label}[/]   "
            f"[bold]{away_score}[/] : [bold]{home_score}[/]   "
            f"B [yellow]{ball}[/]  S [red]{strike}[/]  O [white]{out}[/]"
        )
        line2 = Text.from_markup(
            f"[dim]투수[/] [bold]{pitcher_name}[/] [dim](ERA {p_era}, {p_inn}이닝)[/]   →   "
            f"[dim]타자[/] [bold yellow]{batter_name}[/] "
            f"[dim](시즌 {b_avg_s}, 오늘 {b_today})[/]"
        )
        line3 = Text.from_markup(
            f"[dim]상대 전적:[/] {career}    "
            f"[dim]폴링 {self.poll_relay:.1f}s · "
            f"[bold]q[/] 종료, [bold]r[/] 즉시 새로고침[/]"
        )

        return Panel(
            Group(line1, line2, line3),
            title="[bold magenta]경기 상황[/]",
            border_style="magenta",
        )
