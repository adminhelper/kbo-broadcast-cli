# kbo-cli

터미널에서 KBO 야구 경기 일정, 실시간 스코어, 문자중계, 박스스코어, 팀 순위를 확인하는 CLI.
선호 팀을 등록하면 해당 팀 정보가 우선 표시되고, 경기 시작 30분 전에 OS 알림이 발송된다.

## 필수 환경

- Python 3.11 이상
- macOS / Linux / Windows (자동 알림 설치는 macOS만 지원)
- UTF-8 한글 폰트가 설정된 터미널
- 인터넷 (네이버 스포츠, KBO 공식 사이트 접근)

## 설치

### uv

```bash
uv tool install git+https://github.com/adminhelper/kbo-broadcast-cli.git
```

uv가 없다면: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### pipx

```bash
pipx install git+https://github.com/adminhelper/kbo-broadcast-cli.git
```

### 소스에서

```bash
git clone https://github.com/adminhelper/kbo-broadcast-cli.git
cd kbo-broadcast-cli
uv sync
./kbo today          # macOS .venv UF_HIDDEN 우회 래퍼
```

설치 후 `kbo --help`가 동작하면 완료. `command not found`가 나오면 PATH에 `~/.local/bin`을 추가한다.

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

## 처음 사용 순서

### 1. 선호 팀 등록

```bash
kbo
```

처음 실행하면 셋업 위저드가 뜬다. 10개 구단 목록에서 번호(예: `5`) 또는 코드(예: `SSG`)를 입력하면 `~/.config/kbo-cli/config.json`에 저장된다.

이후 `kbo`는 선호 팀 대시보드를 보여준다: 어제 결과, 오늘 경기, 팀 순위, 시즌 요약, 오늘 전체 일정.

### 2. 라이브 중계 보기

```bash
kbo live              # 선호 팀 진행 중 경기 자동 선택
kbo live SSG          # 팀 코드
kbo live ssg-wo       # 매치업 (SSG vs 키움)
kbo live 1            # 오늘 일정의 1번째 경기
kbo live --here SSG   # 현재 터미널에서 (새 창 X)
```

기본 동작은 새 터미널을 옆에 열어 사이드 패널처럼 표시한다. 메인 터미널은 그대로 사용 가능.

- tmux 세션 안: 오른쪽으로 split-window
- macOS: iTerm 또는 Terminal.app 새 창 (화면 오른쪽 배치)
- Linux: 설치된 터미널 에뮬레이터 (gnome-terminal/konsole/xterm 등)

라이브 창 단축키: `q` 종료, `r` 즉시 새로고침 (자동 5초 폴링).

### 3. 알림 설치 (macOS)

```bash
kbo notify test          # 권한 확인 (한 번만 macOS 알림 권한 허용)
kbo notify install       # launchd 자동 등록
```

이후 컴퓨터가 켜져 있으면 5분마다 일정을 체크해 선호 팀 경기 시작 30분 전에 알림을 띄운다.

```bash
kbo notify status        # 현재 상태
kbo notify uninstall     # 자동 알림 제거
```

옵션:

```bash
kbo notify install --interval 60   # 체크 주기 1분
kbo notify install --all           # 선호 팀 외 전체 경기도 알림
kbo notify check --lead 60         # 60분 전부터 알림 발송
```

이미 보낸 알림은 `~/.cache/kbo-cli/notified.json`에 기록되어 중복되지 않는다 (7일 후 자동 정리).

Linux/Windows는 자동 등록이 없으니 cron, systemd timer, 작업 스케줄러로 `kbo notify check`를 5분 주기 등록한다.

## 명령 목록

| 명령 | 설명 |
|---|---|
| `kbo` | 선호 팀 대시보드 (없으면 셋업 위저드) |
| `kbo setup` | 선호 팀 재설정 |
| `kbo config` | 현재 설정 보기 |
| `kbo today` | 오늘 KBO 경기 (선호 팀 우선) |
| `kbo yesterday` | 어제 결과 |
| `kbo schedule [날짜]` | 특정 날짜 일정 — `2026-05-19`, `어제`, `3일전`, `내일` 등 |
| `kbo standings` | 팀 순위표 (선호 팀 강조) |
| `kbo team [코드]` | 팀 정보 + 응원 구호 (코드 생략 시 10팀 전체) |
| `kbo game <gameId>` | 박스스코어, 결승타, 라인업 |
| `kbo replay <gameId>` | 과거 경기 풀 리플레이 (박스 + 문자중계 전 이닝) |
| `kbo live [질의]` | 실시간 중계 TUI (새 창에서 실행) |
| `kbo notify ...` | 알림 관련 (`test`, `install`, `status`, `uninstall`, `check`, `run`) |

각 명령은 `--help`로 옵션을 확인할 수 있다.

## 팀 코드

| 코드 | 팀 |  | 코드 | 팀 |
|---|---|---|---|---|
| KIA | KIA 타이거즈 |  | LT | 롯데 자이언츠 |
| SS | 삼성 라이온즈 |  | KT | KT 위즈 |
| LG | LG 트윈스 |  | WO | 키움 히어로즈 |
| OB | 두산 베어스 |  | HH | 한화 이글스 |
| SSG | SSG 랜더스 |  | NC | NC 다이노스 |

네이버 API의 내부 코드 (`HT`, `SK`)는 자동으로 `KIA`, `SSG`로 매핑된다.

## 데이터 소스

- 일정·실시간 데이터: 네이버 스포츠 비공식 API (`api-gw.sports.naver.com/schedule/games/*`)
- 팀 순위: KBO 공식 사이트 `TeamRankDaily.aspx` HTML 스크래핑 (네이버 순위 엔드포인트는 인증 요구)

비공식 API라 KBO/네이버 측 변경에 따라 호환성이 깨질 수 있다.

## 트러블슈팅

**한글 깨짐** — 터미널이 UTF-8 + 한글 폰트로 설정되어 있는지 확인. iTerm2의 경우 Preferences → Profiles → Text → Font에서 D2Coding, Pretendard Mono 등을 지정.

**`command not found: kbo`** — PATH에 `~/.local/bin`이 없는 경우. 위 설치 섹션 마지막 명령 참고.

**`ModuleNotFoundError: No module named 'kbo_cli'`** (소스 개발 시) — macOS uv가 `.venv` 내부에 UF_HIDDEN 플래그를 붙여 Python 3.11+ `site.py`가 `.pth`를 건너뛰는 이슈. 동봉된 `./kbo` 래퍼가 `chflags nohidden` 후 `uv run --no-sync python -m kbo_cli`로 호출한다. uv tool/pipx 설치본에는 해당 없음.

**알림이 안 뜬다** — `kbo notify test`로 권한 확인. 거부했다면 시스템 설정 → 알림 → 스크립트 편집기 → 허용. 로그: `~/.cache/kbo-cli/notify.err.log`.

**`kbo live`가 새 창을 못 연다** — 자동 감지가 실패한 환경. `kbo live --here <질의>`로 현재 터미널에서 실행.

## 제한 사항

ABS존(자동 볼·스트라이크 판정 좌표) 실시간 표시는 미지원. 네이버·KBO가 좌표 데이터를 공개 엔드포인트로 노출하지 않아서 정식 API가 열리기 전까지는 추가하지 않는다.

## 라이선스

[MIT](LICENSE). 개인 학습 및 취미용으로 제공하며, 응원가 가사·구단 로고·중계 영상에 대한 권리는 각 권리자에게 있다. 본 저장소는 응원가 제목과 짧은 응원 구호만 포함한다.

이슈/제안: https://github.com/adminhelper/kbo-broadcast-cli/issues
