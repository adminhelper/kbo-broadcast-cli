# KBO Broadcast CLI

KBO 야구를 터미널에서 보는 CLI. 실시간 스코어, 문자중계, 박스스코어, 팀 순위, 응원가까지.

## 설치

`Python 3.11+` 만 있으면 됩니다.

```bash
# uv 사용자 (권장)
uv tool install git+https://github.com/adminhelper/kbo-broadcast-cli.git

# pipx 사용자
pipx install git+https://github.com/adminhelper/kbo-broadcast-cli.git
```

설치 후엔 어떤 터미널에서든 `kbo` 명령으로 바로 사용 가능합니다 — Claude Code, Codex, OMC, iTerm/zsh, VS Code 통합 터미널 어디든 OK.

## 사용법

```bash
kbo --help               # 도움말
kbo today                # 오늘의 경기
kbo standings            # 팀 순위
kbo game <gameId>        # 박스스코어 + 결승타 + 라인업
kbo team KIA             # 팀 정보 + 응원가
kbo live <gameId>        # 실시간 중계 TUI (Textual)
kbo schedule 2026-05-19
```

### 로컬 개발

```bash
git clone https://github.com/adminhelper/kbo-broadcast-cli.git
cd kbo-broadcast-cli
uv sync
./kbo today              # 래퍼 스크립트 (macOS .venv UF_HIDDEN 우회)
```

`gameId`는 `./kbo today` 결과의 마지막 열에서 확인 가능 (예: `20260519SKWO02026`).

팀 코드: `KIA` `SS`(삼성) `LG` `OB`(두산) `SSG` `LT`(롯데) `KT` `WO`(키움) `HH`(한화) `NC`.

> 네이버 API가 보내는 내부 코드(`HT`, `SK`)도 자동으로 `KIA`/`SSG`로 매핑됩니다.

## 데이터 소스

- **실시간 경기 데이터** — 네이버 스포츠 비공식 API (`api-gw.sports.naver.com`)
  - `/schedule/games`, `/schedule/calendar` — 일정
  - `/schedule/games/{gameId}/relay` — 문자중계, 현재 카운트/주자/이닝
  - `/schedule/games/{gameId}/record` — 박스스코어, 결승타, 라인업
  - `/schedule/games/{gameId}/preview` — 예고 라인업, 시즌 기록
- **팀 순위** — KBO 공식 사이트 `TeamRankDaily.aspx` HTML 스크래핑
  - (네이버 `/schedule/standings`는 인증을 요구해서 폴백)

비공식 API이므로 KBO/네이버 측 변경에 따라 깨질 수 있습니다.

## 라이브 TUI 단축키

- `q` — 종료
- `r` — 즉시 새로고침 (자동 5초 폴링)

## 알려진 한계 — ABS존 실시간 표시

요청하신 6가지 중 **ABS존(자동 볼·스트라이크 판정 좌표) 실시간 표시는 현재 지원하지 않습니다**.

조사 결과:
- 네이버 스포츠 공개 API에는 ABS 존별 좌표(x,y)와 판정(B/S) 데이터를 노출하는 엔드포인트가 없음
- KBO 공식 사이트도 ABS 좌표를 외부에 제공하지 않음
- 라이브 페이지에서 표시되는 스트라이크존 시각화는 클라이언트 측에서 렌더링되며, 원본 좌표는 보호된 endpoint에서 옴

향후 방향:
1. KBO/네이버가 공식 API를 공개하면 즉시 통합
2. Playwright로 라이브 페이지를 자동 조작해 표시된 존 이미지를 OCR/추출 (heavy하고 fragile)
3. PTS·Trackman 등 외부 트래킹 서비스의 유료 API와 연동

## 트러블슈팅

### `ModuleNotFoundError: No module named 'kbo_cli'`

macOS에서 `uv`가 `.venv/` 내부 파일에 `UF_HIDDEN` flag를 붙여 Python 3.11+ `site.py`가 `.pth`를 건너뛰는 이슈가 있습니다. `./kbo` 래퍼 스크립트가 자동으로 `chflags nohidden`을 수행하니, 항상 `./kbo` 또는 `uv run --no-sync python -m kbo_cli` 형태로 호출하세요.

## 라이선스 / 면책

본 도구는 개인 학습·취미 용도로 제공되며, 응원가 가사·구단 로고·중계 영상에 대한 권리는 각 권리자에게 있습니다. 응원가 목록은 제목과 짧은 응원 구호만 포함합니다.
