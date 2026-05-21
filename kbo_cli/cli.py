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
from rich.panel import Panel
from rich.text import Text

from .api import KBOClient, now_kst_date
from .config import Config, config_path
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


def _resolve_game_id(query: str | None, games: list) -> "Game | None":
    """사용자 입력을 실제 game.game_id로 변환.

    지원하는 형태:
      - 없음        : 선호 팀의 진행 중 경기 우선
      - 정식 ID     : 'YYYYMMDD' 시작 (예: 20260521WOSSG02026)
      - 팀 코드     : 'SSG', 'KIA' (오늘 일정에서 해당 팀 경기)
      - 매치업      : 'ssg-wo', 'ssg vs wo', 'ssg wo' (두 팀 코드)
      - 번호        : '1' ~ '9'  (오늘 일정의 N번째 경기)
    """
    from .data.teams import normalize

    cfg = Config.load()
    fav = normalize(cfg.favorite_team) if cfg.favorite_team else ""

    def is_live(g):
        return g.status_code == "STARTED" and not g.cancel
    def is_before(g):
        return g.status_code == "BEFORE" and not g.cancel
    def is_fav(g):
        return fav and fav in {normalize(g.home_team_code), normalize(g.away_team_code)}

    # 인자 없음: 선호 팀 진행 → 진행 중 아무거나 → 선호 팀 시작 전 → 첫 시작 전
    if not query:
        return (
            next((g for g in games if is_live(g) and is_fav(g)), None)
            or next((g for g in games if is_live(g)), None)
            or next((g for g in games if is_before(g) and is_fav(g)), None)
            or next((g for g in games if is_before(g)), None)
        )

    q = query.strip()

    # 정식 game ID (YYYYMMDD로 시작 + 영문)
    if len(q) >= 12 and q[:8].isdigit():
        # schedule 결과에 없어도 일단 통과 (다른 날짜)
        return next((g for g in games if g.game_id == q), _StubGame(q))

    # 번호 (1~9)
    if q.isdigit() and 1 <= int(q) <= 9:
        idx = int(q) - 1
        if idx < len(games):
            return games[idx]
        return None

    # 두 팀 매치업 (구분자: '-', ' ', 'vs', 'VS')
    import re
    parts = [p for p in re.split(r"[\s\-/]+|vs", q, flags=re.IGNORECASE) if p]
    parts = [normalize(p) for p in parts]
    if len(parts) >= 2:
        a, b = parts[0], parts[1]
        for g in games:
            home = normalize(g.home_team_code)
            away = normalize(g.away_team_code)
            if {home, away} == {a, b}:
                return g
        return None

    # 단일 팀 코드
    if len(parts) == 1:
        code = parts[0]
        candidates = [g for g in games
                      if code in {normalize(g.home_team_code), normalize(g.away_team_code)}]
        if not candidates:
            return None
        return (
            next((g for g in candidates if is_live(g)), None)
            or next((g for g in candidates if is_before(g)), None)
            or candidates[0]
        )

    return None


class _StubGame:
    """game_id만 있고 schedule에 없는 경우의 최소 객체."""
    def __init__(self, gid: str):
        self.game_id = gid
        self.home_team_code = self.away_team_code = None
        self.home_team_name = self.away_team_name = None
        self.display_status = "?"


@app.command("live", help="실시간 중계 — 새 터미널 창(또는 tmux split)에서 옆에 표시")
def live(
    query: Optional[str] = typer.Argument(
        None,
        help="게임ID / 팀코드(SSG) / 매치업(ssg-wo) / 번호(1~9). 생략 시 선호 팀 진행 경기.",
    ),
    here: bool = typer.Option(
        False, "--here",
        help="새 창을 열지 않고 현재 터미널에서 실행 (블로킹).",
    ),
) -> None:
    from .tui import LiveBroadcastApp
    from .data.teams import colored
    from . import launch as L

    # 오늘 일정 로드
    async def _go():
        async with KBOClient() as c:
            return await c.schedule(now_kst_date())
    games = _run(_go())

    chosen = _resolve_game_id(query, games)
    if not chosen:
        console.print(f"[red]'{query}'에 해당하는 경기를 찾지 못했습니다.[/]" if query
                      else "[yellow]진행 중이거나 곧 시작할 KBO 경기가 없습니다.[/]")
        console.print("[dim]오늘 경기 목록을 보려면: kbo today[/]")
        console.print("[dim]예시: kbo live SSG  /  kbo live ssg-wo  /  kbo live 1[/]")
        return

    if getattr(chosen, "home_team_code", None):
        away = colored(chosen.away_team_code, chosen.away_team_name)
        home = colored(chosen.home_team_code, chosen.home_team_name)
        status_label = chosen.display_status
        console.print(Text.from_markup(
            f"[dim]선택:[/] {away} vs {home}  [dim]({status_label})  {chosen.game_id}[/]"
        ))

    if here:
        LiveBroadcastApp(chosen.game_id).run()
        return

    # 새 터미널/패널에서 실행
    mode = L.launch_side_panel(chosen.game_id)
    msg_map = {
        "tmux": "tmux 오른쪽 패널에서 실행 중입니다. Ctrl+B → O 로 패널 전환.",
        "iterm": "iTerm 새 창에서 실행 중입니다.",
        "terminal": "Terminal 새 창에서 실행 중입니다.",
        "inline": "새 창 자동 실행 환경이 아닙니다. '--here' 플래그로 현재 터미널에서 실행하세요.",
    }
    if mode in {"gnome-terminal", "konsole", "xfce4-terminal", "xterm"}:
        console.print(f"[green]✓ {mode} 새 창에서 실행 중입니다.[/]")
    elif mode == "inline":
        console.print(f"[yellow]{msg_map[mode]}[/]")
        # 폴백: 그냥 여기서 실행
        LiveBroadcastApp(chosen.game_id).run()
    else:
        console.print(f"[green]✓ {msg_map[mode]}[/]")
        console.print("[dim]종료는 그 창에서 'q'를 누르세요. 메인 터미널은 계속 사용 가능합니다.[/]")


notify_app = typer.Typer(help="경기 시작 알림 (선호 팀 30분 전 자동 알림)")
app.add_typer(notify_app, name="notify")


@notify_app.command("check", help="지금 임박한 경기를 확인하고 알림 발송 (스케줄러가 호출)")
def notify_check(
    lead: int = typer.Option(30, "--lead", "-l", help="시작 N분 전부터 알림"),
    all_games: bool = typer.Option(False, "--all", help="선호 팀 외 전체 경기도 알림"),
) -> None:
    from . import notify as N
    cfg = Config.load()
    fav = None if all_games else cfg.favorite_team

    async def _go():
        async with KBOClient() as c:
            return await c.schedule(now_kst_date())

    games = _run(_go())
    upcoming = N.find_upcoming(games, lead_minutes=lead, favorite=fav)

    sent = 0
    for ug in upcoming:
        if N.already_notified(ug.game.game_id):
            continue
        title, body = N.format_message(ug)
        if N.send_notification(title, body):
            N.mark_notified(ug.game.game_id)
            sent += 1
            console.print(f"[green]🔔 {title}[/]  {body}")
    if not sent:
        console.print(f"[dim]임박 경기 없음 (lead={lead}분, favorite={fav or '전체'})[/]")


@notify_app.command("test", help="테스트 알림 한 번 발송")
def notify_test() -> None:
    from . import notify as N
    ok = N.send_notification("⚾ KBO 알림 테스트", "이 메시지가 보이면 알림 설정 정상입니다.")
    if ok:
        console.print("[green]✓ 알림 전송 성공[/]")
    else:
        console.print("[red]✗ 알림 전송 실패 — 시스템 알림 권한을 확인하세요.[/]")


@notify_app.command("install", help="백그라운드 자동 알림 설치 (macOS launchd)")
def notify_install(
    interval: int = typer.Option(300, "--interval", "-i", help="체크 주기(초). 기본 5분"),
    all_games: bool = typer.Option(False, "--all", help="선호 팀 외 전체 경기도 알림"),
) -> None:
    from . import notify as N
    import platform
    if platform.system() != "Darwin":
        console.print("[yellow]자동 설치는 현재 macOS만 지원합니다.[/]")
        console.print("[dim]Linux는 cron 또는 systemd timer로 'kbo notify check'를 주기적으로 실행하세요.[/]")
        return
    try:
        p = N.install_launchd(interval_seconds=interval, all_games=all_games)
    except Exception as e:
        console.print(f"[red]설치 실패: {e}[/]")
        return
    cfg = Config.load()
    target = "전체 KBO 경기" if all_games else f"{cfg.favorite_team or '선호 팀'}"
    console.print(Panel(
        Text.from_markup(
            f"[bold green]✓ 자동 알림 설치 완료[/]\n\n"
            f"매 {interval}초마다 임박한 [bold]{target}[/]을 확인해\n"
            f"시작 30분 이내 경기에 대해 알림을 보냅니다.\n\n"
            f"[dim]plist:[/] {p}\n"
            f"[dim]로그:[/] ~/.cache/kbo-cli/notify.out.log"
        ),
        border_style="green",
    ))


@notify_app.command("uninstall", help="백그라운드 자동 알림 제거")
def notify_uninstall() -> None:
    from . import notify as N
    ok = N.uninstall_launchd()
    if ok:
        console.print("[green]✓ 자동 알림 제거 완료[/]")
    else:
        console.print("[yellow]설치된 알림이 없거나 이미 제거됨.[/]")


@notify_app.command("status", help="자동 알림 상태 확인")
def notify_status() -> None:
    from . import notify as N
    s = N.launchd_status()
    if not s.get("installed"):
        console.print(f"[yellow]자동 알림 미설치.[/] [dim]플랫폼: {s.get('platform', 'macOS')}[/]")
        console.print("  설치: [bold]kbo notify install[/]")
        return
    color = "green" if s.get("loaded") else "yellow"
    console.print(Panel(
        Text.from_markup(
            f"[bold {color}]자동 알림: {'활성' if s.get('loaded') else '플리스트만 존재'}[/]\n"
            f"[dim]plist:[/] {s.get('plist')}\n"
            f"[dim]detail:[/] {s.get('detail', '')}"
        ),
        border_style=color,
    ))


@notify_app.command("run", help="포그라운드 워처: 1분마다 체크 (Ctrl+C로 종료)")
def notify_run(
    lead: int = typer.Option(30, "--lead", "-l"),
    all_games: bool = typer.Option(False, "--all"),
    interval: int = typer.Option(60, "--interval", "-i", help="체크 주기(초)"),
) -> None:
    import time
    console.print(f"[bold]🔔 KBO 알림 워처 시작[/]  lead={lead}분  interval={interval}s")
    console.print("[dim]Ctrl+C로 종료[/]\n")
    try:
        while True:
            notify_check(lead=lead, all_games=all_games)
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]워처 종료[/]")


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
