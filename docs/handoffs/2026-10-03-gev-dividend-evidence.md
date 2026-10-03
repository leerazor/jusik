# 등록 종목 배당 검증 다음 단계

- 2026-10-03 UTC, `/home/kwl/projects/jusik`, main `78b10ee` 기준 자료 작업. 코드 변경 없음.
- 등록 revision 1/16종목. runner paused, 개발 서비스/timer/기존 optimizer inactive, 운영 웹 active. 자동매매·PAPER/live 승격·Pages 제외, 같은 대화 30분 heartbeat 유지.
- GEV 2026-03-17/06-16 사건의 공식 금액·기준일·지급일 2건을 기존 importer로 사본 검증 후 연구 검토 DB에 추가했다. 배당락일·주당 기준은 미확인으로 partial/excluded 유지. 적격 13/111 그대로다.
- [작업 기록](../development-records/2026-10-03-gev-dividend-evidence.md)과 audit `/home/kwl/.local/share/jusik/portfolio-audit/20261003-gev-dividend-evidence/` 재사용. 같은 공지·같은 캐시 대조를 반복하지 않는다.
- VRT 2024-12-03 공급자 0.038 대 공식 0.0375. 공식 웹 본문 확인, 원문 다운로드 403으로 import 없음. SOXL 4건과 함께 기존 raw SHA 대조: 5건 모두 원문=저장 금액. 정규화에서 생긴 차이가 아니다.
- 다음 시작: 공식 현금 금액과 날짜/주당 기준을 독립 검증해 기존 provider revision과 연결하는 입력 계약을 bounded 설계한다. 기존 strict 비교의 허용 오차 완화·matched 강제 변경·원본 덮어쓰기는 금지. 배당락일은 기준일로 자동 추정하지 않는다.
- 아직 NAV·비용·공식 달력·신원·성과 비교는 미완료다. 전체 과거 PIT 연구를 새 등록 종목 연구의 선행 차단으로 되살리지 않는다. 계약 마련 뒤 독립 계산 검증과 사전등록 비교로 이어간다.

재개 문장: `MEMORY.md`와 이 인계를 읽고 진행 writer·등록 revision을 확인한 뒤, 원문 정밀도를 보존하는 공식 배당 입력 계약부터 이어가세요.
