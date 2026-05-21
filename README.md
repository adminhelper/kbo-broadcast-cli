# ⚾ kbo-cli — 터미널에서 보는 KBO 야구

> KBO 경기 일정·실시간 스코어·문자중계·박스스코어·팀 순위·응원가까지 모두 터미널에서.
> 선호 팀을 한 번만 등록하면 자기 팀 위주로 정렬되고, 경기 시작 30분 전 알림까지 자동으로.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Made with Rich](https://img.shields.io/badge/Made_with-Rich-ff69b4.svg)](https://github.com/Textualize/rich)

---

## 📚 목차

1. [필수 환경](#1-필수-환경)
2. [설치 방법](#2-설치-방법)
3. [사용 순서 (처음 쓰는 사람용)](#3-사용-순서-처음-쓰는-사람용)
4. [전체 명령 모음](#4-전체-명령-모음)
5. [경기 시작 30분 전 자동 알림](#5-경기-시작-30분-전-자동-알림)
6. [팀 코드](#6-팀-코드)
7. [데이터 소스](#7-데이터-소스)
8. [트러블슈팅](#8-트러블슈팅)
9. [알려진 한계 — ABS존](#9-알려진-한계--abs존)
10. [라이선스](#10-라이선스)

---

## 1. 필수 환경

| 항목 | 요구사항 |
|---|---|
| **Python** | 3.11 이상 |
| **OS** | macOS / Linux / Windows (알림 자동화는 macOS만 지원, 나머지는 수동) |
| **터미널** | UTF-8 + 한글 폰트 지원 (iTerm2, WezTerm, Windows Terminal, VS Code 통합 터미널 등) |
| **인터넷** | 네이버 스포츠 + KBO 공식 사이트 접근 |

Python이 없다면 [python.org](https://www.python.org/downloads/) 또는 `brew install python@3.12`로 먼저 설치.

---

## 2. 설치 방법

설치 도구 셋 중 **편한 것 하나**만 고르면 됩니다.

### 방법 A — `uv` (가장 빠름, 권장)

```bash
# uv 자체가 없다면 한 줄로 설치
curl -LsSf https://astral.sh/uv/install.sh | sh

# kbo-cli 설치
uv tool install git+https://github.com/adminhelper/kbo-broadcast-cli.git
```

### 방법 B — `pipx` (Python 표준 도구)

```bash
# pipx 자체가 없다면
brew install pipx        # macOS
# 또는: python3 -m pip install --user pipx && pipx ensurepath

# kbo-cli 설치
pipx install git+https://github.com/adminhelper/kbo-broadcast-cli.git
```

### 방법 C — 소스에서 직접 (개발자용)

```bash
git clone https://github.com/adminhelper/kbo-broadcast-cli.git
cd kbo-broadcast-cli
uv sync
./kbo today    # 동봉된 래퍼 스크립트 사용 (macOS의 UF_HIDDEN 우회)
```

### 설치 확인

```bash
kbo --help
```

`Usage: kbo [OPTIONS] COMMAND [ARGS]…` 가 나오면 성공.

> 만약 `command not found: kbo`가 나오면 PATH에 `~/.local/bin`이 안 잡힌 거예요.
> 자세한 해결법은 [트러블슈팅 ②](#-command-not-found-kbo) 참고.

---

## 3. 사용 순서 (처음 쓰는 사람용)

### 🥇 STEP 1 — 선호 팀 등록 (한 번만)

```bash
kbo
```

처음 실행하면 **셋업 위저드**가 자동으로 뜹니다. 10개 구단 목록에서 번호나 코드(예: `5` 또는 `SSG`)를 입력하면 끝.

```
번호  코드  팀
 1   KIA   KIA 타이거즈
 2   SS    삼성 라이온즈
 3   LG    LG 트윈스
 4   OB    두산 베어스
 5   SSG   SSG 랜더스
 ...
팀 번호 또는 코드 입력 (예: 5 또는 KIA): 5
✅ 선호 팀이 SSG 랜더스로 저장되었습니다.
```

이후로 모든 명령에서 자기 팀이 **⭐ 표시**와 함께 가장 먼저 보입니다.

> 팀 바꾸고 싶으면 `kbo setup`을 다시 실행. 현재 설정 확인은 `kbo config`.

---

### 🥈 STEP 2 — 매일 보기

```bash
kbo
```

선호 팀 **대시보드**가 뜹니다:

```
⭐ SSG 랜더스 대시보드   2026-05-21

[SSG 어제 결과]  SSG 5:6 키움 (종료)
[SSG 오늘 경기]  SSG vs 키움 @고척 18:30

[KBO 팀 순위]
  ...
  4위 ⭐ SSG  22승 1무 21패  승률 0.512   ← 내 팀 하이라이트
  ...

[현재 SSG 시즌] 4위  22승 1무 21패  최근10 3승7패  연속 3패
[오늘 전체 KBO 경기]  ...
```

이것 한 화면으로 어제 결과 → 오늘 경기 → 시즌 위치까지 다 들어옵니다.

---

### 🥉 STEP 3 — 경기 시작 30분 전 알림 켜기 (macOS)

```bash
# 1) 알림 권한 테스트 (한 번만)
kbo notify test
```

macOS 우상단에 **알림이 떠야** 합니다. 처음엔 권한 요청 팝업이 뜨니까 **허용** 클릭.

```bash
# 2) 자동 알림 켜기
kbo notify install
```

이제부터 컴퓨터를 켜둔 동안 launchd가 5분마다 자동으로 체크해서, **SSG 경기 시작 30분 전에 알림을 띄워줍니다**.

```bash
# 상태 확인 / 끄기
kbo notify status
kbo notify uninstall
```

---

### 🏅 STEP 4 — 경기 보기

```bash
# 오늘 경기 일정 + 라이브 스코어
kbo today

# 어제 결과
kbo yesterday

# 다른 날짜
kbo schedule 2026-05-19
kbo schedule 어제
kbo schedule 3일전
```

`Game ID`(예: `20260520WOSSG02026`)를 보고 원하는 경기를 깊게 파보세요:

```bash
# 박스스코어 + 결승타 + 라인업
kbo game 20260520WOSSG02026

# 과거 경기 풀 리플레이 (스코어 + 박스 + 문자중계 전체 이닝)
kbo replay 20260519SKWO02026

# 실시간 중계 TUI (Textual) — 진행 중 경기에서 진가 발휘
kbo live 20260521WOSSG02026
```

**`kbo live` 단축키**
- `q` — 종료
- `r` — 즉시 새로고침 (자동 5초 폴링)

---

### 🎉 STEP 5 — 응원가 / 팀 정보

```bash
kbo team SSG     # 응원 구호, 대표 응원가 제목, 홈구장, 마스코트
kbo team         # 10개 구단 카드 한 번에 보기
```

---

## 4. 전체 명령 모음

| 명령 | 설명 |
|---|---|
| `kbo` | 선호 팀 대시보드 (첫 실행 시 셋업 위저드) |
| `kbo setup` | 선호 팀 재설정 |
| `kbo config` | 현재 설정 확인 |
| `kbo today` | 오늘 KBO 경기 (선호 팀 ⭐ 우선) |
| `kbo yesterday` | 어제 KBO 결과 |
| `kbo schedule [날짜]` | 특정 날짜 일정 — `2026-05-19` / `어제` / `3일전` / `내일` 등 |
| `kbo standings` | KBO 팀 순위표 (선호 팀 하이라이트) |
| `kbo team [코드]` | 팀 정보 + 응원가 (코드 생략 시 10팀 전부) |
| `kbo game <gameId>` | 박스스코어 + 결승타 + 라인업 |
| `kbo replay <gameId>` | 과거 경기 풀 리플레이 (스코어 + 박스 + 문자중계 전 이닝) |
| `kbo live <gameId>` | 실시간 중계 TUI (Textual full-screen) |
| `kbo notify test` | 알림 한 번 발송 (권한 확인) |
| `kbo notify install` | 백그라운드 자동 알림 설치 (macOS launchd) |
| `kbo notify status` | 자동 알림 상태 |
| `kbo notify uninstall` | 자동 알림 제거 |
| `kbo notify check` | 지금 한 번만 임박 경기 체크 (스케줄러 호출용) |
| `kbo notify run` | 포그라운드 워처 (Ctrl+C로 종료) |

각 명령은 `--help`로 옵션을 볼 수 있습니다. 예: `kbo notify install --help`.

---

## 5. 경기 시작 30분 전 자동 알림

### macOS — 한 줄 설치

```bash
kbo notify install
```

내부적으로 `~/Library/LaunchAgents/com.kbo-cli.notify.plist`를 만들고 launchctl로 로드합니다. 로그인하면 자동으로 5분마다 임박 경기 체크.

### 옵션

```bash
kbo notify install --interval 60   # 1분마다 체크 (기본 300초=5분)
kbo notify install --all           # 선호 팀 외 전체 경기 알림
kbo notify check --lead 60         # 60분 전부터 알림 (기본 30분)
```

### Linux / Windows

자동 설치는 아직 macOS만 지원합니다. 다른 OS는 직접 스케줄링하세요.

**Linux (cron 예시)** — 5분마다 체크:
```cron
*/5 * * * *  /home/user/.local/bin/kbo notify check
```

**Linux (systemd timer)** — 더 견고함:
```ini
# ~/.config/systemd/user/kbo-notify.timer
[Unit]
Description=KBO pre-game notifier
[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
```

```ini
# ~/.config/systemd/user/kbo-notify.service
[Unit]
Description=KBO pre-game notifier
[Service]
Type=oneshot
ExecStart=%h/.local/bin/kbo notify check
```

```bash
systemctl --user enable --now kbo-notify.timer
```

**Windows** — 작업 스케줄러에 `kbo notify check` 5분 주기 등록.

### 중복 방지

이미 알린 게임 ID는 `~/.cache/kbo-cli/notified.json`에 기록되어 중복 발송을 막습니다. 7일 지난 항목은 자동 정리.

### 권한 (macOS 최초 1회)

처음 `kbo notify test` 실행 시 알림 권한 팝업이 뜹니다 → **허용**.
이미 거부했다면: **시스템 설정 → 알림 → 스크립트 편집기 (또는 터미널)** → 알림 허용 ON.

---

## 6. 팀 코드

| 코드 | 팀 |  | 코드 | 팀 |
|---|---|---|---|---|
| `KIA` | KIA 타이거즈 |  | `LT` | 롯데 자이언츠 |
| `SS` | 삼성 라이온즈 |  | `KT` | KT 위즈 |
| `LG` | LG 트윈스 |  | `WO` | 키움 히어로즈 |
| `OB` | 두산 베어스 |  | `HH` | 한화 이글스 |
| `SSG` | SSG 랜더스 |  | `NC` | NC 다이노스 |

> 네이버 API의 내부 코드 (`HT`, `SK`)도 자동으로 `KIA`/`SSG`로 매핑됩니다.

---

## 7. 데이터 소스

- **실시간 경기 데이터** — 네이버 스포츠 비공식 API (`api-gw.sports.naver.com`)
  - `/schedule/games`, `/schedule/calendar` — 일정
  - `/schedule/games/{gameId}/relay` — 문자중계, 현재 카운트/주자/이닝
  - `/schedule/games/{gameId}/record` — 박스스코어, 결승타, 라인업
  - `/schedule/games/{gameId}/preview` — 예고 라인업, 시즌 기록
- **팀 순위** — KBO 공식 사이트 `TeamRankDaily.aspx` HTML 스크래핑
  - (네이버 `/schedule/standings`는 인증 요구해서 폴백)

비공식 API이므로 KBO/네이버 측 변경에 따라 깨질 수 있습니다.

---

## 8. 트러블슈팅

### ① `kbo` 한글이 깨져 보일 때

터미널 UTF-8 / 한글 폰트 확인. iTerm2는 **Preferences → Profiles → Text → Font**에서 D2Coding, Pretendard Mono 등 한글 지원 폰트 설정.

### ② `command not found: kbo`

`uv tool` / `pipx`로 설치했는데 명령이 안 잡히는 경우 PATH에 `~/.local/bin`이 없는 거예요.

```bash
# zsh 사용자
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# bash 사용자
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### ③ `ModuleNotFoundError: No module named 'kbo_cli'` (소스 개발 시)

macOS에서 `uv`가 `.venv/` 내부 `.pth` 파일에 `UF_HIDDEN` flag를 붙여 Python 3.11+ `site.py`가 건너뛰는 이슈. 동봉된 `./kbo` 래퍼가 자동으로 `chflags nohidden` 처리하니 **`./kbo` 또는 `uv run --no-sync python -m kbo_cli`** 형태로 호출하세요. (사용자 설치본 — `uv tool` / `pipx` — 에는 해당 없음.)

### ④ 알림이 안 떠요

```bash
kbo notify test        # 권한 확인
kbo notify status      # launchd 활성 여부
tail -f ~/.cache/kbo-cli/notify.err.log   # 에러 로그
```

권한 거부했다면 시스템 설정 → 알림 → 스크립트 편집기 → 알림 허용 ON.

### ⑤ 라이브 TUI(`kbo live`)가 안 보여요

`kbo live`는 full-screen TUI입니다. Claude Code/Codex 같은 AI 도구 안에서는 `!` 접두사로 백그라운드 호출하면 출력이 안 보여요. **자기 터미널**에서 직접 실행하세요.

---

## 9. 알려진 한계 — ABS존

**ABS존(자동 볼·스트라이크 판정 좌표) 실시간 표시는 미지원**입니다.

- 네이버 스포츠 공개 API에 ABS 좌표(x, y) 엔드포인트 없음
- KBO 공식 사이트도 ABS 좌표 미공개
- 라이브 페이지 시각화는 클라이언트 렌더링이라 원본 좌표는 보호된 endpoint

향후 가능한 방향:
1. KBO/네이버 공식 API 공개 시 즉시 통합
2. Playwright로 페이지 자동화 + 이미지 OCR (무겁고 fragile)
3. PTS / Trackman 등 외부 트래킹 서비스 유료 API

---

## 10. 라이선스

[MIT License](LICENSE) — 자유롭게 사용·수정·재배포 가능.

본 도구는 **개인 학습·취미 용도**로 제공되며,
응원가 가사·구단 로고·중계 영상에 대한 권리는 각 권리자에게 있습니다.
응원가 데이터는 곡 제목과 짧은 응원 구호만 포함합니다 (가사 미포함).

---

### 🤝 기여 / 이슈

버그/제안: https://github.com/adminhelper/kbo-broadcast-cli/issues

Pull Request 환영합니다.

⚾ **Play ball!**
