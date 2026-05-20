"""KBO CLI 엔트리포인트.

명령 일람:
  kbo today                       오늘의 경기 일정/결과
  kbo yesterday                   어제 경기 결과
  kbo schedule [날짜]             특정 날짜 (YYYY-MM-DD / yesterday / -N) 일정
  kbo standings                   팀 순위표
  kbo game <gameId>               경기 박스스코어 + 결승타 + 라인업
  kbo replay <gameId>             과거 경기 전체 리플레이 (스코어 + 박스 + 문자중계)
  kbo team <팀코드>               팀 정보 + 응원가
  kbo live <gameId>               실시간 중계 (Textual TUI)
"""

from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, timedelta
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
    """YYYY-MM-DD, yesterday/어제/오늘/today, ±N(일), N일전 등 지원."""
    if not s:
        return now_kst_date()
    s = s.strip().lower()
    today = now_kst_date()
    if s in {"today", "오늘"}:
        return today
    if s in {"yesterday", "어제"}:
        return today - timedelta(days=1)
    if s in {"tomorrow", "내일"}:
        return today + timedelta(days=1)
    # -3 / +2 / 3일전 / 5일후
    m = re.fullmatch(r"([+-]?\d+)(?:일?(전|후|ago)?)?", s)
    if m:
        n = int(m.group(1))
        suf = m.group(2)
        if suf in {"전", "ago"}:
            n = -abs(n)
        elif suf == "후":
            n = abs(n)
        return today + timedelta(days=n)
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


@app.command("yesterday", help="어제 경기 결과")
def yesterday() -> None:
    d = now_kst_date() - timedelta(days=1)
    async def _go() -> None:
        async with KBOClient() as c:
            games = await c.schedule(d)
        console.print(schedule_table(games, title=f"어제 KBO 경기 결과 ({d})"))

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


@app.command("replay", help="과거 경기 전체 리플레이 (스코어 + 박스 + 문자중계 전 이닝)")
def replay(
    game_id: str = typer.Argument(..., help="네이버 게임 ID (지난 경기)"),
    max_innings: int = typer.Option(12, "--max-innings", "-i", help="최대 조회 이닝 (연장 대비)"),
) -> None:
    async def _go() -> None:
        async with KBOClient() as c:
            try:
                rec = await c.record(game_id)
            except Exception as e:
                console.print(f"[red]record 조회 실패: {e}[/]")
                return
            current_inn = int(rec.get("currentInning") or 9)
            innings_to_fetch = min(max_innings, max(current_inn, 9))

            # 모든 이닝의 relay를 동시 요청
            relay_tasks = [c.relay(game_id, inning=i) for i in range(1, innings_to_fetch + 1)]
            relays = await asyncio.gather(*relay_tasks, return_exceptions=True)

            # 최신 이닝 relay (스코어보드용)
            latest_relay = next(
                (r for r in reversed(relays) if isinstance(r, dict) and r.get("textRelays")),
                {},
            )
            try:
                sched = await c.schedule(_game_date(game_id))
                g = next((x for x in sched if x.game_id == game_id), None)
            except Exception:
                g = None

        if g:
            console.print(scoreboard(g, latest_relay))

        etc = rec.get("etcRecords") or []
        if etc:
            lines = [f"[dim]{e.get('how', '')}:[/] {e.get('result', '')}" for e in etc[:8]]
            console.print(Panel("\n".join(lines), title="주요 기록", border_style="cyan"))

        # 박스스코어 (요약)
        console.print(batter_table(rec, "away"))
        console.print(pitcher_table(rec, "away"))
        console.print(batter_table(rec, "home"))
        console.print(pitcher_table(rec, "home"))

        # 전체 문자중계 — 이닝별 모아서 시간순 정렬
        all_events: list[dict] = []
        for r in relays:
            if isinstance(r, dict):
                all_events.extend(r.get("textRelays", []) or [])
        # 중복 제거 (no 기준)
        seen: set = set()
        dedup: list[dict] = []
        for e in all_events:
            key = (e.get("inn"), e.get("no"))
            if key in seen:
                continue
            seen.add(key)
            dedup.append(e)

        console.print(Panel(text_relay_lines(dedup, limit=None),
                            title="문자중계 (전체)", border_style="yellow"))

    _run(_go())


@app.command("live", help="실시간 중계 (Textual TUI)")
def live(game_id: str = typer.Argument(..., help="네이버 게임 ID")) -> None:
    from .tui import LiveBroadcastApp
    LiveBroadcastApp(game_id).run()


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
