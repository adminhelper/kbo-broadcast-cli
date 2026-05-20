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
from .config import Config, config_path
from .data.cheer_songs import CHEER
from .data.teams import TEAMS, normalize, team
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
    no_args_is_help=False,  # 인자 없이 호출되면 dashboard 실행
    rich_markup_mode="rich",
)
console = Console()


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """`kbo` 단독 호출 시: 설정이 없으면 setup, 있으면 dashboard."""
    if ctx.invoked_subcommand is not None:
        return
    cfg = Config.load()
    if not cfg.is_configured:
        _run_setup_wizard()
    else:
        _run_dashboard(cfg)


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


@app.command("today", help="오늘의 KBO 경기 일정/결과 (선호 팀 우선)")
def today() -> None:
    cfg = Config.load()
    async def _go() -> None:
        async with KBOClient() as c:
            games = await c.schedule(now_kst_date())
        console.print(schedule_table(games,
                                     title=f"오늘의 KBO 경기 ({now_kst_date()})",
                                     favorite=cfg.favorite_team))

    _run(_go())


@app.command("yesterday", help="어제 경기 결과")
def yesterday() -> None:
    cfg = Config.load()
    d = now_kst_date() - timedelta(days=1)
    async def _go() -> None:
        async with KBOClient() as c:
            games = await c.schedule(d)
        console.print(schedule_table(games,
                                     title=f"어제 KBO 경기 결과 ({d})",
                                     favorite=cfg.favorite_team))

    _run(_go())


@app.command("schedule", help="특정 날짜 일정 조회")
def schedule(
    on: Optional[str] = typer.Argument(None, help="YYYY-MM-DD / yesterday / 3일전 등"),
) -> None:
    cfg = Config.load()
    d = _parse_date(on)
    async def _go() -> None:
        async with KBOClient() as c:
            games = await c.schedule(d)
        console.print(schedule_table(games,
                                     title=f"KBO 경기 일정 ({d})",
                                     favorite=cfg.favorite_team))

    _run(_go())


@app.command("standings", help="팀 순위표 (선호 팀 하이라이트)")
def standings(
    season: Optional[int] = typer.Option(None, "--season", "-s", help="시즌 연도"),
) -> None:
    cfg = Config.load()
    async def _go() -> None:
        async with KBOClient() as c:
            ranks = await c.standings(season)
        if not ranks:
            console.print("[red]순위표를 가져오지 못했습니다. KBO 사이트 응답 형식이 바뀌었을 수 있습니다.[/]")
            return
        console.print(standings_table(ranks, favorite=cfg.favorite_team))

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


@app.command("setup", help="초기 설정 - 선호 팀 등록")
def setup() -> None:
    _run_setup_wizard()


@app.command("config", help="현재 설정 보기")
def show_config() -> None:
    cfg = Config.load()
    if not cfg.is_configured:
        console.print(f"[yellow]설정이 없습니다. `kbo setup`을 실행하세요.[/]")
        console.print(f"[dim]설정 파일 위치: {config_path()}[/]")
        return
    fav = team(cfg.favorite_team)
    console.print(Panel(
        Text.from_markup(
            f"[bold]선호 팀:[/] [bold {fav['color']}]{fav['full_name']}[/]  "
            f"([dim]{cfg.favorite_team}[/])\n"
            f"[bold]설정 파일:[/] [dim]{config_path()}[/]"
        ),
        title="kbo-cli 설정",
        border_style="cyan",
    ))


def _run_setup_wizard() -> None:
    """선호 팀 선택 인터랙티브 위저드."""
    console.print(Panel(
        Text.from_markup(
            "[bold cyan]환영합니다! kbo-cli 초기 설정[/]\n\n"
            "선호하는 KBO 팀을 한 개 선택하세요. 이후 모든 명령에서\n"
            "이 팀의 경기·순위가 ⭐ 표시와 함께 우선 노출됩니다."
        ),
        border_style="cyan",
    ))

    from rich.table import Table as _T
    t = _T(show_header=True, header_style="bold", title_style="bold cyan")
    t.add_column("#", justify="center")
    t.add_column("코드", justify="center")
    t.add_column("팀")
    codes = list(TEAMS.keys())
    for i, code in enumerate(codes, 1):
        meta = TEAMS[code]
        t.add_row(str(i),
                  f"[bold {meta['color']}]{code}[/]",
                  f"[{meta['color']}]{meta['full_name']}[/]")
    console.print(t)

    while True:
        raw = typer.prompt("팀 번호 또는 코드 입력 (예: 5 또는 KIA)").strip()
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(codes):
                chosen = codes[idx - 1]
                break
            console.print(f"[red]1~{len(codes)} 사이 숫자를 입력하세요.[/]")
            continue
        canon = normalize(raw)
        if canon in TEAMS:
            chosen = canon
            break
        console.print(f"[red]모르는 팀 코드입니다: {raw}[/]")

    cfg = Config.load()
    cfg.favorite_team = chosen
    path = cfg.save()
    fav = team(chosen)
    console.print(Panel(
        Text.from_markup(
            f"선호 팀이 [bold {fav['color']}]{fav['full_name']}[/]로 저장되었습니다. ⭐\n\n"
            f"이제 [bold]kbo[/]만 입력하면 {fav['name']} 대시보드가 열려요.\n"
            f"[dim]설정 파일: {path}[/]"
        ),
        title="✅ 설정 완료",
        border_style="green",
    ))


def _run_dashboard(cfg: Config) -> None:
    """선호 팀 위주 한눈 대시보드."""
    fav_code = cfg.favorite_team
    fav = team(fav_code)
    today_date = now_kst_date()

    async def _go():
        async with KBOClient() as c:
            # 동시 요청: 오늘 일정 / 어제 일정 / 순위
            today_games_t, yest_games_t, ranks_t = await asyncio.gather(
                c.schedule(today_date),
                c.schedule(today_date - timedelta(days=1)),
                c.standings(),
                return_exceptions=True,
            )
        return today_games_t, yest_games_t, ranks_t

    today_games, yest_games, ranks = _run(_go())

    console.print(Panel(
        Text.from_markup(
            f"[bold {fav['color']}]⭐ {fav['full_name']} 대시보드[/]   "
            f"[dim]{today_date}[/]"
        ),
        border_style=fav["color"],
    ))

    # 1) 선호 팀 어제 결과
    if isinstance(yest_games, list):
        my_yest = [g for g in yest_games
                   if fav_code in {normalize(g.home_team_code), normalize(g.away_team_code)}]
        if my_yest:
            console.print(schedule_table(my_yest,
                                         title=f"{fav['name']} 어제 결과",
                                         favorite=fav_code))

    # 2) 선호 팀 오늘/다음 경기
    if isinstance(today_games, list):
        my_today = [g for g in today_games
                    if fav_code in {normalize(g.home_team_code), normalize(g.away_team_code)}]
        if my_today:
            console.print(schedule_table(my_today,
                                         title=f"{fav['name']} 오늘 경기",
                                         favorite=fav_code))
        else:
            console.print(f"[dim]{fav['name']}은(는) 오늘 경기가 없어요.[/]")

    # 3) 순위표 (선호 팀 하이라이트)
    if isinstance(ranks, list) and ranks:
        console.print(standings_table(ranks, favorite=fav_code))
        my_rank = next((r for r in ranks if normalize(r.team_code) == fav_code), None)
        if my_rank:
            console.print(Text.from_markup(
                f"[dim]현재 {fav['name']} 시즌:[/]  "
                f"[bold]{my_rank.rank}위[/]  "
                f"{my_rank.wins}승 {my_rank.draws}무 {my_rank.losses}패  "
                f"승률 {my_rank.win_rate:.3f}  "
                f"최근10 {my_rank.recent10}  연속 {my_rank.streak}"
            ))

    # 4) 오늘 전체 경기 요약
    if isinstance(today_games, list) and today_games:
        console.print(schedule_table(today_games,
                                     title="오늘 전체 KBO 경기",
                                     favorite=fav_code))


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
