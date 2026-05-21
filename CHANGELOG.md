# Changelog

[Keep a Changelog](https://keepachangelog.com/) 형식 + [Semantic Versioning](https://semver.org/) 을 따른다.

## [0.3.0] - 2026-05-22

### Added
- `kbo live --demo` — 가짜 1회초~2회말 시뮬 (만루 홈런, 백투백, 3점 홈런 등 13단계, 베이스 ◆/◇ 변화 표시).
- `kbo cheers` 명령군 — `add` / `list` / `play` / `remove` / `dir` / `init-demo` (macOS `say` TTS 자동 등록) / `add-url` (`yt-dlp` 로 YouTube 음원 추출).
- `kbo preview <gameId>` — 라이브 패널을 다양한 폭(160/100/60) 에 SVG·텍스트로 저장 (스크린샷 검증용).
- `kbo live --no-sound` 플래그 — 사운드 자동 재생 비활성.
- cmux 호환 — `$CMUX_SURFACE_ID` 감지 시 macOS iTerm/Terminal 새 창으로 폴백.
- 점수 변경 시 macOS native 알림 (`⚾ {팀} N점`).
- 홈런 감지 — `textRelays` 에 "홈런" 키워드 들어오면 별도 알림 (`💥 {팀} 홈런!`).
- 응원가 디렉토리 `~/.config/kbo-cli/cheers/{TEAM}.{mp3,m4a,wav,aiff,ogg}` 자동 인식.

### Changed
- 라이브 TUI 전면 재설계 (네이버 스타일 6 패널):
  - `SCORE` — 양 팀 R/H/E, 이닝 배지, B/S/O 트래픽 라이트 색상 (초록·노랑·빨강), 현재 투수 + 투구수
  - `FIELD` — ▶ 타석 + 다이아몬드 미니맵 최상단, 외야/유격/3루/2루/1루/투수/포수 표 배치, 베이스에 주자 들어가면 같은 행에 `◆ 주자` 표시
  - `ON DECK` — 다음 3타자 + 양팀 시즌 평균 타율
  - `PITCHER CARD` / `BATTER CARD` — 시즌 + 오늘 기록, 상대 전적
  - `RELAY` — 문자중계 (min-height 9 확보)
- `FieldWidget` 반응형 — `render()` override 로 tmux 패널 resize 시 자동 layout 재구성 (60/40 폭 임계로 컬럼 축소).
- 베이스 상태 표시 — "비어있음" 라벨 제거, 주자 있는 베이스에만 `◆ 주자` 표시.
- 라이브 데이터 매핑 수정 — `relay.currentGameState` + `relay.{home,away}Lineup` 기준 (이전 잘못 보던 `baseInfo` / `Entry` 키).
- 폴링 전략 — relay 2초, schedule/박스스코어 60초 분리. UI 는 0.5초마다 캐시 read-only 렌더.
- 팀 이름 표시 — Naver 내부 코드(`SK`, `HT`) 대신 친숙한 약어(`SSG`, `KIA`) 일관 노출.
- `kbo live` 인자 해석 — 팀 코드(`SSG`) / 매치업(`ssg-wo`, `ssg vs wo`) / 오늘 일정 번호(`1`~`9`) / 정식 게임 ID 모두 인식.

### Fixed
- TTS 자동 재생 비활성화 — 사용자 요청에 따라 알림만, 사운드는 `kbo cheers play` 로 명시적 호출.

## [0.2.0] - 2026-05-21

### Added
- `kbo player <이름|pcode>` — 선수 정보 + 사진. 이름이면 오늘 라인업에서 매칭, 숫자면 네이버 pcode로 직접 조회. iTerm2 / WezTerm 인라인 이미지, 그 외엔 chafa 폴백.
- `kbo live` 가 인자 없이도 동작: 선호 팀 진행 중 경기를 자동 선택, 팀 코드(`SSG`) / 매치업(`ssg-wo` / `wo vs ssg`) / 오늘 일정 번호(`1`~`9`) 모두 인식.
- `kbo live` 가 옆에 사이드 패널처럼 새 창을 연다. tmux 안이면 `split-window`, macOS면 iTerm/Terminal 새 창, Linux면 첫 가용 터미널 에뮬레이터. `--here`로 inline 폴백.
- `kbo notify` 서브커맨드 그룹 — `check` / `test` / `install` / `uninstall` / `status` / `run`. macOS launchd 자동 등록으로 선호 팀 경기 시작 30분 전 native 알림. `~/.cache/kbo-cli/notified.json` 으로 중복 방지(7일 자동 정리).
- `kbo replay <gameId>` — 과거 경기 풀 리플레이 (스코어보드 + 결승타·홈런·도루 + 양팀 박스스코어 + 전 이닝 문자중계).
- `kbo yesterday` / 상대 날짜 파싱 (`어제`, `3일전`, `내일`, `-N` 등).
- 선호 팀 등록 위저드 + 대시보드(`kbo` 인자 없이 호출), 모든 명령에서 선호 팀 자동 ⭐ 강조 + 우선 정렬.

### Changed
- 라이브 TUI 레이아웃을 네이버 라이브 페이지 스타일로 전면 재설계: `SCORE` / `FIELD` / `ON DECK` / `PITCHER CARD` / `BATTER CARD` / `RELAY` 6패널 구성. `FIELD` 는 수비 9포지션 이름과 다이아몬드 주자 표시를 함께 그린다.
- 라이브 TUI 폴링을 두 워커로 분리: relay 기본 2초, 스케줄·박스스코어 60초. UI 는 0.5초마다 캐시만 다시 렌더해서 깜빡임을 줄였다.
- 라이브 데이터 매핑을 `relay.currentGameState` + `relay.{home,away}Lineup` 기준으로 수정(이전엔 존재하지 않는 `baseInfo` / `Entry` 키를 보고 있었다). 주자, 카운트, 현재 타자/투수, 시즌 ERA/AVG, 오늘 H-AB 가 이제 모두 표시된다.
- 팀 코드를 친숙한 약어로 변경(`HT → KIA`, `SK → SSG`). 네이버 내부 코드 `HT`/`SK` 는 alias 로 계속 받는다.

### Fixed
- macOS uv 가 `.venv` 내부 파일에 `UF_HIDDEN` 플래그를 붙여 Python `site.py` 가 `.pth` 를 건너뛰는 이슈 — 로컬 개발용 `./kbo` 래퍼가 `chflags nohidden` 처리 후 `uv run --no-sync python -m kbo_cli` 로 호출.
- `kbo today` 출력의 Game ID 컬럼이 잘려서 안 보이던 문제 — `no_wrap` + `overflow="fold"` 적용.

## [0.1.0] - 2026-05-20

### Added
- 첫 공개 릴리스.
- `kbo today` / `schedule` / `standings` / `game` / `team` / `live` 기본 명령.
- 네이버 스포츠 비공식 API + KBO 공식 사이트 스크래핑.
- Rich 기반 컬러 테이블, Textual 기반 라이브 중계 TUI.
- 응원가 / 팀 메타데이터 10개 구단.
