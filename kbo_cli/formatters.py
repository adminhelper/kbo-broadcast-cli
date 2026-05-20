"""Rich 기반 출력 포매터: 스코어보드, 일정표, 순위표, 라인업 등."""

from __future__ import annotations

from typing import Any, Iterable

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .data.cheer_songs import cheer
from .data.teams import colored, team
from .models import Game, TeamRank


# ────────────────────────── 일정/결과 ──────────────────────────


def schedule_table(games: Iterable[Game], title: str = "오늘의 KBO 경기") -> Table:
    t = Table(title=title, title_style="bold cyan", header_style="bold")
    t.add_column("시간", justify="center", width=6)
    t.add_column("원정 (선공)", justify="right")
    t.add_column("스코어", justify="center", width=8)
    t.add_column("홈 (후공)", justify="left")
    t.add_column("구장", style="dim")
    t.add_column("상태", justify="center")
    t.add_column("중계", style="dim")
    t.add_column("Game ID", style="dim")

    for g in games:
        away = colored(g.away_team_code, g.away_team_name)
        home = colored(g.home_team_code, g.home_team_name)
        if g.is_finished:
            score = f"[bold]{g.away_team_score} : {g.home_team_score}[/]"
        elif g.status_code == "STARTED":
            score = f"[bold yellow]{g.away_team_score} : {g.home_team_score}[/]"
        else:
            score = "vs"
        status_color = {
            "RESULT": "green",
            "STARTED": "yellow",
            "BEFORE": "white",
        }.get(g.status_code or "", "white")
        if g.cancel:
            status_color = "red"
        t.add_row(
            g.start_time,
            away,
            score,
            home,
            g.stadium or "-",
            f"[{status_color}]{g.display_status}[/]",
            g.broad_channel or "-",
            g.game_id,
        )
    return t


# ────────────────────────── 순위표 ──────────────────────────


def standings_table(ranks: list[TeamRank]) -> Table:
    t = Table(title="KBO 팀 순위", title_style="bold cyan", header_style="bold")
    t.add_column("순위", justify="center")
    t.add_column("팀")
    t.add_column("경기", justify="right")
    t.add_column("승", justify="right", style="green")
    t.add_column("무", justify="right")
    t.add_column("패", justify="right", style="red")
    t.add_column("승률", justify="right")
    t.add_column("게임차", justify="right")
    t.add_column("최근10", justify="center")
    t.add_column("연속", justify="center")

    for r in ranks:
        # 1·2·3위는 메달 컬러
        rank_style = {1: "[bold yellow]", 2: "[bold white]", 3: "[bold orange3]"}.get(r.rank, "")
        rank_close = "[/]" if rank_style else ""
        t.add_row(
            f"{rank_style}{r.rank}{rank_close}",
            colored(r.team_code, r.team_name),
            str(r.games),
            str(r.wins),
            str(r.draws),
            str(r.losses),
            f"{r.win_rate:.3f}",
            "-" if r.games_behind == 0 else f"{r.games_behind:.1f}",
            r.recent10,
            r.streak,
        )
    return t


# ────────────────────────── 스코어보드 ──────────────────────────


def scoreboard(game: Game, relay: dict[str, Any] | None = None) -> Panel:
    """스코어보드 + 현재 이닝/카운트/주자."""
    away_name = colored(game.away_team_code, game.away_team_name)
    home_name = colored(game.home_team_code, game.home_team_name)

    inning_score = (relay or {}).get("inningScore") or {}
    home_innings = inning_score.get("home", {}) or {}
    away_innings = inning_score.get("away", {}) or {}
    max_inning = max(
        [int(k) for k in list(home_innings.keys()) + list(away_innings.keys()) if k.isdigit()] or [9]
    )

    tbl = Table(show_header=True, header_style="bold", padding=(0, 1), expand=False)
    tbl.add_column("팀", no_wrap=True)
    for i in range(1, max(max_inning, 9) + 1):
        tbl.add_column(str(i), justify="center", width=2)
    tbl.add_column("R", justify="center", style="bold")
    tbl.add_column("H", justify="center", style="dim")
    tbl.add_column("E", justify="center", style="dim")

    def _row(name: str, innings: dict[str, str], total: int, is_top: bool) -> list[str]:
        cells = [name]
        for i in range(1, max(max_inning, 9) + 1):
            cells.append(innings.get(str(i), "-"))
        # H/E는 record 호출이 따로 필요 — 일단 점수만
        cells += [str(total), "-", "-"]
        return cells

    # 선공 = 원정(away) 위에, 후공 = 홈(home) 아래에
    tbl.add_row(*_row(f"{away_name} ▲", away_innings, game.away_team_score or 0, True))
    tbl.add_row(*_row(f"{home_name} ▼", home_innings, game.home_team_score or 0, False))

    # 현재 상황 (이닝, 카운트, 주자)
    status_lines: list[RenderableType] = [tbl]
    if relay:
        inn = relay.get("inn")
        hoa = relay.get("homeOrAway")
        offense = "초" if str(hoa) == "0" else "말"  # 0=away=초, 1=home=말 (네이버 관례)
        base = relay.get("baseInfo") or {}
        bases = base.get("bases") or [False, False, False]
        out = base.get("out", "-")
        ball = base.get("ball", "-")
        strike = base.get("strike", "-")
        diamond = _diamond(bases)
        line1 = Text.from_markup(
            f"[bold]{inn}회 {offense}[/]   "
            f"B [yellow]{ball}[/]  S [red]{strike}[/]  O [white]{out}[/]"
        )
        status_lines.append(Text(""))
        status_lines.append(line1)
        status_lines.append(diamond)

    title = (
        f"[bold]{game.stadium or '-'}[/]  "
        f"[dim]{game.game_date or ''}  {game.start_time}  {game.display_status}[/]"
    )
    return Panel(Group(*status_lines), title=title, border_style="cyan")


def _diamond(bases: list[bool]) -> Text:
    """1·2·3루 주자 표시 (◆ = 주자, ◇ = 빈루)."""
    b1, b2, b3 = (bases + [False, False, False])[:3]
    sym = lambda x: "[bold yellow]◆[/]" if x else "[dim]◇[/]"
    return Text.from_markup(
        f"        {sym(b2)}\n"
        f"   {sym(b3)}     {sym(b1)}\n"
        f"        [dim]◇[/]"
    )


# ────────────────────────── 문자중계 ──────────────────────────


def text_relay_lines(relay: dict[str, Any] | list[dict], limit: int | None = 20) -> Group:
    """문자중계 렌더. relay는 textRelayData dict 또는 미리 합쳐둔 list.

    Naver schema:
      - title: "3회말 삼성 공격" / "4번타자 디아즈" / 이벤트 요약
      - inn: 이닝
      - homeOrAway: "0"(원정/초) / "1"(홈/말)
      - no, seqno: 이벤트 순서
    """
    if isinstance(relay, list):
        items = relay
    else:
        items = (
            relay.get("textRelays")
            or relay.get("textRelayList")
            or relay.get("relays")
            or []
        )

    # 이벤트는 보통 inn 오름차순 + no 오름차순으로 정렬해야 시간순
    try:
        items = sorted(items, key=lambda r: (int(r.get("inn") or 0), int(r.get("no") or 0)))
    except (TypeError, ValueError):
        pass

    if limit is not None:
        items = items[-limit:]

    out: list[RenderableType] = []
    last_inning_side: tuple[int, str] | None = None
    for r in items:
        inn = r.get("inn", "-")
        hoa = r.get("homeOrAway")
        side = "초" if str(hoa) == "0" else "말"
        # 이닝 헤더 ("3회말 삼성 공격" 같은 statusCode=0)는 진하게
        title = r.get("title") or ""
        style_code = str(r.get("titleStyle") or r.get("type") or "")
        # textOptions[0].text에 실제 결과 텍스트가 들어가는 경우가 있음
        text = ""
        topts = r.get("textOptions") or []
        if topts and isinstance(topts, list):
            text = topts[0].get("text") or topts[0].get("textOptionDesc") or ""
            # title과 동일하면 생략
            if text.strip() == title.strip():
                text = ""
        if style_code == "0":
            out.append(Text.from_markup(f"\n[bold yellow]▶ {title}[/]"))
        else:
            prefix = f"[dim]{inn}회{side}[/]"
            body = f"[bold]{title}[/]"
            if text:
                body += f"  [dim]→[/] {text}"
            out.append(Text.from_markup(f"  {prefix}  {body}"))
        last_inning_side = (int(inn) if str(inn).isdigit() else 0, side)
    if not out:
        out.append(Text.from_markup("[dim](문자중계 데이터 없음)[/]"))
    return Group(*out)


# ────────────────────────── 박스스코어 ──────────────────────────


def _str(v: Any, dash: str = "-") -> str:
    if v is None or v == "":
        return dash
    return str(v)


def batter_table(record: dict[str, Any], side: str = "home") -> Table:
    """타자 박스스코어. side: "home" | "away"."""
    rows = (record.get("battersBoxscore") or {}).get(side, []) or []
    title = "홈 타자" if side == "home" else "원정 타자"
    t = Table(title=title, title_style="bold", header_style="bold dim")
    t.add_column("타순", justify="center")
    t.add_column("선수")
    t.add_column("포지션", style="dim")
    t.add_column("타수", justify="right")
    t.add_column("안타", justify="right")
    t.add_column("홈런", justify="right")
    t.add_column("타점", justify="right")
    t.add_column("득점", justify="right")
    t.add_column("4구", justify="right")
    t.add_column("삼진", justify="right")
    t.add_column("도루", justify="right")
    t.add_column("타율", justify="right")
    for r in rows:
        t.add_row(
            _str(r.get("batOrder")),
            _str(r.get("name")),
            _str(r.get("pos")),
            _str(r.get("ab")),
            _str(r.get("hit")),
            _str(r.get("hr")),
            _str(r.get("rbi")),
            _str(r.get("run")),
            _str(r.get("bb")),
            _str(r.get("kk")),
            _str(r.get("sb")),
            _str(r.get("hra")),
        )
    return t


def pitcher_table(record: dict[str, Any], side: str = "home") -> Table:
    rows = (record.get("pitchersBoxscore") or {}).get(side, []) or []
    title = "홈 투수" if side == "home" else "원정 투수"
    t = Table(title=title, title_style="bold", header_style="bold dim")
    t.add_column("선수")
    t.add_column("결과", style="dim")
    t.add_column("이닝", justify="right")
    t.add_column("타자", justify="right")
    t.add_column("피안타", justify="right")
    t.add_column("실점", justify="right")
    t.add_column("자책", justify="right")
    t.add_column("탈삼진", justify="right")
    t.add_column("4구", justify="right")
    t.add_column("ERA", justify="right")
    for r in rows:
        result = r.get("wls") or r.get("tb") or ""
        t.add_row(
            _str(r.get("name")),
            _str(result),
            _str(r.get("inn")),
            _str(r.get("bf")),
            _str(r.get("hit")),
            _str(r.get("r")),
            _str(r.get("er")),
            _str(r.get("kk")),
            _str(r.get("bb")),
            _str(r.get("era")),
        )
    return t


# ────────────────────────── 응원/팀 정보 ──────────────────────────


def team_info_panel(team_code: str) -> Panel:
    t = team(team_code)
    c = cheer(team_code)
    songs = "\n".join(f"  • {s}" for s in (c.get("songs") or []))
    body = Text.from_markup(
        f"[bold {t['color']}]{t['full_name']}[/]\n"
        f"[dim]홈구장:[/] {t['stadium']}\n"
        f"[dim]마스코트:[/] {t['mascot']}\n\n"
        f"[bold]대표 응원 구호[/]\n  {c.get('famous_chant')}\n"
        f"  {c.get('battle_cry')}\n\n"
        f"[bold]대표 응원가[/]\n{songs}"
    )
    return Panel(body, title=f"[bold {t['color']}]{t['name']}[/] 팀 정보", border_style=t["color"])
