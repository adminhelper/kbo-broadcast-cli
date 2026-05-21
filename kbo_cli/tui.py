"""실시간 KBO 중계 TUI (Textual).

레이아웃 (네이버 라이브 페이지 차용):
  ┌──────────┬─────────────────────┬──────────┐
  │ ScoreBox │     FIELD (다이아  │  OnDeck   │
  │ + count  │   몬드 + 수비 9명) │  (대기    │
  │ + 투구수 │     + 현재 타자     │  타석)    │
  ├──────────┴─────────────────────┴──────────┤
  │  Pitcher Card │  Batter Card               │
  ├───────────────────────────────────────────┤
  │  Relay (문자중계, slim)                    │
  └───────────────────────────────────────────┘

데이터:
- relay (스코어/카운트/주자/문자중계): 짧은 주기 (기본 2초)
- schedule + record (게임 메타, 박스스코어): 긴 주기 (기본 60초)
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from rich.align import Align
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from .api import KBOClient
from .data.teams import colored, team as _team_meta
from .formatters import text_relay_lines
from .models import Game


# 포지션 이름 매핑 — relay.Lineup.batter[].posName 한국어 -> 짧은 라벨
POS_LABELS = {
    "투수": "투수", "포수": "포수",
    "1루수": "1루", "2루수": "2루", "3루수": "3루",
    "유격수": "유격", "좌익수": "좌익", "중견수": "중견", "우익수": "우익",
    "지명타자": "지명",
}


class ScoreBoxWidget(Static): pass
class FieldWidget(Static): pass
class OnDeckWidget(Static): pass
class PitcherCardWidget(Static): pass
class BatterCardWidget(Static): pass
class RelayWidget(Static): pass


class LiveBroadcastApp(App):
    CSS = """
    Screen { layout: vertical; }

    #top { height: 55%; }
    #scorebox  { width: 18%; height: 100%; border: round red; padding: 0 1; }
    #field     { width: 54%; height: 100%; border: round green; padding: 1 2; }
    #ondeck    { width: 28%; height: 100%; border: round white; padding: 0 1; }

    #cards { height: 8; }
    #pitcher-card { width: 50%; height: 100%; border: round cyan; padding: 0 1; }
    #batter-card  { width: 50%; height: 100%; border: round yellow; padding: 0 1; }

    #relay {
        height: 1fr;
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
            yield ScoreBoxWidget("[dim]로딩…[/]", id="scorebox")
            yield FieldWidget("[dim]필드 로딩…[/]", id="field")
            yield OnDeckWidget("[dim]대기타석…[/]", id="ondeck")
        with Horizontal(id="cards"):
            yield PitcherCardWidget("[dim]투수 로딩…[/]", id="pitcher-card")
            yield BatterCardWidget("[dim]타자 로딩…[/]", id="batter-card")
        yield RelayWidget("[dim]문자중계 로딩…[/]", id="relay")
        yield Footer()

    async def on_mount(self) -> None:
        self.client = KBOClient()
        self.title = f"KBO 라이브 · {self.game_id}"
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
        self.query_one("#scorebox", ScoreBoxWidget).update(self._scorebox_panel())
        self.query_one("#field", FieldWidget).update(self._field_panel())
        self.query_one("#ondeck", OnDeckWidget).update(self._ondeck_panel())
        self.query_one("#pitcher-card", PitcherCardWidget).update(self._pitcher_card())
        self.query_one("#batter-card", BatterCardWidget).update(self._batter_card())
        self.query_one("#relay", RelayWidget).update(text_relay_lines(self._relay, limit=30))

    # ───────────────────── panels ─────────────────────

    def _scorebox_panel(self) -> Panel:
        """좌측: 양 팀 점수 + 이닝 + B/S/O + 투구수."""
        relay = self._relay
        cgs = relay.get("currentGameState") or {}
        inn = relay.get("inn", "-")
        hoa = str(relay.get("homeOrAway", "-"))
        side_label = "초" if hoa == "0" else "말"
        away_code = self._game.away_team_code if self._game else "원정"
        home_code = self._game.home_team_code if self._game else "홈"
        away_score = cgs.get("awayScore", "0")
        home_score = cgs.get("homeScore", "0")

        # 점수 표
        score_tbl = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        score_tbl.add_column(justify="left", no_wrap=True)
        score_tbl.add_column(justify="right", no_wrap=True, style="bold")
        score_tbl.add_row(colored(away_code, _team_meta(away_code)["name"]), str(away_score))
        score_tbl.add_row(colored(home_code, _team_meta(home_code)["name"]), str(home_score))

        # 이닝 / 카운트
        ball = int(cgs.get("ball", 0) or 0)
        strike = int(cgs.get("strike", 0) or 0)
        out = int(cgs.get("out", 0) or 0)
        bso = (
            f"[bold]B[/] {'●' * ball}{'○' * (3 - ball)}\n"
            f"[bold]S[/] {'●' * strike}{'○' * (2 - strike)}\n"
            f"[bold]O[/] {'●' * out}{'○' * (2 - out)}"
        )

        # 현재 투수 + 투구수
        pitcher_row = self._find_lineup_row(cgs.get("pitcher"), "pitcher",
                                            defense_side=True)
        pitcher_line = (
            f"\n[dim]현재 투수[/]\n[bold]{pitcher_row.get('name', '-')}[/]\n"
            f"[dim]투구수[/] [bold]{pitcher_row.get('ballCount', '-')}[/]"
        )

        body = Group(
            score_tbl,
            Text(""),
            Align.center(Text.from_markup(f"[bold]{inn}회 {side_label}[/]")),
            Text(""),
            Text.from_markup(bso),
            Text.from_markup(pitcher_line),
        )
        return Panel(body, title="[bold]SCORE[/]", border_style="red")

    def _field_panel(self) -> Panel:
        """중앙: 다이아몬드 + 수비 9명 + 현재 타자."""
        relay = self._relay
        cgs = relay.get("currentGameState") or {}
        hoa = str(relay.get("homeOrAway", "-"))
        offense_side = "home" if hoa == "1" else "away"
        defense_side = "away" if hoa == "1" else "home"

        # 수비 측 야수 매핑 (포지션 → 이름)
        defense_lineup = (relay.get(f"{defense_side}Lineup") or {}).get("batter") or []
        pos_to_name: dict[str, str] = {}
        for b in defense_lineup:
            pos = b.get("posName")
            if pos and pos not in pos_to_name:
                pos_to_name[pos] = b.get("name", "-")

        # 현재 투수 (defense)
        pitcher_row = self._find_lineup_row(cgs.get("pitcher"), "pitcher",
                                            defense_side=True)
        pos_to_name.setdefault("투수", pitcher_row.get("name", "-"))

        # 현재 타자 (offense)
        batter_row = self._find_lineup_row(cgs.get("batter"), "batter",
                                            defense_side=False)
        batter_name = batter_row.get("name", "-")
        batter_order = batter_row.get("batOrder", "?")

        # 주자 표시
        on1 = str(cgs.get("base1", "0")) not in {"0", "", "None"}
        on2 = str(cgs.get("base2", "0")) not in {"0", "", "None"}
        on3 = str(cgs.get("base3", "0")) not in {"0", "", "None"}

        runner = lambda on: "[bold yellow]◆[/]" if on else "[dim]◇[/]"

        def fielder(pos: str) -> str:
            name = pos_to_name.get(pos)
            if not name:
                return f"[dim]{POS_LABELS.get(pos, pos)}[/]"
            return f"[bold]{name}[/]\n[dim]{POS_LABELS.get(pos, pos)}[/]"

        # 외야 (좌/중/우)
        out_tbl = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        out_tbl.add_column(justify="center"); out_tbl.add_column(justify="center"); out_tbl.add_column(justify="center")
        out_tbl.add_row(fielder("좌익수"), fielder("중견수"), fielder("우익수"))

        # 내야 (3-유격-2-1) — 4셀
        infield = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        for _ in range(4): infield.add_column(justify="center")
        infield.add_row(fielder("3루수"), fielder("유격수"), fielder("2루수"), fielder("1루수"))

        # 다이아몬드 (주자 표시) — 2루 / 3루+1루 / 홈
        diamond_lines = (
            f"          {runner(on2)}\n"
            f"   {runner(on3)}        {runner(on1)}\n"
            f"          [dim]◇[/]"
        )

        # 배터리 (투수 / 포수)
        battery_tbl = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        battery_tbl.add_column(justify="center")
        battery_tbl.add_row(fielder("투수"))
        battery_tbl.add_row(fielder("포수"))

        # 현재 타석
        bat_label = (
            f"[bold yellow]▶ {batter_order}번 {batter_name}[/]\n"
            f"[dim]타석[/]"
        )

        body = Group(
            out_tbl,
            Text(""),
            infield,
            Text(""),
            Align.center(Text.from_markup(diamond_lines)),
            Text(""),
            battery_tbl,
            Text(""),
            Align.center(Text.from_markup(bat_label)),
        )
        return Panel(body, title="[bold green]FIELD[/]", border_style="green")

    def _ondeck_panel(self) -> Panel:
        """우측: 대기 타석 (현재 타자 다음 3명) + 양팀 라인업 요약."""
        relay = self._relay
        cgs = relay.get("currentGameState") or {}
        hoa = str(relay.get("homeOrAway", "-"))
        offense_side = "home" if hoa == "1" else "away"
        offense_lineup = (relay.get(f"{offense_side}Lineup") or {}).get("batter") or []

        # 현재 타자 인덱스 찾고 다음 3명
        cur_batter_pcode = str(cgs.get("batter") or "")
        cur_idx = None
        for i, b in enumerate(offense_lineup):
            if str(b.get("pcode") or "") == cur_batter_pcode:
                cur_idx = i
                break

        on_deck: list = []
        if cur_idx is not None and offense_lineup:
            for n in range(1, 4):
                nxt = offense_lineup[(cur_idx + n) % len(offense_lineup)]
                on_deck.append(nxt)
        else:
            on_deck = offense_lineup[:3]

        on_deck_tbl = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        on_deck_tbl.add_column(width=2, no_wrap=True, style="dim")
        on_deck_tbl.add_column(no_wrap=True)
        on_deck_tbl.add_column(style="dim", no_wrap=True)
        for n, b in enumerate(on_deck, start=1):
            avg = b.get("seasonHra")
            avg_s = f"{avg:.3f}" if isinstance(avg, (int, float)) else (avg or "-")
            on_deck_tbl.add_row(
                f"{n}번",
                f"{b.get('batOrder', '?')}타순 {b.get('name', '-')}",
                avg_s,
            )

        # 양팀 짧은 시즌 요약
        away_lineup = (relay.get("awayLineup") or {}).get("batter") or []
        home_lineup = (relay.get("homeLineup") or {}).get("batter") or []
        away_code = self._game.away_team_code if self._game else "원정"
        home_code = self._game.home_team_code if self._game else "홈"

        summary_tbl = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        summary_tbl.add_column(no_wrap=True)
        summary_tbl.add_column(no_wrap=True, style="dim", justify="right")
        for code, lineup in [(away_code, away_lineup), (home_code, home_lineup)]:
            avgs = [b.get("seasonHra") for b in lineup
                    if isinstance(b.get("seasonHra"), (int, float))]
            team_avg = sum(avgs) / len(avgs) if avgs else 0
            summary_tbl.add_row(colored(code, _team_meta(code)["name"]), f"평균 {team_avg:.3f}")

        body = Group(
            Text.from_markup("[bold]대기 타석[/]"),
            on_deck_tbl,
            Text(""),
            Text.from_markup("[bold]팀 타격[/]"),
            summary_tbl,
        )
        return Panel(body, title="[bold]ON DECK[/]", border_style="white")

    def _pitcher_card(self) -> Panel:
        """투수 카드: 이름, 시즌 ERA, 오늘 투구 기록."""
        relay = self._relay
        cgs = relay.get("currentGameState") or {}
        p = self._find_lineup_row(cgs.get("pitcher"), "pitcher", defense_side=True)
        if not p:
            return Panel("[dim]투수 정보 없음[/]", title="[bold cyan]투수[/]", border_style="cyan")

        defense_code = (
            self._game.away_team_code if str(relay.get("homeOrAway")) == "1"
            else self._game.home_team_code
        ) if self._game else "-"
        team = colored(defense_code, _team_meta(defense_code)["name"])
        head = Text.from_markup(
            f"{team}  [bold]{p.get('name', '-')}[/]  "
            f"[dim]시즌 ERA[/] [bold]{p.get('seasonEra', '-')}[/]"
        )
        stats = Text.from_markup(
            f"[dim]투구[/] {p.get('ballCount', '-')}  "
            f"[dim]이닝[/] {p.get('inn', '-')}  "
            f"[dim]탈삼진[/] {p.get('kk', '-')}  "
            f"[dim]볼넷[/] {p.get('bb', '-')}  "
            f"[dim]실점[/] {p.get('run', '-')}  "
            f"[dim]자책[/] {p.get('er', '-')}  "
            f"[dim]피안타[/] {p.get('hit', '-')}"
        )
        return Panel(Group(head, stats),
                     title="[bold cyan]현재 투수[/]", border_style="cyan")

    def _batter_card(self) -> Panel:
        """타자 카드: 이름, 시즌 타율, 오늘 기록 + 상대 전적."""
        relay = self._relay
        cgs = relay.get("currentGameState") or {}
        b = self._find_lineup_row(cgs.get("batter"), "batter", defense_side=False)
        if not b:
            return Panel("[dim]타자 정보 없음[/]", title="[bold yellow]타자[/]", border_style="yellow")

        offense_code = (
            self._game.home_team_code if str(relay.get("homeOrAway")) == "1"
            else self._game.away_team_code
        ) if self._game else "-"
        team = colored(offense_code, _team_meta(offense_code)["name"])
        avg = b.get("seasonHra")
        avg_s = f"{avg:.3f}" if isinstance(avg, (int, float)) else (avg or "-")
        head = Text.from_markup(
            f"{team}  [bold yellow]▶ {b.get('batOrder', '?')}번 {b.get('name', '-')}[/]  "
            f"[dim]시즌 타율[/] [bold]{avg_s}[/]"
        )
        stats = Text.from_markup(
            f"[dim]타석[/] {b.get('pa', '-')}  "
            f"[dim]타수[/] {b.get('ab', '-')}  "
            f"[dim]안타[/] {b.get('hit', '-')}  "
            f"[dim]득점[/] {b.get('run', '-')}  "
            f"[dim]타점[/] {b.get('rbi', '-')}  "
            f"[dim]홈런[/] {b.get('hr', '-')}  "
            f"[dim]볼넷[/] {b.get('bb', '-')}  "
            f"[dim]삼진[/] {b.get('kk', '-')}"
        )
        career = relay.get("pitcherVsBatterCareerStats") or "첫 맞대결"
        vs = Text.from_markup(f"[dim]상대 전적:[/] {career}")
        return Panel(Group(head, stats, vs),
                     title="[bold yellow]현재 타자[/]", border_style="yellow")

    # ───────────────────── lookup ─────────────────────

    def _find_lineup_row(self, pcode: str | None, role: str,
                         defense_side: bool) -> dict:
        """homeLineup/awayLineup 의 batter/pitcher 리스트에서 pcode 매칭.

        defense_side=True 면 수비측(반대 측), False 면 공격측(homeOrAway 측).
        """
        if not pcode:
            return {}
        hoa = str(self._relay.get("homeOrAway", "-"))
        offense = "home" if hoa == "1" else "away"
        side = ("away" if offense == "home" else "home") if defense_side else offense
        lineup = (self._relay.get(f"{side}Lineup") or {}).get(role) or []
        target = str(pcode)
        for item in lineup:
            if str(item.get("pcode") or "") == target:
                return item
        return {}
