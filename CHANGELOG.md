# Changelog

[Keep a Changelog](https://keepachangelog.com/) 형식 + [Semantic Versioning](https://semver.org/) 을 따른다.

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
