"""KBO CLI 엔트리포인트.

명령 일람:
  kbo today                       오늘의 경기 일정/결과
  kbo schedule [날짜]             특정 날짜 (YYYY-MM-DD) 일정
  kbo standings                   팀 순위표
  kbo game <gameId>               경기 박스스코어 + 결승타 + 라인업
  kbo team <팀코드>               팀 정보 + 응원가
  kbo live <gameId>               실시간 중계 (Textual TUI)
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from .api import KBOClient, now_kst_date
from .data.cheer_songs import CHEER
from .data.teams import TEAMS
from .formatters import (
    batter_table,
    pitcher_table,
    schedule_table,
    scoreboard,
    standings_table,
    team_info_panel,
    text_relay_lines,
)

app = typer.Typer(
    name="kbo",
    help="KBO 야구 중계 CLI",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _parse_date(s: str | None) -> date:
    if not s:
        return now_kst_date()
    return datetime.strptime(s, "%Y-%m-%d").date()


def _run(coro):
    return asyncio.run(coro)


@app.command("today", help="오늘의 KBO 경기 일정/결과")
def today() -> None:
    async def _go() -> None:
        async with KBOClient() as c:
            games = await c.schedule(now_kst_date())
        console.print(schedule_table(games, title=f"오늘의 KBO 경기 ({now_kst_date()})"))

    _run(_go())


@app.command("schedule", help="특정 날짜 일정 조회")
def schedule(
    on: Optional[str] = typer.Argument(None, help="YYYY-MM-DD (생략 시 오늘)"),
) -> None:
    d = _parse_date(on)
    async def _go() -> None:
        async with KBOClient() as c:
            games = await c.schedule(d)
        console.print(schedule_table(games, title=f"KBO 경기 일정 ({d})"))

    _run(_go())


@app.command("standings", help="팀 순위표")
def standings(
    season: Optional[int] = typer.Option(None, "--season", "-s", help="시즌 연도"),
) -> None:
    async def _go() -> None:
        async with KBOClient() as c:
            ranks = await c.standings(season)
        if not ranks:
            console.print("[red]순위표를 가져오지 못했습니다. KBO 사이트 응답 형식이 바뀌었을 수 있습니다.[/]")
            return
        console.print(standings_table(ranks))

    _run(_go())


@app.command("game", help="경기 박스스코어 + 결승타 + 라인업")
def game(game_id: str = typer.Argument(..., help="네이버 게임 ID 예: 20260519KTSS02026")) -> None:
    async def _go() -> None:
        async with KBOClient() as c:
            try:
                rec = await c.record(game_id)
            except Exception as e:
                console.print(f"[red]record 조회 실패: {e}[/]")
                return
            try:
                rel = await c.relay(game_id)
            except Exception:
                rel = {}
            try:
                sched = await c.schedule(_game_date(game_id))
                g = next((x for x in sched if x.game_id == game_id), None)
            except Exception:
                g = None

        if g:
            console.print(scoreboard(g, rel))
        # 결승타·결승점 등 etcRecords
        etc = rec.get("etcRecords") or []
        if etc:
            lines = []
            for e in etc[:6]:
                lines.append(f"[dim]{e.get('how', '')}:[/] {e.get('result', '')}")
            console.print(Panel("\n".join(lines), title="주요 기록", border_style="cyan"))
        console.print(batter_table(rec, "away"))
        console.print(pitcher_table(rec, "away"))
        console.print(batter_table(rec, "home"))
        console.print(pitcher_table(rec, "home"))

    _run(_go())


def _game_date(game_id: str) -> date:
    # gameId 첫 8자리가 YYYYMMDD
    return datetime.strptime(game_id[:8], "%Y%m%d").date()


@app.command("team", help="팀 정보 + 응원가")
def team_cmd(
    team_code: Optional[str] = typer.Argument(None, help="팀 코드 (HT/SS/LG/OB/SK/LT/KT/WO/HH/NC). 생략 시 전 팀."),
) -> None:
    if team_code:
        console.print(team_info_panel(team_code.upper()))
        return
    # 전체 팀 카드
    from rich.columns import Columns
    panels = [team_info_panel(code) for code in TEAMS]
    console.print(Columns(panels, expand=True))


@app.command("live", help="실시간 중계 (Textual TUI)")
def live(game_id: str = typer.Argument(..., help="네이버 게임 ID")) -> None:
    from .tui import LiveBroadcastApp
    LiveBroadcastApp(game_id).run()


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
