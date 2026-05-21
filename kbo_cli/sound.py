"""점수 변경 시 짧은 알림음/응원가 재생.

저작권 문제로 저장소에 음원을 동봉하지 않는다. 동작 방식:

1) 사용자가 응원가 파일을 직접 ~/.config/kbo-cli/cheers/{TEAM}.{mp3,wav,m4a,aiff,ogg}
   로 가져다 두면 점수 났을 때 그 팀 파일을 재생한다.
2) 파일이 없으면 OS 기본 알림음을 사용한다 (macOS: Glass, Linux: beep, Windows: MessageBeep).
3) `--no-sound` 또는 config의 sound=false 면 전부 무음.

재생 길이는 백그라운드 sub-process 가 자체적으로 끝까지 트는 식으로 둔다 (3 초 이내 cap 은 OS 별로 어렵고, 사용자 직접 트림으로 충분).
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


CHEER_EXTS = (".mp3", ".m4a", ".wav", ".aiff", ".ogg")


def cheer_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    p = Path(base) / "kbo-cli" / "cheers"
    return p


def cheer_file(team_code: str) -> Path | None:
    """팀 코드에 해당하는 응원가 파일 찾기. 없으면 None."""
    from .data.teams import normalize
    canon = normalize(team_code) or team_code
    d = cheer_dir()
    if not d.exists():
        return None
    for ext in CHEER_EXTS:
        p = d / f"{canon}{ext}"
        if p.exists():
            return p
    return None


def _system_default_sound() -> list[str] | None:
    sysname = platform.system()
    if sysname == "Darwin":
        # 점수가 났을 때의 default beep
        return ["afplay", "/System/Library/Sounds/Glass.aiff"]
    if sysname == "Linux":
        if shutil.which("paplay"):
            # 일반 알림음 경로 추정
            for cand in (
                "/usr/share/sounds/freedesktop/stereo/complete.oga",
                "/usr/share/sounds/alsa/Front_Center.wav",
            ):
                if Path(cand).exists():
                    return ["paplay", cand]
        if shutil.which("beep"):
            return ["beep"]
    return None


def _player_for(path: Path) -> list[str] | None:
    """파일 확장자에 맞는 OS 재생 명령."""
    sysname = platform.system()
    suffix = path.suffix.lower()
    if sysname == "Darwin":
        # afplay 는 mp3/aiff/wav/m4a/ogg/aac 등 다 지원
        return ["afplay", str(path)]
    if sysname == "Linux":
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]
        if shutil.which("mpv"):
            return ["mpv", "--really-quiet", "--no-video", str(path)]
        if suffix in (".wav", ".aiff") and shutil.which("aplay"):
            return ["aplay", "-q", str(path)]
        if shutil.which("paplay"):
            return ["paplay", str(path)]
    return None


def play_for_team(team_code: str | None) -> str:
    """팀 응원가 또는 기본 알림음 재생. 재생 방식 이름 반환.

    반환값: 'cheer', 'default', 'none'
    """
    if team_code:
        f = cheer_file(team_code)
        if f:
            cmd = _player_for(f)
            if cmd:
                try:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return "cheer"
                except OSError:
                    pass

    cmd = _system_default_sound()
    if cmd:
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return "default"
        except OSError:
            pass

    # 마지막 폴백: 터미널 벨
    try:
        import sys
        sys.stdout.write("\a")
        sys.stdout.flush()
    except OSError:
        pass
    return "none"
