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
class OnDeckWidget(Static): pass
class PitcherCardWidget(Static): pass
class BatterCardWidget(Static): pass
class RelayWidget(Static): pass


class FieldWidget(Static):
    """필드 패널 — render() 시점에 자체 size.width 기반으로 다시 그린다.

    이렇게 하면 tmux 패널을 리사이즈했을 때 Textual 의 SIGWINCH 처리만으로
    바로 새 width 에 맞춰 반응형 layout 이 적용된다.
    """

    def on_resize(self, event) -> None:  # type: ignore[override]
        self.refresh()

    def render(self):  # type: ignore[override]
        app = self.app
        builder = getattr(app, "_field_panel", None)
        if builder is None:
            return Text.from_markup("[dim]필드 로딩…[/]")
        w = self.size.width or 80
        return builder(width=w)


class LiveBroadcastApp(App):
    CSS = """
    Screen { layout: vertical; }

    #top { height: 50%; }
    #scorebox  { width: 18%; height: 100%; border: round red; padding: 0 1; }
    #field     { width: 54%; height: 100%; border: round green; padding: 1 2; }
    #ondeck    { width: 28%; height: 100%; border: round white; padding: 0 1; }

    #cards { height: 6; }
    #pitcher-card { width: 50%; height: 100%; border: round cyan; padding: 0 1; }
    #batter-card  { width: 50%; height: 100%; border: round yellow; padding: 0 1; }

    /* 문자중계 — 충분한 높이 확보 (최소 약 7~8줄 + border) */
    #relay {
        height: 1fr;
        min-height: 9;
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
        sound: bool = True,
        demo: bool = False,
    ) -> None:
        super().__init__()
        self.game_id = game_id
        self.poll_relay = poll_relay
        self.poll_meta = poll_meta
        self.render_interval = render_interval
        self.sound = sound
        self.demo = demo
        self.client = None  # KBOClient | DemoClient | None
        self._relay: dict[str, Any] = {}
        self._game: Game | None = None
        self._record: dict[str, Any] = {}
        self._error: str | None = None
        self._dirty: bool = True
        # 이전 폭 추적 (반응형 강제 재렌더용)
        self._last_widths: dict[str, int] = {}
        # 이전 점수 추적 (알림 트리거)
        self._last_score: tuple[str, str] | None = None
        # 이전 이닝/공격측 추적 (공수 교대 시 TTS 응원가 트리거)
        self._last_inn_half: tuple[Any, str] | None = None
        # 이전 textRelays 의 마지막 이벤트 no — 새 이벤트 중 홈런 감지
        self._last_event_no: int = -1

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
        if self.demo:
            from .demo import DemoClient
            self.client = DemoClient(step_seconds=self.poll_relay)
            self.title = f"KBO 라이브 (DEMO) · {self.game_id}"
        else:
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

    def on_resize(self, event) -> None:  # type: ignore[override]
        # 화면 크기 변화 시 다음 _render 에서 반응형 layout 적용
        self._dirty = True

    # ───────────────────── fetch ─────────────────────

    async def _fetch_relay(self) -> None:
        if self.client is None:
            return
        try:
            data = await self.client.relay(self.game_id)
            if data:
                cgs = data.get("currentGameState") or {}
                away_score = str(cgs.get("awayScore", "0"))
                home_score = str(cgs.get("homeScore", "0"))
                inn = data.get("inn")
                hoa = str(data.get("homeOrAway", "-"))
                half = "초" if hoa == "0" else "말"

                # 공수 교대 감지는 보존 (UI 로직용). TTS 자동 재생은 비활성화.
                self._last_inn_half = (inn, half)

                # ─ 점수 변경 감지 → macOS 알림만 (사운드는 공수 교대 때만) ─
                if self._last_score is not None:
                    prev_a, prev_h = self._last_score
                    scored_team_code = None
                    diff = 0
                    if away_score != prev_a:
                        scored_team_code = self._game.away_team_code if self._game else None
                        try:
                            diff = int(away_score) - int(prev_a)
                        except ValueError:
                            diff = 0
                    elif home_score != prev_h:
                        scored_team_code = self._game.home_team_code if self._game else None
                        try:
                            diff = int(home_score) - int(prev_h)
                        except ValueError:
                            diff = 0
                    if scored_team_code:
                        try:
                            from . import notify as N
                            N.send_notification(
                                f"⚾ {scored_team_code} {diff}점",
                                f"{inn}회 {half}  현재 {away_score} : {home_score}",
                                sound="Glass",
                            )
                        except Exception:
                            pass
                self._last_score = (away_score, home_score)

                # ─ 새 이벤트 중 홈런 감지 → 별도 알림 ─
                events = data.get("textRelays") or []
                new_events = [
                    e for e in events
                    if isinstance(e.get("no"), int) and e["no"] > self._last_event_no
                ]
                if events:
                    self._last_event_no = max(
                        (e.get("no") for e in events if isinstance(e.get("no"), int)),
                        default=self._last_event_no,
                    )
                if self._last_event_no >= 0:
                    self._maybe_homerun(new_events)

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
        # FieldWidget 은 자체 render() 가 size.width 를 보고 그리므로 refresh() 만.
        self.query_one("#field", FieldWidget).refresh()
        self.query_one("#ondeck", OnDeckWidget).update(self._ondeck_panel())
        self.query_one("#pitcher-card", PitcherCardWidget).update(self._pitcher_card())
        self.query_one("#batter-card", BatterCardWidget).update(self._batter_card())
        self.query_one("#relay", RelayWidget).update(text_relay_lines(self._relay, limit=30))

    # ───────────────────── panels ─────────────────────

    def _scorebox_panel(self) -> Panel:
        """좌측: 양 팀 점수 + 이닝 + B/S/O 진행 막대 + 투구수."""
        relay = self._relay
        cgs = relay.get("currentGameState") or {}
        inn = relay.get("inn", "-")
        hoa = str(relay.get("homeOrAway", "-"))
        side_label = "초" if hoa == "0" else "말"
        away_code = self._game.away_team_code if self._game else "원정"
        home_code = self._game.home_team_code if self._game else "홈"
        away_meta = _team_meta(away_code)
        home_meta = _team_meta(home_code)
        away_score = str(cgs.get("awayScore", "0"))
        home_score = str(cgs.get("homeScore", "0"))
        away_hit = str(cgs.get("awayHit", "0"))
        home_hit = str(cgs.get("homeHit", "0"))
        away_err = str(cgs.get("awayError", "0"))
        home_err = str(cgs.get("homeError", "0"))

        # 큰 점수 표: 팀이름 / R / H / E
        score_tbl = Table(show_header=True, box=None, padding=(0, 1),
                          expand=True, header_style="dim")
        score_tbl.add_column("팀", justify="left", no_wrap=True)
        score_tbl.add_column("R", justify="right", style="bold")
        score_tbl.add_column("H", justify="right", style="dim")
        score_tbl.add_column("E", justify="right", style="dim")
        score_tbl.add_row(
            f"[bold {away_meta['color']}]{away_meta['name']}[/]",
            f"[bold {away_meta['color']}]{away_score}[/]",
            away_hit, away_err,
        )
        score_tbl.add_row(
            f"[bold {home_meta['color']}]{home_meta['name']}[/]",
            f"[bold {home_meta['color']}]{home_score}[/]",
            home_hit, home_err,
        )

        # 이닝 배지 큰 글씨
        inn_badge = Align.center(Text.from_markup(
            f"[bold yellow on grey15]  {inn}회 {side_label}  [/]"
        ))

        # B/S/O 진행 막대 — 채워진 도트는 컬러, 빈 도트는 어둡게
        def bar(label: str, filled: int, total: int, color: str) -> str:
            full = f"[{color}]●[/]" * filled
            empty = "[grey30]○[/]" * (total - filled)
            return f"[bold]{label}[/]  {full}{empty}"

        ball = int(cgs.get("ball", 0) or 0)
        strike = int(cgs.get("strike", 0) or 0)
        out = int(cgs.get("out", 0) or 0)
        bso = (
            f"{bar('B', ball, 4, 'green')}\n"
            f"{bar('S', strike, 3, 'yellow')}\n"
            f"{bar('O', out, 3, 'red')}"
        )

        # 현재 투수 + 투구수
        pitcher_row = self._find_lineup_row(cgs.get("pitcher"), "pitcher",
                                            defense_side=True)
        pcount = pitcher_row.get("ballCount", "-")
        pname = pitcher_row.get("name", "-")
        pitcher_line = (
            f"[dim]현재 투수[/]\n[bold]{pname}[/]\n"
            f"[dim]투구수[/]  [bold]{pcount}[/]"
        )

        body = Group(
            score_tbl,
            Text(""),
            inn_badge,
            Text(""),
            Text.from_markup(bso),
            Text(""),
            Text.from_markup(pitcher_line),
        )
        return Panel(body, title="[bold red]SCORE[/]", border_style="red")

    def _field_panel(self, width: int = 80) -> Panel:
        """중앙: 라인업 표 형식의 필드.

        한 행이 하나의 포지션이고, 컬럼은:
          [구역]  포지션  수비수      |  주자/상태
            외야   좌익    이형종      |
            ...
            내야   3루     김웅빈      |  ◆ 오태곤 (주자)
            ...
            홈     포수    김건희      |  ▶ 4번 에레디아 (타석)
            홈     투수    김재웅      |

        반응형:
          width >= 60  : 구역 컬럼 포함, 전체 정보
          40 <= width < 60 : 구역 컬럼 생략, 그 외 그대로
          width < 40   : 포지션 + 이름만 (주자는 다이아몬드 한 줄 요약)
        """
        relay = self._relay
        cgs = relay.get("currentGameState") or {}
        hoa = str(relay.get("homeOrAway", "-"))
        defense_side = "away" if hoa == "1" else "home"

        defense_lineup = (relay.get(f"{defense_side}Lineup") or {}).get("batter") or []
        pos_to_name: dict[str, str] = {}
        for b in defense_lineup:
            pos = b.get("posName")
            if pos and pos not in pos_to_name:
                pos_to_name[pos] = b.get("name", "-")
        pitcher_row = self._find_lineup_row(cgs.get("pitcher"), "pitcher",
                                            defense_side=True)
        pos_to_name.setdefault("투수", pitcher_row.get("name", "-"))

        batter_row = self._find_lineup_row(cgs.get("batter"), "batter",
                                            defense_side=False)
        batter_name = batter_row.get("name", "-")
        batter_order = batter_row.get("batOrder", "?")

        on1 = str(cgs.get("base1", "0")) not in {"0", "", "None"}
        on2 = str(cgs.get("base2", "0")) not in {"0", "", "None"}
        on3 = str(cgs.get("base3", "0")) not in {"0", "", "None"}

        compact = width < 60
        tiny = width < 40

        def fielder_name(pos: str) -> str:
            return pos_to_name.get(pos) or "[dim]-[/]"

        def runner_text(on: bool) -> str:
            return "[bold yellow]◆[/]" if on else "[grey30]◇[/]"

        t = Table(show_header=True, box=None, padding=(0, 1),
                  expand=True, header_style="dim")
        if not compact:
            t.add_column("구역", style="dim", no_wrap=True, width=4)
        t.add_column("포지션", no_wrap=True, width=4)
        t.add_column("수비", no_wrap=True)
        if not tiny:
            t.add_column("주자/상태", no_wrap=True)

        def row(area: str, pos: str, name: str, runner: str = "") -> None:
            cells = []
            if not compact:
                cells.append(area)
            cells.append(pos)
            cells.append(name)
            if not tiny:
                cells.append(runner)
            t.add_row(*cells)

        # 외야
        row("외야", "좌익", fielder_name("좌익수"))
        row("",   "중견", fielder_name("중견수"))
        row("",   "우익", fielder_name("우익수"))
        # 내야 — 베이스가 있는 포지션은 주자 마커 표시
        row("내야", "유격", fielder_name("유격수"))
        # 베이스 행 — 주자 있을 때만 표시, 비어있는 베이스는 공백
        row("",   "3루", fielder_name("3루수"),
            f"[bold yellow]◆ 주자[/]" if on3 else "")
        row("",   "2루", fielder_name("2루수"),
            f"[bold yellow]◆ 주자[/]" if on2 else "")
        row("",   "1루", fielder_name("1루수"),
            f"[bold yellow]◆ 주자[/]" if on1 else "")
        # 홈 — 투수, 포수 (타석은 panel 상단으로 이동)
        row("홈",  "투수", fielder_name("투수"))
        row("",   "포수", fielder_name("포수"))

        # 작은 다이아몬드 미니맵 — 상단으로 끌어올림
        diamond = (
            f"     {runner_text(on2)}\n"
            f"  {runner_text(on3)}     {runner_text(on1)}\n"
            f"     [grey30]◇[/]"
        )

        # ▶ 타석 — panel 최상단 별도 라인 (가장 큰 비중)
        at_bat_top = Text.from_markup(
            f"[bold yellow]▶ {batter_order}번 {batter_name}[/]  [dim](타석)[/]"
        )

        body = Group(
            Align.center(at_bat_top),
            Align.center(Text.from_markup(diamond)),
            Text(""),
            t,
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

    def _maybe_homerun(self, new_events: list[dict]) -> None:
        """새 이벤트 중 '홈런'이 보이면 native notification 만 (TTS 는 공수 교대 시)."""
        for ev in new_events:
            title = ev.get("title") or ""
            topts = ev.get("textOptions") or []
            text = topts[0].get("text", "") if topts and isinstance(topts, list) else ""
            blob = f"{title} {text}"
            if "홈런" not in blob:
                continue
            hoa = str(ev.get("homeOrAway", "-"))
            team_code = None
            if self._game:
                team_code = (self._game.home_team_code if hoa == "1"
                              else self._game.away_team_code)
            try:
                from . import notify as N
                body = title if title else "홈런!"
                if text and text != title:
                    body = f"{title} — {text}"
                N.send_notification(f"💥 {team_code or 'KBO'} 홈런!", body, sound="Hero")
            except Exception:
                pass
            break

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
