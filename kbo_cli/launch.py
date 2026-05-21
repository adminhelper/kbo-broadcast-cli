"""라이브 TUI를 옆에 사이드 패널처럼 띄우기 위한 새 터미널 launcher.

전략 (자동 선택):
1) tmux 세션 안 ($TMUX 설정됨) → split-window 로 오른쪽 패널 생성
2) macOS + iTerm 실행 중 → iTerm 새 창
3) macOS + Terminal.app → Terminal 새 창
4) 외 환경 → 폴백 안내
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


def _quote(arg: str) -> str:
    """shell 인용 (간단). game_id 등 숫자/영문이라 아주 단순화."""
    if all(c.isalnum() or c in "-_." for c in arg):
        return arg
    return "'" + arg.replace("'", "'\\''") + "'"


def _kbo_bin() -> str:
    """현재 프로세스의 kbo 실행 파일 절대 경로 추정."""
    cand = shutil.which("kbo")
    return cand or "kbo"


def in_tmux() -> bool:
    return bool(os.environ.get("TMUX"))


def launch_side_panel(
    game_id: str,
    poll: float | None = None,
    meta_poll: float | None = None,
) -> str:
    """`kbo live <game_id> --here`를 옆 패널/새 창에서 실행.

    실행 방식 이름을 문자열로 반환 ('tmux' / 'iterm' / 'terminal' / 'inline').
    """
    parts = [_quote(_kbo_bin()), "live", _quote(game_id), "--here"]
    if poll is not None:
        parts += ["--poll", str(poll)]
    if meta_poll is not None:
        parts += ["--meta-poll", str(meta_poll)]
    cmd = " ".join(parts)

    # 1) tmux 세션 안이면 split-window
    if in_tmux() and shutil.which("tmux"):
        # 오른쪽으로 분할, 70% 폭(메인 패널이 작아지지 않게 새 패널이 메인이 됨)
        subprocess.run(["tmux", "split-window", "-h", "-l", "70%", cmd], check=False)
        return "tmux"

    sysname = platform.system()
    if sysname == "Darwin":
        # 2) iTerm 우선
        if _is_app_running("iTerm") or _has_app_bundle("iTerm"):
            _launch_iterm(cmd)
            return "iterm"
        # 3) Terminal.app
        _launch_terminal_app(cmd)
        return "terminal"

    if sysname == "Linux":
        # gnome-terminal / konsole / xterm 등 시도
        for term in ("gnome-terminal", "konsole", "xfce4-terminal", "xterm"):
            if shutil.which(term):
                if term == "gnome-terminal":
                    subprocess.Popen([term, "--", "bash", "-lc", cmd])
                elif term == "konsole":
                    subprocess.Popen([term, "-e", "bash", "-lc", cmd])
                else:
                    subprocess.Popen([term, "-e", "bash", "-lc", cmd])
                return term
        return "inline"

    return "inline"


def _is_app_running(app_name: str) -> bool:
    try:
        r = subprocess.run(
            ["osascript", "-e",
             f'tell application "System Events" to (name of processes) contains "{app_name}"'],
            capture_output=True, text=True, timeout=3,
        )
        return r.stdout.strip().lower() == "true"
    except (subprocess.SubprocessError, OSError):
        return False


def _has_app_bundle(app_name: str) -> bool:
    return Path(f"/Applications/{app_name}.app").exists()


def _launch_iterm(cmd: str) -> None:
    """iTerm 새 창을 화면 오른쪽 절반에 배치하고 명령 실행."""
    script = f'''
    tell application "iTerm"
        activate
        set newWindow to (create window with default profile)
        tell current session of newWindow
            write text "{cmd}"
        end tell
        -- 화면 오른쪽 절반으로 이동
        tell application "System Events"
            tell process "iTerm2"
                try
                    set position of window 1 to {{720, 0}}
                    set size of window 1 to {{720, 900}}
                end try
            end tell
        end tell
    end tell
    '''
    subprocess.run(["osascript", "-e", script], check=False, capture_output=True)


def _launch_terminal_app(cmd: str) -> None:
    """Terminal.app 새 창에서 실행."""
    # do script 가 새 창을 만들어줌
    script = f'tell application "Terminal" to activate\n' \
             f'tell application "Terminal" to do script "{cmd}"'
    subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
