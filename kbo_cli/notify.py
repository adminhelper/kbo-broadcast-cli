"""경기 시작 알림.

기본 흐름:
- `kbo notify check`가 오늘 일정을 조회해 시작 30분 이내인 경기를 찾는다.
- 이전에 알린 적 없는 경기만 native notification으로 푸시한다.
- 이미 알린 game_id는 ~/.cache/kbo-cli/notified.json 에 저장해 중복 방지.

자동 실행은 OS별 스케줄러를 사용한다:
- macOS: launchd plist (~/Library/LaunchAgents/com.kbo-cli.notify.plist)
- Linux: 사용자가 cron/systemd 직접 등록 (안내 메시지)
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from .models import Game

PLIST_LABEL = "com.kbo-cli.notify"
DEFAULT_INTERVAL_SECONDS = 300  # 5분마다 체크
DEFAULT_LEAD_MINUTES = 30


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "kbo-cli"


def notified_path() -> Path:
    return cache_dir() / "notified.json"


def _load_notified() -> dict[str, list[str]]:
    p = notified_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_notified(data: dict[str, list[str]]) -> None:
    cache_dir().mkdir(parents=True, exist_ok=True)
    notified_path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def already_notified(game_id: str) -> bool:
    data = _load_notified()
    today = datetime.now().strftime("%Y-%m-%d")
    return game_id in data.get(today, [])


def mark_notified(game_id: str) -> None:
    data = _load_notified()
    today = datetime.now().strftime("%Y-%m-%d")
    # 7일 이상 지난 키는 정리
    cutoff = datetime.now().date() - timedelta(days=7)
    for k in list(data.keys()):
        try:
            if datetime.strptime(k, "%Y-%m-%d").date() < cutoff:
                del data[k]
        except ValueError:
            del data[k]
    data.setdefault(today, []).append(game_id)
    _save_notified(data)


# ────────────────────── native notification ──────────────────────


def send_notification(title: str, message: str, sound: str = "Glass") -> bool:
    """OS별 native 알림 발송. 성공/실패 bool 반환."""
    sysname = platform.system()
    try:
        if sysname == "Darwin":
            # title에 작은따옴표가 들어가면 osascript가 깨지므로 이스케이프
            t = title.replace('"', '\\"')
            m = message.replace('"', '\\"')
            script = f'display notification "{m}" with title "{t}" sound name "{sound}"'
            subprocess.run(
                ["osascript", "-e", script],
                check=True,
                capture_output=True,
                timeout=5,
            )
            return True
        if sysname == "Linux":
            if shutil.which("notify-send"):
                subprocess.run(
                    ["notify-send", "--app-name=kbo-cli", title, message],
                    check=True, timeout=5,
                )
                return True
            return False
        if sysname == "Windows":
            # winrt 가 있으면 사용, 없으면 message box 폴백
            try:
                from win10toast import ToastNotifier  # type: ignore
                ToastNotifier().show_toast(title, message, duration=10, threaded=True)
                return True
            except ImportError:
                return False
        return False
    except (subprocess.SubprocessError, OSError):
        return False


# ────────────────────── 경기 매칭 ──────────────────────


@dataclass
class UpcomingGame:
    game: Game
    minutes_left: int


def find_upcoming(
    games: Iterable[Game],
    lead_minutes: int = DEFAULT_LEAD_MINUTES,
    favorite: str | None = None,
) -> list[UpcomingGame]:
    """시작 lead_minutes 분 이내, 아직 시작 전인 경기 추출."""
    from .data.teams import normalize

    fav = normalize(favorite) if favorite else ""
    now = datetime.now()
    threshold = now + timedelta(minutes=lead_minutes)

    out: list[UpcomingGame] = []
    for g in games:
        if not g.game_date_time or g.cancel or g.suspended:
            continue
        if g.status_code not in {"BEFORE"}:
            continue
        try:
            start = datetime.fromisoformat(g.game_date_time)
        except ValueError:
            continue
        if not (now <= start <= threshold):
            continue
        if fav:
            home = normalize(g.home_team_code)
            away = normalize(g.away_team_code)
            if fav not in {home, away}:
                continue
        minutes_left = max(0, int((start - now).total_seconds() // 60))
        out.append(UpcomingGame(game=g, minutes_left=minutes_left))
    return out


def format_message(ug: UpcomingGame) -> tuple[str, str]:
    g = ug.game
    title = f"⚾ KBO {ug.minutes_left}분 후 경기 시작"
    away = g.away_team_name or g.away_team_code or "원정"
    home = g.home_team_name or g.home_team_code or "홈"
    body = f"{away} vs {home}  @{g.stadium or '-'}  {g.start_time}"
    if g.broad_channel:
        body += f"  · {g.broad_channel}"
    return title, body


# ────────────────────── macOS launchd ──────────────────────


def _launch_agents_dir() -> Path:
    return Path(os.path.expanduser("~/Library/LaunchAgents"))


def plist_path() -> Path:
    return _launch_agents_dir() / f"{PLIST_LABEL}.plist"


def _kbo_executable() -> str:
    """launchd가 호출할 kbo 실행 파일 절대 경로."""
    candidate = shutil.which("kbo")
    if candidate:
        return candidate
    # 마지막 폴백: 현재 venv python -m kbo_cli
    return f"{sys.executable} -m kbo_cli"


def build_plist(interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
                all_games: bool = False) -> str:
    kbo_bin = _kbo_executable()
    args_xml = [
        "<string>notify</string>",
        "<string>check</string>",
    ]
    if all_games:
        args_xml.append("<string>--all</string>")

    # 단일 경로(kbo) vs python -m 형태 처리
    if " " in kbo_bin:
        parts = kbo_bin.split()
        program_args = "\n".join(f"    <string>{p}</string>" for p in parts) + "\n    " + "\n    ".join(args_xml)
    else:
        program_args = f"    <string>{kbo_bin}</string>\n    " + "\n    ".join(args_xml)

    log_dir = cache_dir()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
{program_args}
  </array>
  <key>StartInterval</key>
  <integer>{interval_seconds}</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{log_dir}/notify.out.log</string>
  <key>StandardErrorPath</key>
  <string>{log_dir}/notify.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
"""


def install_launchd(interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
                    all_games: bool = False) -> Path:
    """plist 작성 후 launchctl로 로드."""
    if platform.system() != "Darwin":
        raise RuntimeError("launchd 설치는 macOS에서만 가능합니다.")
    _launch_agents_dir().mkdir(parents=True, exist_ok=True)
    cache_dir().mkdir(parents=True, exist_ok=True)
    p = plist_path()
    p.write_text(build_plist(interval_seconds, all_games), encoding="utf-8")

    # 기존 로드 해제 후 다시 로드 (modern launchctl)
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(p)],
                   capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(p)],
                   check=True, capture_output=True)
    return p


def uninstall_launchd() -> bool:
    if platform.system() != "Darwin":
        return False
    p = plist_path()
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(p)],
                   capture_output=True)
    if p.exists():
        p.unlink()
        return True
    return False


def launchd_status() -> dict[str, str | bool]:
    if platform.system() != "Darwin":
        return {"installed": False, "platform": platform.system()}
    p = plist_path()
    if not p.exists():
        return {"installed": False, "plist": str(p)}
    uid = os.getuid()
    r = subprocess.run(["launchctl", "print", f"gui/{uid}/{PLIST_LABEL}"],
                       capture_output=True, text=True)
    return {
        "installed": True,
        "plist": str(p),
        "loaded": r.returncode == 0,
        "detail": (r.stdout.splitlines()[0] if r.stdout else r.stderr.splitlines()[0] if r.stderr else ""),
    }
