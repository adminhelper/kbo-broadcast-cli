"""터미널에서 KBO 선수 사진을 보여주기 위한 fetch/render 헬퍼.

이미지 출처 (둘 다 200으로 응답):
- KBO 공식: https://www.koreabaseball.com/Photo/Players/Now/{pcode}.jpg
- 네이버   : https://sports-phinf.pstatic.net/player/kbo/default/{pcode}.png

렌더 전략 (자동 감지):
1) iTerm2 (TERM_PROGRAM=iTerm.app 또는 LC_TERMINAL=iTerm2)
   → ESC ] 1337 ; File= ... BEL  인라인 이미지 escape
2) WezTerm — iTerm 프로토콜 지원하므로 같이 사용
3) chafa(외부 CLI) 가 PATH에 있으면 ANSI 컬러 블록으로 변환
4) 그 외 → 렌더 불가, 호출자는 사진 없이 텍스트만 표시한다
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
from pathlib import Path

import httpx

PHOTO_URLS = [
    "https://www.koreabaseball.com/Photo/Players/Now/{pcode}.jpg",
    "https://sports-phinf.pstatic.net/player/kbo/default/{pcode}.png",
]


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    p = Path(base) / "kbo-cli" / "players"
    p.mkdir(parents=True, exist_ok=True)
    return p


def fetch_player_image(pcode: str | int) -> Path | None:
    """선수 사진을 캐시에 받고 경로 반환. 받기 실패면 None."""
    pcode = str(pcode).strip()
    if not pcode:
        return None
    cached = _cache_dir() / f"{pcode}"
    # 확장자 다양하므로 .png/.jpg 두 가지 확인
    for ext in (".jpg", ".png"):
        if (cached.with_suffix(ext)).exists():
            return cached.with_suffix(ext)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://m.sports.naver.com/",
    }
    with httpx.Client(timeout=5.0, headers=headers, follow_redirects=True) as c:
        for url in PHOTO_URLS:
            try:
                r = c.get(url.format(pcode=pcode))
            except httpx.HTTPError:
                continue
            if r.status_code != 200 or len(r.content) < 1000:
                continue
            ext = ".jpg" if url.endswith(".jpg") else ".png"
            path = cached.with_suffix(ext)
            path.write_bytes(r.content)
            return path
    return None


# ────────────────────── terminal detection ──────────────────────


def _is_iterm() -> bool:
    return (
        os.environ.get("TERM_PROGRAM") == "iTerm.app"
        or os.environ.get("LC_TERMINAL") == "iTerm2"
        or os.environ.get("TERM_PROGRAM") == "WezTerm"
    )


def _has_chafa() -> bool:
    return shutil.which("chafa") is not None


# ────────────────────── render ──────────────────────


def render_player(pcode: str | int, width: int = 20, height: int = 10) -> str | None:
    """터미널 인라인으로 출력 가능한 텍스트를 반환.

    width/height는 cell 단위 (chafa) 또는 픽셀 hint (iTerm).
    """
    path = fetch_player_image(pcode)
    if path is None:
        return None

    if _is_iterm():
        return _iterm_inline(path, cells_w=width, cells_h=height)
    if _has_chafa():
        return _chafa_blocks(path, width=width, height=height)
    return None


def _iterm_inline(path: Path, cells_w: int, cells_h: int) -> str:
    """iTerm2 inline image escape. cells_w/h 는 cell 단위 크기 hint."""
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    # ESC ] 1337 ; File= name=<b64name>; inline=1; width=Ncell; height=Mcell;
    #             preserveAspectRatio=1 : <b64data> BEL
    name = base64.b64encode(path.name.encode()).decode("ascii")
    esc = "\x1b]1337;File="
    bel = "\x07"
    return (
        f"{esc}name={name};inline=1;"
        f"width={cells_w};height={cells_h};preserveAspectRatio=1:{b64}{bel}"
    )


def _chafa_blocks(path: Path, width: int, height: int) -> str:
    """chafa CLI를 호출해 ANSI 컬러 블록 문자로 변환."""
    try:
        r = subprocess.run(
            ["chafa", f"--size={width}x{height}", "--symbols=block",
             "--colors=256", str(path)],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return r.stdout
    except (subprocess.SubprocessError, OSError):
        pass
    return ""


def supports_inline_image() -> bool:
    """현재 터미널에서 사진 출력이 가능한지."""
    return _is_iterm() or _has_chafa()
